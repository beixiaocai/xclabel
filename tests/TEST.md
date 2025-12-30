
# 测试脚本集合

## 1. 测试API连接
测试与大模型API的连接是否正常
```bash
python tests/test_api.py --image tests/bus.jpg --model-api http://192.168.1.105:1234/v1
```

## 2. 自动标注图片（单张）
对单张图片进行目标检测和标注
```bash
python tests/test_api.py --image tests/bus.jpg --model-api http://192.168.1.105:1234/v1
```

## 3. 处理视频 - 生成标注帧
对视频进行抽帧、检测和标注，保存原始帧和标注帧
```bash
# 本地视频处理
python tests/auto_label.py --video tests/test13.mp4 --output tests/test13 --interval 20 --timeout 60

# RTSP流处理（示例）
python tests/auto_label.py --video rtsp://example.com/stream --output tests/rtsp_output --interval 10 --timeout 30
```

## 4. 处理视频 - 生成检测视频片段
对视频进行抽帧检测，当检测到目标时，生成前后1秒的干净原视频片段
```bash
# 本地视频处理
python tests/auto_label_video.py --video tests/test13.mp4 --output tests/test13_video --interval 10 --timeout 60

# RTSP流处理（示例）
python tests/auto_label_video.py --video rtsp://example.com/stream --output tests/rtsp_video_output --interval 5 --timeout 30
```

## 5. 自定义参数说明
- `--video`：视频文件路径或RTSP流地址
- `--output`：输出目录路径
- `--interval`：抽帧间隔（帧数）
- `--model-api`：大模型API地址
- `--api-key`：API密钥（如果需要）
- `--prompt`：自定义提示词
- `--timeout`：HTTP请求超时时间（秒）

## 6. 日志文件
所有脚本运行时都会生成带时间戳的日志文件，便于后续查询和分析

## 7. 输出目录结构

### auto_label.py 输出结构
```
output_dir/
├── raw_frames/      # 原始未渲染帧
│   ├── frame_000000.jpg
│   ├── frame_000020.jpg
│   └── ...
└── labeled_frames/  # 带有标注的帧
    ├── frame_000000.jpg
    ├── frame_000020.jpg
    └── ...
```

### auto_label_video.py 输出结构
```
output_dir/
└── videos/          # 合成的视频片段
    ├── video_000000.mp4
    ├── video_000020.mp4
    └── ...
```