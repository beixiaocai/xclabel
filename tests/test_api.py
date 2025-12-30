import requests
import json
import base64
import argparse

def test_lmstudio_api(image_path, model_api, api_key=None):
    """测试LMStudio API调用是否正确
    
    Args:
        image_path: 测试图片路径
        model_api: API地址
        api_key: API密钥
        
    Returns:
        bool: API调用是否成功
        dict: 解析后的检测结果
    """
    print(f"测试图片: {image_path}")
    print(f"API地址: {model_api}")
    
    # 构建请求头
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # 确保API地址以正确的端点结尾
    api_endpoint = model_api
    if api_endpoint.endswith("/v1"):
        api_endpoint = f"{api_endpoint}/chat/completions"
    elif not api_endpoint.endswith("/chat/completions"):
        api_endpoint = f"{api_endpoint.rstrip('/')}/v1/chat/completions"
    
    print(f"使用的API端点: {api_endpoint}")
    
    # 读取图像并压缩，减少base64编码后的大小
    try:
        import cv2
        import numpy as np
        
        # 读取图像
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("无法读取图像")
        
        # 压缩图像（调整大小）
        max_size = 640  # 最大边长
        h, w = img.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            print(f"✅ 图像已压缩，新尺寸: {new_w}x{new_h}")
        else:
            print(f"✅ 图像尺寸合适: {w}x{h}")
        
        # 转换为JPEG格式，降低质量
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        image_base64 = base64.b64encode(buffer).decode("utf-8")
        print(f"✅ 图像编码成功，base64大小: {len(image_base64) // 1024} KB")
    except Exception as e:
        print(f"❌ 图像处理失败: {e}")
        return False, {}
    
    # 构建请求体（简化提示词，减少token数量）
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
                        "text": "检测图中物体，返回JSON：{\"detections\":[{\"label\":\"类别\",\"confidence\":0.9,\"bbox\":[x1,y1,x2,y2]}]}"
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
        print("📤 发送API请求...")
        response = requests.post(api_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ API请求成功，状态码: {response.status_code}")
        
        # 解析响应
        result = response.json()
        print("📥 API响应:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 提取检测结果
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            print(f"\n📝 模型返回内容:")
            print(content)
            
            # 解析JSON内容
            try:
                # 去除Markdown格式标记
                if content.startswith('```json'):
                    content = content[7:]  # 移除开头的```json
                if content.endswith('```'):
                    content = content[:-3]  # 移除结尾的```
                content = content.strip()  # 去除首尾空白
                
                detection_result = json.loads(content)
                print("✅ 模型返回内容解析成功")
                
                # 验证检测结果格式
                if "detections" in detection_result:
                    detections = detection_result["detections"]
                    print(f"🔍 检测到 {len(detections)} 个目标")
                    
                    # 验证每个检测结果的格式
                    valid_detections = []
                    for i, det in enumerate(detections):
                        if isinstance(det, dict) and all(key in det for key in ["label", "confidence", "bbox"]):
                            # 验证坐标格式
                            bbox = det["bbox"]
                            if isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(coord, (int, float)) for coord in bbox):
                                valid_detections.append(det)
                                print(f"   🎯 目标 {i+1}: {det['label']} (置信度: {det['confidence']:.2f})，坐标: {bbox}")
                            else:
                                print(f"   ❌ 目标 {i+1} 坐标格式无效: {bbox}")
                        else:
                            print(f"   ❌ 目标 {i+1} 格式无效: {det}")
                    
                    if valid_detections:
                        print(f"\n✅ 共 {len(valid_detections)} 个有效检测结果")
                        return True, {"detections": valid_detections}
                    else:
                        print("\n❌ 没有有效检测结果")
                        return False, detection_result
                else:
                    print("❌ 模型返回内容缺少'detections'字段")
                    return False, detection_result
            except json.JSONDecodeError as e:
                print(f"❌ 模型返回内容不是有效的JSON: {e}")
                print(f"   处理后的内容: {content[:100]}...")
                return False, {}
        else:
            print("❌ API响应缺少'choices'字段")
            return False, result
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API请求失败: {e}")
        print(f"   状态码: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
        if hasattr(e, 'response'):
            try:
                error_details = e.response.json()
                print(f"   错误详情: {json.dumps(error_details, indent=2)}")
            except:
                print(f"   错误响应: {e.response.text}")
        return False, {}
    except Exception as e:
        print(f"❌ 测试过程中发生未知错误: {e}")
        return False, {}

def parse_args():
    parser = argparse.ArgumentParser(description="测试LMStudio API调用")
    parser.add_argument("--image", required=True, help="测试图片路径")
    parser.add_argument("--model-api", default="http://192.168.1.105:1234", help="大模型API地址")
    parser.add_argument("--api-key", help="API密钥")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    print("=" * 60)
    print("LMStudio API 测试工具")
    print("=" * 60)
    
    success, result = test_lmstudio_api(args.image, args.model_api, args.api_key)
    
    print("=" * 60)
    if success:
        print("🎉 测试成功！API能够正确检测图片中的目标并返回坐标")
    else:
        print("💥 测试失败！请检查API配置或模型状态")
    print("=" * 60)
