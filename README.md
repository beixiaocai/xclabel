## xclabel
* 作者：北小菜 
* 作者主页：https://www.yuturuishi.com
* gitee开源地址：https://gitee.com/Vanishi/xclabel
* github开源地址：https://github.com/beixiaocai/xclabel

### 软件介绍
- xclabel是一款功能强大的开源图像标注工具，支持样本导入、标注、AI自动标注、数据集导出和YOLO11模型管理
- 采用Python+Flask开发，跨平台支持Windows/Linux/Mac，可通过源码运行或直接运行打包后的exe文件
- 支持多种标注类型，包括矩形、多边形等
- 支持导入图片文件夹、视频文件、LabelMe格式数据集
- 支持RTSP流处理，可直接对网络摄像头流进行标注
- 支持AI自动标注功能，可对图片和视频进行大模型自动标注
- 支持导出YOLO格式数据集，可自定义训练/验证/测试比例
- 集成YOLO11模型管理，支持安装、卸载和预训练模型下载
- 内置文件管理系统，支持文件浏览、上传、下载、删除、新建文件夹等操作
- 支持命令行参数配置，可通过--host和--port指定IP和端口
- 简洁直观的用户界面，易于使用
- 支持左侧侧边栏宽度保存功能，提升用户体验
- 实现AI标注进度显示，包括已执行数量、总量、总耗时和进度条

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
3. **AI自动标注**：
   - 支持多种推理工具（LMStudio、vLLM、ollama、阿里云大模型）
   - 支持图片和视频的AI自动标注
   - 实现AI标注弹框，包含API配置、提示词输入和标签选择
   - 支持显示标注进度，包括已执行数量、总量、总耗时和进度条
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
12. **UI优化**：
    - 在导航栏添加AI按钮
    - 实现左侧侧边栏宽度保存功能，使用localStorage持久化
    - 优化AI标注弹框样式，使元素更紧凑
    - 改进左侧侧边栏图片列表，解决序号和文件名重叠问题

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
├── AiUtils.py                # AI自动标注工具类
├── app.spec                  # PyInstaller打包配置文件
├── CHANGELOG.md              # 版本更新记录
├── LICENSE                   # 授权协议
├── README.md                 # 项目说明文档
├── requirements.txt          # 依赖列表
├── .gitignore               # Git忽略文件配置
├── static/
│   ├── all.min.css           # Font Awesome图标库
│   ├── script.js             # 脚本文件
│   ├── style.css             # 样式文件
│   ├── annotations/          # 标注数据存储目录
│   │   ├── annotations.json  # 标注数据
│   │   └── classes.json      # 标签数据
│   ├── fonts/                # 字体文件目录
│   │   ├── fa-brands-400.woff2
│   │   ├── fa-regular-400.woff2
│   │   ├── fa-solid-900.woff2
│   │   └── fa-v4compatibility.woff2
│   └── images/               # 图片资源目录
│       ├── close.gif
│       ├── load.gif
│       ├── loading.gif
│       ├── logo.ico
│       └── logo.png
├── templates/
│   ├── ai_config.html        # AI配置页面
│   ├── file_manager.html     # 文件管理页面
│   └── index.html            # 主页面模板
├── tests/                    # 测试文件目录
│   ├── TEST.md              # 测试说明
│   ├── auto_label.py        # 自动标注测试脚本
│   ├── auto_label_video.py  # 视频自动标注测试脚本
│   ├── test_api.py          # API测试脚本
│   └── test_llpr.py         # LLPR测试脚本
├── uploads/                  # 上传的图片和视频存储目录（运行时自动创建）
└── plugins/                  # 插件目录（用于YOLO11安装，运行时自动创建）
```

### 标注流程
1. **添加数据集**：点击右上角"添加数据集"按钮，选择要标注的图片、视频或LabelMe数据集
2. **创建标签**：在右侧标签管理中添加需要的标签，设置颜色
3. **开始标注**：
   - **手动标注**：选择左侧图片列表中的图片，使用左侧工具进行标注
   - **AI自动标注**：点击导航栏"AI"按钮，在弹框中配置API参数、输入提示词、选择标签，然后点击"开始执行"
4. **导出数据集**：标注完成后，点击右上角"导出数据集"按钮，选择导出格式和参数

### AI标注使用说明
1. **打开AI标注弹框**：点击导航栏中的"AI"按钮
2. **配置API参数**：检查并确认API配置信息，包括推理工具、模型、API地址等
3. **输入提示词**：在提示词输入框中输入用于标注的提示词
4. **选择标签**：从标签列表中选择一个用于标注的标签
5. **开始AI标注**：确保左侧侧边栏至少选中一个图片文件，然后点击"开始执行"
6. **查看标注进度**：在弹框中查看标注进度，包括已执行数量、总量、总耗时和进度条
7. **完成标注**：标注完成后，系统会自动更新标注数据，可在左侧图片列表中查看已标注的图片

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

### 授权协议
- 本项目自有代码使用宽松的MIT协议，在保留版权信息的情况下可以自由应用于各自商用、非商业的项目。
- 本项目使用了一些第三方库，使用本项目时请遵循相应第三方库的授权协议。
- 由于使用本项目而产生的商业纠纷或侵权行为一概与本项目及开发者无关，请自行承担法律风险。

