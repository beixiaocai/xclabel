import cv2
import os
import requests
import json
from datetime import datetime, timedelta
import argparse
from typing import List, Dict, Any
import time
import logging
from logging.handlers import RotatingFileHandler

# 配置logging
from datetime import datetime
# 生成带时间戳的日志文件名
log_filename = f"auto_label_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # 输出到控制台
        logging.StreamHandler(),
        # 输出到文件，按大小滚动，最大10MB，保留5个备份
        RotatingFileHandler(
            log_filename,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

# 记录日志文件名
logging.info(f"📄 日志文件: {log_filename}")

class AutoLabeler:
    def __init__(self, model_api_url: str, api_key: str = None, prompt: str = None, timeout: int = 30):
        """初始化自动标注器
        
        Args:
            model_api_url: 大模型API地址
            api_key: API密钥（如果需要）
            prompt: 自定义提示词
            timeout: HTTP请求超时时间（秒）
        """
        self.model_api_url = model_api_url
        self.api_key = api_key
        self.session = requests.Session()
        # 设置默认超时时间
        self.timeout = timeout
        # 默认提示词
        self.default_prompt = "检测图中物体，返回JSON：{\"detections\":[{\"label\":\"类别\",\"confidence\":0.9,\"bbox\":[x1,y1,x2,y2]}]}"
        # 使用用户自定义提示词或默认提示词
        self.prompt = prompt if prompt else self.default_prompt
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """调用LMStudio的qwen3-vl-8b模型API分析图像
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            大模型返回的分析结果
        """
        import base64
        
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # 确保API地址以正确的端点结尾
        api_endpoint = self.model_api_url
        # 如果API地址以/v1结尾，添加/chat/completions端点
        if api_endpoint.endswith("/v1"):
            api_endpoint = f"{api_endpoint}/chat/completions"
        # 如果API地址是根路径，添加完整端点
        elif not api_endpoint.endswith("/chat/completions"):
            api_endpoint = f"{api_endpoint.rstrip('/')}/v1/chat/completions"
        
        # 读取图像并压缩，减少base64编码后的大小
        import cv2
        import numpy as np
        
        # 读取图像
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"无法读取图像: {image_path}")
        
        # 压缩图像（调整大小）
        max_size = 640  # 最大边长
        h, w = img.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 转换为JPEG格式，降低质量
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        image_base64 = base64.b64encode(buffer).decode("utf-8")
        
        # 构建LMStudio兼容的请求体
        payload = {
            "model": "qwen/qwen3-vl-8b",
            "messages": [
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
            ],
            "temperature": 0.0,
            "response_format": {
                "type": "text"
            }
        }
        
        # 发送请求
        try:
            response = self.session.post(api_endpoint, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            
            # 解析LMStudio返回的结果
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                # 尝试解析JSON内容
                try:
                    # 去除Markdown格式标记
                    if content.startswith('```json'):
                        content = content[7:]  # 移除开头的```json
                    if content.endswith('```'):
                        content = content[:-3]  # 移除结尾的```
                    content = content.strip()  # 去除首尾空白
                    
                    return json.loads(content)
                except json.JSONDecodeError:
                    logging.error(f"无法解析模型返回的JSON: {content}")
                    return {"detections": []}
            return {"detections": []}
        except Exception as e:
            logging.error(f"分析图像 {image_path} 失败: {e}")
            logging.error(f"使用的API端点: {api_endpoint}")
            return {"detections": []}
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        import glob
        try:
            # 清理所有临时帧文件
            temp_files = glob.glob("frame_*.jpg")
            if temp_files:
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                logging.info(f"✅ 清理了 {len(temp_files)} 个临时文件")
        except Exception as e:
            logging.error(f"❌ 清理临时文件失败: {e}")
    
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
        
        # 定义颜色映射（不同类别使用不同颜色）
        colors = {
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
        
        # 渲染检测框和标签
        for detection in detections:
            # 解析检测结果
            label = detection.get("label", "unknown")
            confidence = detection.get("confidence", 0.0)
            bbox = detection.get("bbox", [0, 0, 0, 0])
            
            # 转换为整数坐标
            x1, y1, x2, y2 = map(int, bbox)
            
            # 获取颜色
            color = colors.get(label, colors["default"])
            
            # 绘制检测框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签和置信度（支持中文）
            label_text = f"{label}: {confidence:.2f}"
            
            # 使用PIL库渲染中文
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
                print(f"中文渲染失败，使用默认渲染: {e}")
                cv2.putText(image, label_text, (x1, y1 - 10 if y1 > 10 else y1 + 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 保存渲染后的图像
        rendered_path = image_path.replace(".jpg", "_labeled.jpg")
        cv2.imwrite(rendered_path, image)
        return rendered_path
    
    def process_video(self, video_path: str, output_dir: str, frame_interval: int = 1):
        """处理视频完整流程，支持本地视频和RTSP流，同步处理模式
        
        Args:
            video_path: 视频文件路径或RTSP流地址
            output_dir: 输出目录
            frame_interval: 抽帧间隔
        """
        # 记录开始时间
        start_time = datetime.now()
        logging.info(f"🚀 开始处理视频流: {video_path}")
        logging.info(f"📁 输出目录: {output_dir}")
        logging.info(f"⏱️  抽帧间隔: {frame_interval}")
        logging.info(f"📅 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("💡 提示: 按 Ctrl+C 可随时中断处理")
        logging.info("=" * 60)
        
        # 创建两个输出目录：一个保存原始未渲染帧，一个保存渲染后的帧
        raw_frames_dir = os.path.join(output_dir, "raw_frames")
        labeled_frames_dir = os.path.join(output_dir, "labeled_frames")
        os.makedirs(raw_frames_dir, exist_ok=True)
        os.makedirs(labeled_frames_dir, exist_ok=True)
        logging.info(f"📁 原始帧目录: {raw_frames_dir}")
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
                                
                                # 保存原始未渲染帧到raw_frames目录
                                raw_frame_path = os.path.join(raw_frames_dir, frame_filename)
                                cv2.imwrite(raw_frame_path, frame)
                                logging.info(f"✅ 已保存原始帧: {raw_frame_path}")
                                
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
            
            # 清理所有临时文件
            self._cleanup_temp_files()
        
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
        logging.info(f"📁 输出目录: {labeled_frames_dir}")
        logging.info("=" * 60)
        logging.info("✅ 处理已停止")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="自动视频标注工具 - 适配LMStudio qwen3-vl-8b模型")
    parser.add_argument("--video", required=True, help="输入视频文件路径或RTSP流地址")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--interval", type=int, default=1, help="抽帧间隔")
    parser.add_argument("--model-api", default="http://192.168.1.105:1234/v1", help="大模型API地址，默认适配LMStudio: http://192.168.1.105:1234")
    parser.add_argument("--api-key", help="API密钥")
    parser.add_argument("--prompt", help="自定义提示词，用于指导大模型检测物体")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP请求超时时间（秒），默认30秒")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # 记录使用的配置
    if args.prompt:
        logging.info(f"📝 使用自定义提示词: {args.prompt}")
    else:
        logging.info(f"📝 使用默认提示词")
    logging.info(f"⏱️  HTTP请求超时时间: {args.timeout} 秒")
    
    # 创建自动标注器
    labeler = AutoLabeler(args.model_api, args.api_key, args.prompt, args.timeout)
    
    # 处理视频
    labeler.process_video(args.video, args.output, args.interval)
