import cv2
import os
import base64
import requests
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
import logging
from collections import deque
from openai import OpenAI

# 默认日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def normalize_bbox_to_pixels(bbox, img_width, img_height):
    """将模型返回的 bbox 转为原图像素坐标。

    支持：
    - 0~1 归一化坐标
    - Qwen-VL 等模型的 0~1000 相对坐标
    - 已是像素坐标的情况（如 LMStudio 按提示词返回像素）
    """
    if not bbox or len(bbox) < 4:
        return 0, 0, 0, 0

    x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    max_val = max(x1, y1, x2, y2)

    if max_val <= 1.0:
        x1 *= img_width
        y1 *= img_height
        x2 *= img_width
        y2 *= img_height
    elif max_val <= 1000 and (
        img_width > 1000 or img_height > 1000 or
        x1 > img_width or y1 > img_height or
        x2 > img_width or y2 > img_height
    ):
        x1 = x1 / 1000.0 * img_width
        y1 = y1 / 1000.0 * img_height
        x2 = x2 / 1000.0 * img_width
        y2 = y2 / 1000.0 * img_height

    x1 = max(0, min(x1, img_width))
    y1 = max(0, min(y1, img_height))
    x2 = max(0, min(x2, img_width))
    y2 = max(0, min(y2, img_height))

    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    return int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))


class AiUtils:
    """AI自动标注工具类，封装了与大模型API交互和视频处理的核心功能"""
    
    def __init__(self, model_api_url: str, api_key: str = None, prompt: str = None, timeout: int = 30, inference_tool: str = "OpenAI", model: str = "qwen/qwen3-vl-8b"):
        """初始化自动标注器
        
        Args:
            model_api_url: 大模型API地址
            api_key: API密钥（如果需要）
            prompt: 自定义提示词
            timeout: HTTP请求超时时间（秒）
            inference_tool: 推理工具，支持OpenAI
            model: 模型名称
        """
        self.model_api_url = model_api_url
        self.api_key = api_key
        self.session = requests.Session()
        self.timeout = timeout
        self.inference_tool = inference_tool
        self.model = model
        # 默认提示词
        self.default_prompt = "检测图中物体，返回JSON：{\"detections\":[{\"label\":\"类别\",\"confidence\":0.9,\"bbox\":[x1,y1,x2,y2]}]}"
        # 使用用户自定义提示词或默认提示词
        self.prompt = prompt if prompt else self.default_prompt
        
        # 定义颜色映射（不同类别使用不同颜色）
        self.colors = {
            "person": (0, 255, 0),
            "car": (255, 0, 0),
            "bicycle": (0, 0, 255),
            "dog": (255, 255, 0),
            "cat": (255, 0, 255),
            "人": (0, 255, 0),
            "车": (255, 0, 0),
            "自行车": (0, 0, 255),
            "狗": (255, 255, 0),
            "猫": (255, 0, 255),
            "default": (0, 255, 255)
        }
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """调用大模型API分析图像
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            大模型返回的分析结果
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"无法读取图像: {image_path}")
        
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        image_base64 = base64.b64encode(buffer).decode("utf-8")
        
        try:
            client = OpenAI(
                api_key=self.api_key if self.api_key else "not-needed",
                base_url=self.model_api_url
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": self.prompt
                            }
                        ]
                    }
                ]
            )
            
            content = response.choices[0].message.content
            logging.info(f"API原始响应: {content}")
            
            # 清理markdown代码块标记
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # 修复AI可能返回的错误JSON格式
            # 1. 修复 confidence: 0:99 应该是 0.99 (冒号误写为小数点)
            import re
            content = re.sub(r'"confidence":\s*(\d+):(\d+)', r'"confidence": \1.\2', content)
            # 2. 修复其他可能的数字格式错误 (如 1:5 应该是 1.5)
            content = re.sub(r':\s*(\d+):(\d+)(?![\d\s]*\])', r': \1.\2', content)
            
            # 3. 修复截断的JSON（AI模型输出被截断）
            # 尝试直接解析，如果失败则修复截断问题
            try:
                result_json = json.loads(content)
            except json.JSONDecodeError:
                logging.warning("JSON解析失败，尝试修复截断的JSON...")
                
                # 策略1：如果以 '[' 开头但不以 ']' 结尾，说明是数组被截断
                if content.strip().startswith('[') and not content.strip().endswith(']'):
                    # 找到最后一个完整的对象结束位置
                    # 从后向前搜索 '}]' 或 '},' 模式
                    last_complete = -1
                    for i in range(len(content) - 2, 0, -1):
                        if content[i] == '}' and (i + 1 < len(content) and content[i+1] in [']', ',']):
                            last_complete = i + 1
                            break
                    
                    if last_complete > 0:
                        fixed_content = content[:last_complete] + ']'
                        logging.info(f"修复截断的JSON数组，原长度: {len(content)}, 修复后长度: {len(fixed_content)}")
                        content = fixed_content
                    else:
                        # 备用策略：找到最后一个完整的 '}' 位置
                        last_brace = content.rfind('}')
                        if last_brace > 0:
                            # 检查这个 '}' 后面是否有完整的 bbox 数组
                            preceding_text = content[:last_brace+1]
                            if '"bbox":' in preceding_text:
                                fixed_content = preceding_text + ']'
                                logging.info(f"备用策略修复JSON数组")
                                content = fixed_content
                            else:
                                raise ValueError("无法找到完整的JSON对象边界")
                        else:
                            raise ValueError("无法修复截断的JSON")
                
                # 再次尝试解析
                try:
                    result_json = json.loads(content)
                except json.JSONDecodeError as e2:
                    logging.error(f"修复后仍然无法解析: {str(e2)}")
                    raise
            
            logging.info(f"JSON解析成功，类型: {type(result_json)}")
            if isinstance(result_json, list):
                logging.info(f"数组长度: {len(result_json)}")
            elif isinstance(result_json, dict):
                logging.info(f"对象键: {list(result_json.keys())}")
            
            # 处理不同格式的响应
            if isinstance(result_json, list):
                # 如果直接返回数组，包装成标准格式
                logging.info("检测到数组格式，转换为标准格式")
                result_json = {"detections": result_json}
            elif isinstance(result_json, dict):
                # 如果返回对象但没有detections字段，尝试兼容处理
                if "detections" not in result_json:
                    logging.info("未找到detections字段，尝试其他字段名")
                    # 检查是否有其他常见字段名
                    for key in ["objects", "results", "predictions", "annotations"]:
                        if key in result_json and isinstance(result_json[key], list):
                            logging.info(f"找到替代字段: {key}")
                            result_json["detections"] = result_json[key]
                            break
                    else:
                        # 如果都没有，创建空数组
                        logging.warning("未找到任何检测数据字段")
                        result_json["detections"] = []
                elif not isinstance(result_json["detections"], list):
                    # 如果detections不是列表，转换为列表
                    logging.info("detections不是列表，转换为列表")
                    result_json["detections"] = [result_json["detections"]]
            else:
                # 其他类型，创建空结果
                logging.warning(f"未知的JSON类型: {type(result_json)}")
                result_json = {"detections": []}

            img_height, img_width = img.shape[:2]
            for det in result_json.get("detections", []):
                if isinstance(det, dict) and det.get("bbox") is not None:
                    det["bbox"] = list(normalize_bbox_to_pixels(det["bbox"], img_width, img_height))
            
            return result_json
        except json.JSONDecodeError as e:
            error_msg = f"无法解析模型返回的JSON: {content[:500]}..."  # 只显示前500字符
            logging.error(f"JSON解析错误: {str(e)}")
            logging.error(f"JSON内容预览: {content[:200]}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"分析图像失败: {str(e)}"
            logging.error(f"分析图像 {image_path} 失败: {e}")
            raise Exception(error_msg)
    
    def render_detections(self, image_path: str, detections: List[Dict[str, Any]]) -> str:
        """将检测结果渲染到图像上
        
        Args:
            image_path: 原始图像路径
            detections: 检测结果列表
            
        Returns:
            渲染后的图像路径
        """
        # 读取图像
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图像: {image_path}")

        img_height, img_width = image.shape[:2]
        
        # 渲染检测框和标签
        for detection in detections:
            # 解析检测结果
            if isinstance(detection, dict):
                label = detection.get("label", "unknown")
                confidence = detection.get("confidence", 0.0)
                bbox = detection.get("bbox", [0, 0, 0, 0])
            else:
                continue
            
            x1, y1, x2, y2 = normalize_bbox_to_pixels(bbox, img_width, img_height)
            
            # 获取颜色
            color = self.colors.get(label, self.colors["default"])
            
            # 绘制检测框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签和置信度（支持中文）
            label_text = f"{label}: {confidence:.2f}"
            
            # 尝试使用PIL库渲染中文
            try:
                from PIL import Image, ImageDraw, ImageFont
                import numpy as np
                
                # 转换为PIL图像
                img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(img_pil)
                
                # 加载默认中文字体或指定字体文件
                try:
                    # 尝试使用系统默认中文字体
                    font = ImageFont.truetype("simhei.ttf", 16)
                except IOError:
                    # 如果没有找到，使用PIL默认字体
                    font = ImageFont.load_default()
                
                # 绘制文本
                text_x = x1
                text_y = y1 - 20 if y1 > 20 else y1 + 20
                draw.text((text_x, text_y), label_text, font=font, fill=tuple(color[::-1]))
                
                # 转换回OpenCV图像
                image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            except Exception as e:
                # 如果PIL渲染失败，使用OpenCV默认渲染（可能会有乱码）
                logging.warning(f"中文渲染失败，使用默认渲染: {e}")
                cv2.putText(image, label_text, (x1, y1 - 10 if y1 > 10 else y1 + 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 保存渲染后的图像
        import os
        base_name, ext = os.path.splitext(image_path)
        rendered_path = f"{base_name}_labeled{ext}"
        cv2.imwrite(rendered_path, image)
        return rendered_path
    
    def process_video(self, video_path: str, output_dir: str, frame_interval: int = 1, save_rendered: bool = True):
        """处理视频完整流程，支持本地视频和RTSP流
        
        Args:
            video_path: 视频文件路径或RTSP流地址
            output_dir: 输出目录
            frame_interval: 抽帧间隔
            save_rendered: 是否保存渲染后的帧
        """
        # 记录开始时间
        start_time = datetime.now()
        logging.info(f"🚀 开始处理视频流: {video_path}")
        logging.info(f"📁 输出目录: {output_dir}")
        logging.info(f"⏱️  抽帧间隔: {frame_interval}")
        logging.info(f"📅 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 创建输出目录
        raw_frames_dir = os.path.join(output_dir, "raw_frames")
        labeled_frames_dir = os.path.join(output_dir, "labeled_frames")
        os.makedirs(raw_frames_dir, exist_ok=True)
        if save_rendered:
            os.makedirs(labeled_frames_dir, exist_ok=True)
        
        logging.info(f"📁 原始帧目录: {raw_frames_dir}")
        if save_rendered:
            logging.info(f"📁 渲染帧目录: {labeled_frames_dir}")
        
        # 初始化变量
        cap = None
        frame_count = 0
        processed_count = 0
        is_rtsp = video_path.lower().startswith("rtsp://")
        max_reconnect_attempts = 50  # 最大重连次数，0表示无限重试
        reconnect_delay = 5  # 重连延迟（秒）
        reconnect_count = 0
        last_status_time = datetime.now()  # 上次输出状态的时间
        status_interval = 60  # 状态输出间隔（秒）
        
        try:
            while True:
                try:
                    # 检查是否需要打开或重新打开视频流
                    if cap is None or not cap.isOpened():
                        if reconnect_count > 0:
                            logging.info(f"🔄 尝试重新连接 RTSP 流... (尝试 {reconnect_count}/{max_reconnect_attempts if max_reconnect_attempts > 0 else '无限'})")
                        else:
                            logging.info(f"📡 打开视频流: {video_path}")
                        
                        # 打开视频或RTSP流
                        cap = cv2.VideoCapture(video_path)
                        if not cap.isOpened():
                            raise ValueError(f"无法打开视频流: {video_path}")
                        
                        if reconnect_count > 0:
                            logging.info("✅ RTSP 流重新连接成功")
                            reconnect_count = 0  # 重置重连计数
                    
                    # 读取一帧
                    cap.grab()  # 只抓取帧，不解码，提高响应速度
                    ret, frame = cap.retrieve()  # 解码帧
                    
                    if not ret:
                        if is_rtsp:
                            # RTSP流中断，尝试重连
                            logging.info(f"⚠️  RTSP 流中断，{reconnect_delay}秒后尝试重连...")
                            
                            # 关闭当前视频流
                            if cap is not None:
                                cap.release()
                                cap = None
                            
                            # 增加重连计数
                            reconnect_count += 1
                            
                            # 检查是否达到最大重连次数
                            if max_reconnect_attempts > 0 and reconnect_count > max_reconnect_attempts:
                                logging.error(f"❌ 达到最大重连次数 ({max_reconnect_attempts})，停止重连")
                                break
                            
                            # 等待重连延迟
                            time.sleep(reconnect_delay)
                            continue  # 跳过当前循环，尝试重新连接
                        else:
                            # 本地视频文件结束
                            logging.info("✅ 视频流读取完成")
                            break
                    
                    # 按照指定间隔处理帧
                    if frame_count % frame_interval == 0:
                        logging.info(f"🔄 处理帧 #{frame_count}")
                        
                        # 定义统一的文件名
                        frame_filename = f"frame_{frame_count:06d}.jpg"
                        
                        # 保存临时帧用于处理
                        temp_frame_path = f"temp_{frame_filename}"
                        cv2.imwrite(temp_frame_path, frame)
                        
                        try:
                            # 分析图像（同步处理，阻塞等待结果）
                            result = self.analyze_image(temp_frame_path)
                            
                            # 解析检测结果
                            detections = result.get("detections", [])
                            if isinstance(detections, dict):
                                detections = [detections]
                            
                            # 仅当检测到至少一个目标时，才保存图片
                            if detections and len(detections) > 0:
                                logging.info(f"✅ 检测到 {len(detections)} 个目标")
                                
                                # 保存原始未渲染帧
                                raw_frame_path = os.path.join(raw_frames_dir, frame_filename)
                                cv2.imwrite(raw_frame_path, frame)
                                logging.info(f"✅ 已保存原始帧: {raw_frame_path}")
                                
                                # 保存渲染后的帧
                                if save_rendered:
                                    # 渲染检测结果
                                    rendered_path = self.render_detections(temp_frame_path, detections)
                                    
                                    # 移动渲染后的帧到最终目录，保持与原始帧相同的文件名
                                    final_path = os.path.join(labeled_frames_dir, frame_filename)
                                    os.rename(rendered_path, final_path)
                                    logging.info(f"✅ 已保存标注帧: {final_path}")
                                
                                processed_count += 1
                            else:
                                logging.info(f"ℹ️  未检测到目标，跳过保存")
                        except KeyboardInterrupt:
                            logging.info("\n⚠️  用户中断处理")
                            # 删除未处理完的临时文件
                            if os.path.exists(temp_frame_path):
                                os.remove(temp_frame_path)
                            raise  # 重新抛出异常，让外层处理
                        
                        # 删除临时文件
                        if os.path.exists(temp_frame_path):
                            os.remove(temp_frame_path)
                    
                    frame_count += 1
                    
                    # 定期输出状态信息
                    current_time = datetime.now()
                    if (current_time - last_status_time).total_seconds() >= status_interval:
                        # 计算运行时长
                        elapsed = current_time - start_time
                        # 计算处理速度
                        fps = processed_count / elapsed.total_seconds() if elapsed.total_seconds() > 0 else 0
                        
                        logging.info(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] "
                              f"运行时长: {str(elapsed).split('.')[0]} | "
                              f"总帧数: {frame_count} | "
                              f"已处理: {processed_count}帧 | "
                              f"处理速度: {fps:.2f}帧/秒")
                        last_status_time = current_time
                    
                    # 短暂休眠，提高中断响应速度
                    time.sleep(0.001)
                    
                except KeyboardInterrupt:
                    logging.info("\n⚠️  用户中断处理")
                    raise  # 重新抛出异常，让外层处理
                except Exception as e:
                    if is_rtsp:
                        # RTSP流出现异常，尝试重连
                        logging.warning(f"⚠️  RTSP 流异常: {e}，{reconnect_delay}秒后尝试重连...")
                        
                        # 关闭当前视频流
                        if cap is not None:
                            cap.release()
                            cap = None
                        
                        # 增加重连计数
                        reconnect_count += 1
                        
                        # 检查是否达到最大重连次数
                        if max_reconnect_attempts > 0 and reconnect_count > max_reconnect_attempts:
                            logging.error(f"❌ 达到最大重连次数 ({max_reconnect_attempts})，停止重连")
                            raise
                        
                        # 等待重连延迟
                        time.sleep(reconnect_delay)
                        continue  # 跳过当前循环，尝试重新连接
                    else:
                        # 本地视频文件异常，直接抛出
                        raise
        
        except KeyboardInterrupt:
            logging.info("\n🛑 正在停止处理...")
        except Exception as e:
            logging.error(f"❌ 处理异常: {e}")
        finally:
            # 确保视频流被释放
            if cap is not None and cap.isOpened():
                cap.release()
                logging.info("✅ 视频流已释放")
        
        # 计算结束时间和总运行时长
        end_time = datetime.now()
        total_elapsed = end_time - start_time
        
        logging.info(f"\n" + "=" * 60)
        logging.info(f"📊 完整处理统计:")
        logging.info(f"📅 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"📅 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"⏱️  总运行时长: {str(total_elapsed).split('.')[0]}")
        logging.info(f"📈 总帧数: {frame_count}")
        logging.info(f"✅ 已处理: {processed_count}帧")
        logging.info(f"📊 处理比例: {processed_count / frame_count * 100:.1f}%" if frame_count > 0 else "📊 处理比例: 0%")
        logging.info(f"⚡ 平均速度: {processed_count / total_elapsed.total_seconds():.2f}帧/秒" if total_elapsed.total_seconds() > 0 else "⚡ 平均速度: 0帧/秒")
        logging.info(f"📁 输出目录: {output_dir}")
        logging.info("=" * 60)
        logging.info("✅ 处理已停止")
