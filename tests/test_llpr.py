#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperLPR车牌识别API测试脚本
"""

import argparse
import base64
import json
import requests
import os

def encode_image_to_base64(image_path):
    """
    将图片文件编码为base64字符串
    """
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        base64_str = base64.b64encode(image_data).decode("utf-8")
        return base64_str
    except Exception as e:
        print(f"[错误] 图片编码失败: {e}")
        return None

def test_hyperlpr_api(image_path, api_url):
    """
    测试HyperLPR API
    """
    # 检查图片文件是否存在
    if not os.path.exists(image_path):
        print(f"[错误] 图片文件不存在: {image_path}")
        return False
    
    # 检查图片格式
    valid_extensions = [".jpg", ".jpeg", ".png", ".bmp"]
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in valid_extensions:
        print(f"[错误] 不支持的图片格式: {ext}，仅支持{valid_extensions}")
        return False
    
    # 编码图片
    base64_image = encode_image_to_base64(image_path)
    if not base64_image:
        return False
    
    # 构建请求数据 - 尝试多种格式
    payload_formats = [
        # 格式1: FormData格式（API需要file字段）
        {
            "data": {
                "file": (os.path.basename(image_path), open(image_path, "rb"), "image/jpeg")
            },
            "headers": {}
        },
        # 格式2: FormData格式（使用不同的文件描述）
        {
            "data": {
                "file": open(image_path, "rb")
            },
            "headers": {}
        }
    ]
    
    try:
        print(f"[信息] 正在调用API: {api_url}")
        print(f"[信息] 处理图片: {image_path}")
        
        # 尝试多种请求格式
        for i, payload_format in enumerate(payload_formats):
            print(f"\n[尝试] 格式 {i+1}: {payload_format['headers'].get('Content-Type', 'multipart/form-data')}")
            
            try:
                # 根据Content-Type选择发送方式
                if payload_format['headers'].get('Content-Type') == 'application/json':
                    # JSON格式请求
                    response = requests.post(
                        api_url, 
                        json=payload_format['data'], 
                        headers=payload_format['headers'], 
                        timeout=30
                    )
                else:
                    # FormData格式请求
                    response = requests.post(
                        api_url, 
                        files=payload_format['data'], 
                        headers=payload_format['headers'], 
                        timeout=30
                    )
                
                # 关闭可能打开的文件
                if 'image' in payload_format['data'] and hasattr(payload_format['data']['image'], 'close'):
                    payload_format['data']['image'].close()
                
                # 检查响应状态码
                if response.status_code == 200:
                    # 解析响应
                    try:
                        result = response.json()
                        # 输出结果
                        print(f"\n[成功] 格式 {i+1} 请求成功!")
                        print("[成功] API响应结果:")
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                        return True
                    except json.JSONDecodeError as e:
                        print(f"[警告] 格式 {i+1} JSON解析失败: {e}")
                        print(f"[警告] 原始响应: {response.text}")
                        continue
                else:
                    print(f"[警告] 格式 {i+1} 请求失败，状态码: {response.status_code}")
                    print(f"[警告] 响应内容: {response.text}")
                    continue
            except requests.exceptions.RequestException as e:
                print(f"[警告] 格式 {i+1} 请求异常: {e}")
                # 关闭可能打开的文件
                if 'image' in payload_format['data'] and hasattr(payload_format['data']['image'], 'close'):
                    payload_format['data']['image'].close()
                continue
        
        # 所有格式都尝试失败
        print(f"\n[错误] 所有请求格式均失败，请检查API文档或联系服务提供者")
        return False
        
    except Exception as e:
        print(f"[错误] 未知错误: {e}")
        # 确保关闭所有可能打开的文件
        for payload_format in payload_formats:
            if 'image' in payload_format['data'] and hasattr(payload_format['data']['image'], 'close'):
                payload_format['data']['image'].close()
        return False

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="HyperLPR车牌识别API测试脚本")
    parser.add_argument("--image", type=str, required=True, help="待识别的图片路径")
    parser.add_argument("--api-url", type=str, default="http://192.168.1.13:9925/api/v1/rec", 
                        help="HyperLPR API地址，默认: http://192.168.1.13:9925/api/v1/rec")
    
    args = parser.parse_args()
    
    return test_hyperlpr_api(args.image, args.api_url)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
