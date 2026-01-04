## xclabel
* 作者：北小菜 
* 作者主页：https://www.yuturuishi.com
* gitee开源地址：https://gitee.com/Vanishi/xclabel
* github开源地址：https://github.com/beixiaocai/xclabel

### 软件介绍
- xclabel是一款功能强大的开源图像标注工具，支持样本导入、标注、自动标注、数据集导出和YOLO11模型管理
- 采用Python+Flask开发，跨平台支持Windows/Linux/Mac，可通过源码运行或直接运行打包后的exe文件
- 支持多种标注类型，包括矩形、多边形等
- 支持导入图片文件夹、视频文件、LabelMe格式数据集
- 支持RTSP流处理，可直接对网络摄像头流进行标注
- 支持自动标注功能，可对图片和视频进行AI自动标注
- 支持导出YOLO格式数据集，可自定义训练/验证/测试比例
- 集成YOLO11模型管理，支持安装、卸载和预训练模型下载
- 内置文件管理系统，支持文件浏览、上传、下载、删除、新建文件夹等操作
- 支持命令行参数配置，可通过--host和--port指定IP和端口
- 简洁直观的用户界面，易于使用

### 软件截图
<img width="720" alt="1" src="https://gitee.com/Vanishi/images/raw/master/xclabel/v2.1/1.png">
<img width="720" alt="2" src="https://gitee.com/Vanishi/images/raw/master/xclabel/v2.1/2.png">
<img width="720" alt="3" src="https://gitee.com/Vanishi/images/raw/master/xclabel/v2.1/3.png">

### 版本历史

查看完整的版本更新记录，请参考 [CHANGELOG.md](CHANGELOG.md)

### 主要功能
1. **图像标注**：支持矩形、多边形等多种标注类型
2. **数据集管理**：
   - 支持图像、视频、LabelMe数据集导入
   - 视频抽帧时使用视频文件名作为前缀，便于管理
3. **自动标注**：
   - 支持多种推理工具（LMStudio、vLLM、ollama）
   - 新增支持阿里云大模型自动标注
   - 支持图片和视频的AI自动标注
4. **API配置管理**：支持保存和加载API配置参数
5. **标注导出**：支持YOLO格式数据集导出，可自定义训练/验证/测试比例
6. **标签管理**：支持添加、编辑、删除标签，自定义标签颜色
7. **YOLO11集成**：
   - 自动安装和卸载YOLO11
   - 支持预训练模型下载和管理
   - 手动拖放模型文件支持
   - CUDA支持自动检测
8. **文件管理系统**：
   - 支持文件系统导航和路径浏览
   - 支持图片预览和放大查看
   - 支持文件选择、全选、批量下载和删除
   - 支持新建文件夹和文件上传
9. **RTSP流处理**：支持直接对网络摄像头流进行标注
10. **快捷键支持**：提高标注效率
11. **实时保存**：标注数据实时保存，避免数据丢失

### 使用说明
1. **安装依赖**：
   ```bash
   # 创建虚拟环境
   python -m venv venv
   
   # 激活虚拟环境
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   
   # 安装依赖
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple 
   
   # 如需打包，打包方式一（不推荐，打包的程序不包含静态资源，进入dist文件，需要拷贝静态资源进去）
   pyinstaller -F app.py
   
   # 如需打包，打包方式二（强烈推荐，打包的程序包含静态资源，进入dist文件，直接启动xclabel.exe）
   pyinstaller app.spec
   
   
   ```

2. **启动服务**：
   ```bash
   python app.py --host 0.0.0.0 --port 9924
   
   ```

3. **访问服务**：
   在浏览器输入 http://127.0.0.1:5000 即可开始使用

4. **YOLO11管理**：
   - 点击右上角"设置"按钮打开设置弹框
   - 在YOLO11安装部分，点击"安装YOLO11"按钮进行安装
   - 选择要下载的预训练模型，点击"下载选中模型"
   - 可以手动拖放模型文件到指定区域进行安装
   - 点击"卸载YOLO11"按钮彻底卸载YOLO11

### 项目结构
```
xclabel/
├── app.py                    # 主应用文件
├── templates/
│   └── index.html            # 主页面模板
├── static/
│   ├── style.css             # 样式文件
│   ├── script.js             # 脚本文件
│   ├── all.min.css           # Font Awesome图标库
│   └── annotations/          # 标注数据存储目录
├── uploads/                  # 上传的图片和视频存储目录
├── plugins/                  # 插件目录（用于YOLO11安装）
├── requirements.txt          # 依赖列表
└── README.md                 # 项目说明文档
```

### 标注流程
1. **添加数据集**：点击右上角"添加数据集"按钮，选择要标注的图片、视频或LabelMe数据集
2. **创建标签**：在右侧标签管理中添加需要的标签，设置颜色
3. **开始标注**：选择左侧图片列表中的图片，使用左侧工具进行标注
4. **导出数据集**：标注完成后，点击右上角"导出数据集"按钮，选择导出格式和参数

### YOLO11使用流程
1. **安装YOLO11**：在设置弹框中点击"安装YOLO11"按钮
2. **下载预训练模型**：选择要下载的模型，点击"下载选中模型"
3. **手动添加模型**：将模型文件拖放到指定区域
4. **使用模型**：安装完成后，可用于模型推理和训练
5. **卸载YOLO11**：点击"卸载YOLO11"按钮彻底删除

### 快捷键说明
- **Ctrl+S**：保存标注
- **Ctrl+Shift+D**：清除标注

### 技术栈
- **后端**：Flask
- **前端**：HTML, CSS, JavaScript
- **数据库**：JSON文件存储
- **图像处理**：OpenCV, PIL
- **YOLO11集成**：Ultralytics YOLO11

### 调用示例

#### 示例1：调用阿里云大模型进行图像分析

```python
from AiUtils import AIAutoLabeler

# 初始化AIAutoLabeler实例
api_key = "your_aliyun_api_key"  # 替换为您的阿里云API密钥
model = "qwen-vl-max"  # 替换为您要使用的阿里云模型名称

# 创建自动标注器实例
labeler = AIAutoLabeler(
    model_api_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=api_key,
    inference_tool="阿里云大模型",
    model=model,
    prompt="检测图中物体，返回JSON：{\"detections\":[{\"label\":\"类别\",\"confidence\":0.9,\"bbox\":[x1,y1,x2,y2]}]}"
)

# 分析图像
image_path = "test.jpg"  # 替换为您的图像路径
result = labeler.analyze_image(image_path)

# 解析结果
detections = result.get("detections", [])
print(f"检测到 {len(detections)} 个目标：")
for i, detection in enumerate(detections):
    label = detection.get("label", "unknown")
    confidence = detection.get("confidence", 0.0)
    bbox = detection.get("bbox", [])
    print(f"目标 {i+1}: {label} (置信度: {confidence:.2f})，位置: {bbox}")
```

#### 示例2：调用LMStudio进行图像分析

```python
from AiUtils import AIAutoLabeler

# 初始化AIAutoLabeler实例
lmstudio_url = "http://localhost:1234/v1"  # LMStudio的API地址
model = "qwen/qwen3-vl-8b"  # LMStudio中运行的模型名称

# 创建自动标注器实例
labeler = AIAutoLabeler(
    model_api_url=lmstudio_url,
    inference_tool="LMStudio",
    model=model,
    prompt="检测图中物体，返回JSON：{\"detections\":[{\"label\":\"类别\",\"confidence\":0.9,\"bbox\":[x1,y1,x2,y2]}]}"
)

# 分析图像
image_path = "test.jpg"  # 替换为您的图像路径
result = labeler.analyze_image(image_path)

# 解析结果
detections = result.get("detections", [])
print(f"检测到 {len(detections)} 个目标：")
for i, detection in enumerate(detections):
    label = detection.get("label", "unknown")
    confidence = detection.get("confidence", 0.0)
    bbox = detection.get("bbox", [])
    print(f"目标 {i+1}: {label} (置信度: {confidence:.2f})，位置: {bbox}")
```

### 授权协议
- 本项目自有代码使用宽松的MIT协议，在保留版权信息的情况下可以自由应用于各自商用、非商业的项目。
- 本项目使用了一些第三方库，使用本项目时请遵循相应第三方库的授权协议。
- 由于使用本项目而产生的商业纠纷或侵权行为一概与本项目及开发者无关，请自行承担法律风险。

