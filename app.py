import os
import json
import math
import numpy as np
import base64
import traceback
import cv2
import sys
import tempfile
import threading
import logging
import uuid
import time
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image
from AiUtils import AIAutoLabeler


app = Flask(__name__)
CORS(app)

# 应用版本号
APP_VERSION = "v2.7"

# 配置SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 任务管理系统
tasks = {}

# 连接ID和任务ID的映射字典，用于跟踪客户端断开连接时需要停止的任务
# 格式: {sid: task_id}
connection_task_map = {}

# 任务状态枚举
TASK_STATUS = {
    'IDLE': 'idle',
    'RUNNING': 'running',
    'PAUSED': 'paused',
    'COMPLETED': 'completed',
    'STOPPED': 'stopped',
    'ERROR': 'error'
}

class VideoAnnotationTask:
    """视频标注任务类"""
    def __init__(self, task_id, video_path, frame_interval, output_dir, api_config):
        self.task_id = task_id
        self.video_path = video_path
        self.frame_interval = frame_interval
        self.output_dir = output_dir
        self.api_config = api_config
        self.status = TASK_STATUS['IDLE']
        self.frame_count = 0
        self.processed_count = 0
        self.total_detections = 0
        self.error = None
        self.thread = None
        self.stop_event = threading.Event()
        self.start_time = None
        
    def start(self):
        """开始任务"""
        import datetime
        self.status = TASK_STATUS['RUNNING']
        self.start_time = datetime.datetime.now().isoformat()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        return self.task_id
    
    def stop(self):
        """停止任务"""
        self.stop_event.set()
        self.status = TASK_STATUS['STOPPED']
        self.send_progress()
        # 不立即join线程，让线程自己完成清理工作
    
    def run(self):
        """运行任务"""
        try:
            import os
            import time
            import base64
            import requests
            
            # 创建输出目录
            os.makedirs(self.output_dir, exist_ok=True)
            raw_dir = os.path.join(self.output_dir, 'raw_frames')
            labeled_dir = os.path.join(self.output_dir, 'labeled_frames')
            os.makedirs(raw_dir, exist_ok=True)
            os.makedirs(labeled_dir, exist_ok=True)
            
            # 获取API配置
            api_url = self.api_config.get('apiUrl', 'http://127.0.0.1:1234/v1')
            api_key = self.api_config.get('apiKey', '')
            timeout = int(self.api_config.get('timeout', 30))
            prompt = self.api_config.get('prompt', '检测图中物体，返回JSON：{"detections":[{"label":"类别","confidence":0.9,"bbox":[x1,y1,x2,y2]}]}')
            model = self.api_config.get('model', 'qwen/qwen3-vl-8b')
            inference_tool = self.api_config.get('inferenceTool', 'LMStudio')
            
            # 初始化AIAutoLabeler
            labeler = AIAutoLabeler(api_url, api_key, prompt, timeout, inference_tool, model)
            
            # 打开视频流
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.error = f'Failed to open video: {self.video_path}'
                self.status = TASK_STATUS['ERROR']
                return
            
            # 处理视频帧
            while not self.stop_event.is_set():
                # 检查停止信号
                if self.stop_event.is_set():
                    break
                    
                ret, frame = cap.read()
                if not ret:
                    # 对于RTSP流，尝试重新连接
                    if self.video_path.startswith('rtsp://'):
                        # 关闭当前连接
                        cap.release()
                        # 短暂休眠后重新打开
                        time.sleep(1)
                        cap = cv2.VideoCapture(self.video_path)
                        if not cap.isOpened():
                            self.error = f'Failed to reopen RTSP stream: {self.video_path}'
                            self.status = TASK_STATUS['ERROR']
                            self.send_progress()
                            break
                        # 发送进度更新，告知正在重连
                        self.send_progress()
                        # 继续循环，不中断任务
                        continue
                    else:
                        # 对于普通视频文件，退出循环
                        break
                
                self.frame_count += 1
                
                # 发送进度更新，即使不处理当前帧，也要更新帧计数
                if self.frame_count % 10 == 0:  # 每10帧发送一次进度更新
                    self.send_progress()
                
                # 按照指定间隔处理帧
                if self.frame_count % self.frame_interval == 0:
                    # 检查停止信号
                    if self.stop_event.is_set():
                        break
                        
                    # 保存原始帧
                    frame_filename = f"frame_{self.frame_count:06d}.jpg"
                    raw_frame_path = os.path.join(raw_dir, frame_filename)
                    cv2.imwrite(raw_frame_path, frame)
                    
                    # 检查停止信号
                    if self.stop_event.is_set():
                        break
                    
                    # 检查停止信号
                    if self.stop_event.is_set():
                        break
                        
                    # 调用API进行标注
                    try:
                        result = labeler.analyze_image(raw_frame_path)
                        detections = result.get("detections", [])
                        if isinstance(detections, dict):
                            detections = [detections]
                    except Exception as e:
                        # API请求失败，继续处理下一帧
                        logging.error(f"API request failed: {str(e)}")
                        # 发送进度更新，告知API请求失败
                        self.send_progress()
                        continue
                    
                    # 检查停止信号
                    if self.stop_event.is_set():
                        break
                    
                    # 检查停止信号
                    if self.stop_event.is_set():
                        break
                        
                    # 渲染检测结果
                    rendered_path = labeler.render_detections(raw_frame_path, detections)
                    
                    # 保存渲染后的帧
                    labeled_frame_path = os.path.join(labeled_dir, frame_filename)
                    # 如果目标文件已存在，先删除
                    if os.path.exists(labeled_frame_path):
                        os.remove(labeled_frame_path)
                    os.rename(rendered_path, labeled_frame_path)
                    
                    # 读取渲染后的帧用于后续处理
                    labeled_frame = cv2.imread(labeled_frame_path)
                    
                    self.processed_count += 1
                    self.total_detections += len(detections)
                    
                    # 生成当前帧和渲染后图片的Base64数据（用于实时显示）
                    # 压缩当前帧用于显示
                    _, raw_buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    current_frame_base64 = base64.b64encode(raw_buffer).decode("utf-8")
                    
                    # 压缩渲染后的帧用于显示
                    _, labeled_buffer = cv2.imencode('.jpg', labeled_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    labeled_frame_base64 = base64.b64encode(labeled_buffer).decode("utf-8")
                    
                    # 发送进度更新，包含当前帧和渲染后的图片
                    self.send_progress(current_frame_base64, labeled_frame_base64)
                    
                    # 短暂休眠，提高响应速度
                    time.sleep(0.001)
            
            # 确保发送最终的进度更新
            # 如果状态还没有被设置为STOPPED或ERROR，设置为COMPLETED
            if self.status != TASK_STATUS['ERROR'] and self.status != TASK_STATUS['STOPPED']:
                self.status = TASK_STATUS['COMPLETED']
            # 发送最终的进度更新
            self.send_progress()
            
        except Exception as e:
            self.status = TASK_STATUS['ERROR']
            self.error = str(e)
            self.send_progress()
        finally:
            # 释放资源
            cap.release()
    
    def send_progress(self, current_frame=None, labeled_frame=None):
        """发送进度更新"""
        import datetime
        progress = {
            'task_id': self.task_id,
            'status': self.status,
            'frame_count': self.frame_count,
            'processed_count': self.processed_count,
            'total_detections': self.total_detections,
            'error': self.error,
            'output_dir': self.output_dir,
            'start_time': self.start_time,
            'current_time': datetime.datetime.now().isoformat()
        }
        
        # 如果提供了当前帧和渲染后的图片，添加到进度更新中
        if current_frame:
            progress['current_frame'] = current_frame
        if labeled_frame:
            progress['labeled_frame'] = labeled_frame
        
        socketio.emit('progress_update', progress)
        
        # 任务完成、停止或出错后，从任务列表中移除任务
        if self.status in [TASK_STATUS['COMPLETED'], TASK_STATUS['STOPPED'], TASK_STATUS['ERROR']]:
            # 使用线程安全的方式移除任务
            if self.task_id in tasks:
                del tasks[self.task_id]
        
    def get_status(self):
        """获取任务状态"""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'frame_count': self.frame_count,
            'processed_count': self.processed_count,
            'total_detections': self.total_detections,
            'error': self.error,
            'output_dir': self.output_dir
        }

# 配置
import os

# 使用当前工作目录作为基础目录
BASE_PATH = os.getcwd()
UPLOAD_FOLDER = os.path.join(BASE_PATH, 'uploads')
STATIC_FOLDER = os.path.join(BASE_PATH, 'static')
ANNOTATIONS_FOLDER = os.path.join(UPLOAD_FOLDER, 'annotations')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STATIC_FOLDER'] = STATIC_FOLDER
app.config['ANNOTATIONS_FOLDER'] = ANNOTATIONS_FOLDER

# 创建必要的目录
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)
os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)

# 模拟数据库存储标注信息
ANNOTATIONS_FILE = os.path.join(ANNOTATIONS_FOLDER, 'annotations.json')
CLASSES_FILE = os.path.join(ANNOTATIONS_FOLDER, 'classes.json')

# 初始化注释文件
if not os.path.exists(ANNOTATIONS_FILE):
    with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)
        
# 初始化类别文件
if not os.path.exists(CLASSES_FILE):
    # 默认类别
    default_classes = [
        {'name': 'person', 'color': '#3aa757'}
    ]
    with open(CLASSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_classes, f)


@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION)

@app.route('/ai-config')
def ai_config():
    return render_template('ai_config.html', version=APP_VERSION)

@app.route('/file-manager')
def file_manager():
    """文件管理页面"""
    return render_template('file_manager.html', version=APP_VERSION)

@app.route('/api/files')
def get_files():
    """获取指定路径下的文件列表"""
    import os
    import mimetypes
    from datetime import datetime
    
    # 获取请求参数
    path = request.args.get('path', 'uploads')
    
    # 安全检查，防止路径遍历攻击
    if '..' in path or path.startswith('/'):
        return jsonify({
            'success': False,
            'error': 'Invalid path'
        }), 400
    
    # 构建完整路径
    # 确保uploads目录存在
    if not os.path.exists('uploads'):
        os.makedirs('uploads', exist_ok=True)
    
    # 优先使用当前工作目录下的uploads目录
    base_path = os.getcwd()
    full_path = os.path.join(base_path, path)
    
    # 检查路径是否存在
    if not os.path.exists(full_path):
        return jsonify({
            'success': False,
            'error': 'Path not found'
        }), 404
    
    # 检查是否为目录
    if not os.path.isdir(full_path):
        return jsonify({
            'success': False,
            'error': 'Path is not a directory'
        }), 400
    
    # 获取目录下的所有项目
    items = os.listdir(full_path)
    files = []
    
    for item in items:
        item_path = os.path.join(full_path, item)
        item_info = {
                'name': item,
                'path': os.path.join(path, item).replace('\\', '/'),
                'relativePath': os.path.relpath(item_path, os.path.join(base_path, 'uploads')).replace('\\', '/') if path.startswith('uploads') else None
            }
        
        if os.path.isdir(item_path):
            # 文件夹
            item_info['type'] = 'folder'
            item_info['size'] = 0
            # 统计子项目数量
            try:
                item_info['children'] = len(os.listdir(item_path))
            except:
                item_info['children'] = 0
        else:
            # 文件
            # 获取文件类型
            mime_type, _ = mimetypes.guess_type(item_path)
            if mime_type and mime_type.startswith('image/'):
                item_info['type'] = 'image'
                # 获取图片尺寸
                try:
                    from PIL import Image
                    with Image.open(item_path) as img:
                        width, height = img.size
                        item_info['width'] = width
                        item_info['height'] = height
                except:
                    item_info['width'] = 0
                    item_info['height'] = 0
            else:
                item_info['type'] = 'file'
            
            # 获取文件大小
            item_info['size'] = os.path.getsize(item_path)
            # 格式化文件大小
            def format_size(size):
                """格式化文件大小"""
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024.0:
                        return f"{size:.1f} {unit}"
                    size /= 1024.0
                return f"{size:.1f} TB"
            item_info['size'] = format_size(item_info['size'])
        
        # 获取修改时间
        mtime = os.path.getmtime(item_path)
        item_info['mtime'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        files.append(item_info)
    
    # 按类型排序，文件夹在前，文件在后，然后按名称排序
    files.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
    
    return jsonify({
        'success': True,
        'files': files
    })

@app.route('/api/classes')
def get_classes():
    """获取所有类别"""
    classes = []
    if os.path.exists(CLASSES_FILE):
        with open(CLASSES_FILE, 'r', encoding='utf-8') as f:
            classes = json.load(f)
    return jsonify(classes)


@app.route('/api/classes', methods=['POST'])
def save_classes():
    """保存所有类别"""
    data = request.json
    
    # 确保ANNOTATIONS_FOLDER目录存在
    os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)
    
    with open(CLASSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    return jsonify({'message': 'Classes saved successfully'})


@app.route('/api/images')
def get_images():
    """获取所有上传的图片"""
    images = []
    
    # 读取标注信息，用于获取每张图片的标注数量
    annotations = {}
    if os.path.exists(ANNOTATIONS_FILE):
        try:
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
        except json.JSONDecodeError:
            # 如果JSON文件无效或为空，使用空字典
            annotations = {}
        except Exception as e:
            # 处理其他可能的错误
            print(f"Error reading annotations file: {e}")
            annotations = {}
    
    # 获取所有图片文件，并按照创建时间排序（最新的在最后）
    upload_folder = app.config['UPLOAD_FOLDER']
    image_files = []
    
    for filename in os.listdir(upload_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            image_path = os.path.join(upload_folder, filename)
            # 获取文件创建时间
            try:
                create_time = os.path.getctime(image_path)
                image_files.append((create_time, filename))
            except Exception as e:
                print(f"Error getting file creation time for {filename}: {e}")
                # 如果获取创建时间失败，使用当前时间作为默认值
                image_files.append((time.time(), filename))
    
    # 按照创建时间排序，最早的在前面，最新的在后面
    image_files.sort(key=lambda x: x[0])
    
    # 构建图片列表
    for create_time, filename in image_files:
        # 获取图片尺寸信息
        try:
            image_path = os.path.join(upload_folder, filename)
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0
        
        # 获取标注数量
        annotation_count = len(annotations.get(filename, []))
        
        images.append({
            'name': filename,
            'width': width,
            'height': height,
            'annotation_count': annotation_count
        })
    return jsonify({'images': images})


@app.route('/api/images/delete', methods=['POST'])
def delete_images():
    """删除指定的图片"""
    data = request.json or {}
    image_names = data.get('images', [])
    
    deleted_count = 0
    errors = []
    
    for image_name in image_names:
        try:
            # 删除图片文件
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_name)
            if os.path.exists(image_path):
                os.remove(image_path)
                deleted_count += 1
                
                # 同时删除对应的标注信息
                annotations = {}
                if os.path.exists(ANNOTATIONS_FILE):
                    with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                        annotations = json.load(f)
                    
                if image_name in annotations:
                    del annotations[image_name]
                    # 确保ANNOTATIONS_FOLDER目录存在
                    os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)
                    with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(annotations, f, indent=2)
            else:
                errors.append(f"图片 '{image_name}' 不存在")
        except Exception as e:
            errors.append(f"删除图片 '{image_name}' 失败: {str(e)}")
    
    if errors:
        return jsonify({
            'success': False,
            'deleted_count': deleted_count,
            'error': '; '.join(errors)
        }), 400
    
    return jsonify({
        'success': True,
        'deleted_count': deleted_count
    })


@app.route('/api/files/delete', methods=['POST'])
def delete_files():
    """删除指定的文件"""
    data = request.json or {}
    file_paths = data.get('files', [])
    
    deleted_count = 0
    errors = []
    
    for file_path in file_paths:
        try:
            # 安全检查，防止路径遍历攻击
            if '..' in file_path or file_path.startswith('/'):
                errors.append(f"无效的文件路径: '{file_path}'")
                continue
            
            # 构建完整路径
            full_path = os.path.join(app.root_path, file_path)
            
            # 检查文件是否存在
            if not os.path.exists(full_path):
                errors.append(f"文件 '{file_path}' 不存在")
                continue
            
            # 检查是否为文件
            if not os.path.isfile(full_path):
                errors.append(f" '{file_path}' 不是文件")
                continue
            
            # 删除文件
            os.remove(full_path)
            deleted_count += 1
            
            # 如果是图片文件，同时删除对应的标注信息
            if os.path.splitext(file_path)[1].lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                image_name = os.path.basename(file_path)
                annotations = {}
                if os.path.exists(ANNOTATIONS_FILE):
                    with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                        annotations = json.load(f)
                    
                if image_name in annotations:
                    del annotations[image_name]
                    # 确保ANNOTATIONS_FOLDER目录存在
                    os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)
                    with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(annotations, f, indent=2)
        except Exception as e:
            errors.append(f"删除文件 '{file_path}' 失败: {str(e)}")
    
    if errors:
        return jsonify({
            'success': False,
            'deleted_count': deleted_count,
            'error': '; '.join(errors)
        }), 400
    
    return jsonify({
        'success': True,
        'deleted_count': deleted_count
    })


@app.route('/api/files/create-folder', methods=['POST'])
def create_folder():
    """创建新文件夹"""
    data = request.json or {}
    path = data.get('path', '')
    folder_name = data.get('folderName', '')
    
    # 参数验证
    if not path or not folder_name:
        return jsonify({
            'success': False,
            'error': '缺少必要参数'
        }), 400
    
    # 安全检查，防止路径遍历攻击
    if '..' in path or path.startswith('/') or '..' in folder_name or folder_name.startswith('/'):
        return jsonify({
            'success': False,
            'error': '无效的路径或文件夹名称'
        }), 400
    
    try:
        # 构建完整的文件夹路径
        full_path = os.path.join(app.root_path, path, folder_name)
        
        # 检查文件夹是否已存在
        if os.path.exists(full_path):
            return jsonify({
                'success': False,
                'error': '文件夹已存在'
            }), 400
        
        # 创建文件夹
        os.makedirs(full_path, exist_ok=True)
        
        return jsonify({
            'success': True,
            'message': '文件夹创建成功'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'创建文件夹失败: {str(e)}'
        }), 500


@app.route('/api/files/upload', methods=['POST'])
def upload_files():
    """上传文件"""
    try:
        # 获取路径参数
        path = request.form.get('path', 'uploads')
        
        # 安全检查，防止路径遍历攻击
        if '..' in path or path.startswith('/'):
            return jsonify({
                'success': False,
                'error': '无效的路径'
            }), 400
        
        # 获取上传的文件
        files = request.files.getlist('files[]')
        if not files:
            return jsonify({
                'success': False,
                'error': '没有选择要上传的文件'
            }), 400
        
        # 构建上传目录路径
        upload_dir = os.path.join(app.root_path, path)
        
        # 确保上传目录存在
        os.makedirs(upload_dir, exist_ok=True)
        
        uploaded_count = 0
        errors = []
        
        # 保存上传的文件
        for file in files:
            if file.filename:
                # 安全检查，防止路径遍历攻击
                if '..' in file.filename or file.filename.startswith('/'):
                    errors.append(f"无效的文件名: '{file.filename}'")
                    continue
                
                # 构建完整的文件路径
                file_path = os.path.join(upload_dir, file.filename)
                
                # 检查文件是否已存在
                if os.path.exists(file_path):
                    errors.append(f"文件 '{file.filename}' 已存在")
                    continue
                
                # 保存文件
                file.save(file_path)
                uploaded_count += 1
        
        if errors:
            return jsonify({
                'success': False,
                'uploaded_count': uploaded_count,
                'error': '; '.join(errors)
            }), 400
        
        return jsonify({
            'success': True,
            'uploaded_count': uploaded_count,
            'message': '文件上传成功'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'上传文件失败: {str(e)}'
        }), 500


@app.route('/api/upload-video', methods=['POST'])
def upload_video_for_label():
    """上传视频文件用于标注"""
    try:
        # 检查是否有文件上传
        if 'video' not in request.files:
            return jsonify({
                'success': False,
                'error': '没有视频文件上传'
            }), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '没有选择视频文件'
            }), 400
        
        # 安全检查，防止路径遍历攻击
        if '..' in file.filename or file.filename.startswith('/'):
            return jsonify({
                'success': False,
                'error': '无效的文件名'
            }), 400
        
        # 构建上传目录路径
        upload_dir = os.path.join(app.root_path, 'uploads', 'auto', 'video')
        
        # 确保上传目录存在
        os.makedirs(upload_dir, exist_ok=True)
        
        # 构建完整的文件路径
        file_path = os.path.join(upload_dir, file.filename)
        
        # 检查文件是否已存在，如果存在则删除
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 保存文件
        file.save(file_path)
        
        # 返回相对路径，格式为: uploads/auto/video/filename
        relative_path = os.path.join('uploads', 'auto', 'video', file.filename)
        
        return jsonify({
            'success': True,
            'filePath': relative_path,
            'message': '视频文件上传成功'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'上传视频文件失败: {str(e)}'
        }), 500


@app.route('/api/files/download', methods=['POST'])
def download_files():
    """批量下载文件，将选中的文件压缩成tar文件后下载"""
    try:
        import tarfile
        import tempfile
        
        # 获取请求参数
        data = request.json or {}
        file_paths = data.get('files', [])
        
        if not file_paths:
            return jsonify({
                'success': False,
                'error': '没有选择要下载的文件'
            }), 400
        
        # 创建临时目录和tar文件
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建tar文件
            tar_file_path = os.path.join(temp_dir, 'files.tar')
            
            with tarfile.open(tar_file_path, 'w') as tar:
                # 添加每个文件到tar文件
                for file_path in file_paths:
                    # 安全检查，防止路径遍历攻击
                    if '..' in file_path or file_path.startswith('/'):
                        continue
                    
                    # 构建完整的文件路径
                    full_path = os.path.join(app.root_path, file_path)
                    
                    # 检查文件是否存在且是文件
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        # 获取相对路径（相对于app.root_path）
                        rel_path = os.path.relpath(full_path, app.root_path)
                        # 获取文件名
                        file_name = os.path.basename(full_path)
                        # 添加文件到tar，使用文件名作为内部名称
                        tar.add(full_path, arcname=file_name)
            
            # 读取tar文件内容
            with open(tar_file_path, 'rb') as f:
                tar_content = f.read()
        
        # 设置响应头，返回tar文件
        from flask import make_response
        response = make_response(tar_content)
        response.headers['Content-Type'] = 'application/x-tar'
        response.headers['Content-Disposition'] = 'attachment; filename=files.tar'
        response.headers['Content-Length'] = len(tar_content)
        
        return response
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'下载文件失败: {str(e)}'
        }), 500


@app.route('/api/image/<filename>')
def get_image(filename):
    """获取指定图片"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """提供uploads目录下的文件访问，支持子目录"""
    import os
    
    # 打印请求的文件名和UPLOAD_FOLDER配置，用于调试
    print(f"请求的文件路径: {filename}")
    print(f"UPLOAD_FOLDER配置: {app.config['UPLOAD_FOLDER']}")
    
    # 构建完整的文件路径
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"完整的文件路径: {full_path}")
    
    # 检查文件是否存在
    if not os.path.exists(full_path):
        print(f"文件不存在: {full_path}")
        return jsonify({
            'success': False,
            'error': 'File not found',
            'requested_path': filename,
            'full_path': full_path,
            'upload_folder': app.config['UPLOAD_FOLDER']
        }), 404
    
    # 安全检查，防止路径遍历攻击
    if '..' in filename or filename.startswith('/'):
        print(f"不安全的文件路径: {filename}")
        return jsonify({
            'success': False,
            'error': 'Invalid file path'
        }), 400
    
    print(f"成功找到文件: {full_path}")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/upload', methods=['POST'])
def upload_folder():
    """上传整个文件夹"""
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files[]')
    uploaded_files = []
    
    for file in files:
        if file.filename != '':
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename or '')
            file.save(filepath)
            uploaded_files.append(file.filename or '')
    
    return jsonify({'message': 'Files uploaded successfully', 'files': uploaded_files})


@app.route('/api/upload-labelme', methods=['POST'])
def upload_labelme_dataset():
    """上传LabelMe格式数据集"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        uploaded_files = []
        processed_annotations = 0
        
        # 读取现有的类别和标注信息
        classes = []
        if os.path.exists(CLASSES_FILE):
            with open(CLASSES_FILE, 'r', encoding='utf-8') as f:
                classes = json.load(f)
        
        annotations = {}
        if os.path.exists(ANNOTATIONS_FILE):
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
        
        # 获取已有类别名称集合，便于快速查找
        existing_class_names = {cls['name'] for cls in classes}
        
        # 处理上传的文件
        image_files = {}
        json_files = {}
        
        for file in files:
            if file.filename != '':
                filename = file.filename or ''
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    image_files[filename] = file
                elif filename.lower().endswith('.json'):
                    json_files[filename] = file
        
        # 处理图像文件
        for image_filename, image_file in image_files.items():
            # 保存图像文件
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(image_path)
            uploaded_files.append(image_filename)
            
            # 查找对应的JSON文件
            json_filename = os.path.splitext(image_filename)[0] + '.json'
            if json_filename in json_files:
                # 读取并解析JSON文件
                json_file = json_files[json_filename]
                json_content = json.loads(json_file.read().decode('utf-8'))
                
                # 解析LabelMe标注格式
                image_annotations = []
                if 'shapes' in json_content:
                    for shape in json_content['shapes']:
                        label = shape.get('label', '')
                        points = shape.get('points', [])
                        
                        # 如果标签不存在于现有类别中，添加它
                        if label and label not in existing_class_names:
                            # 为新类别分配一个默认颜色
                            new_color = '#{:06x}'.format(hash(label) % 0x1000000)
                            classes.append({'name': label, 'color': new_color})
                            existing_class_names.add(label)
                        
                        # 将points转换为我们的内部格式
                        if points and label:
                            # 查找标签的颜色
                            color = '#000000'  # 默认颜色
                            for cls in classes:
                                if cls['name'] == label:
                                    color = cls['color']
                                    break
                            
                            # 确定形状类型
                            shape_type = shape.get('shape_type', 'polygon')
                            
                            # 转换为我们的内部格式
                            internal_points = points
                            internal_type = shape_type
                            
                            # 处理矩形：LabelMe矩形只有2个点，我们需要转换为4个点的矩形
                            if shape_type == 'rectangle' and len(points) == 2:
                                x1, y1 = points[0]
                                x2, y2 = points[1]
                                internal_points = [
                                    [x1, y1],
                                    [x2, y1],
                                    [x2, y2],
                                    [x1, y2]
                                ]
                                internal_type = 'rectangle'
                            elif shape_type == 'circle' and len(points) == 2:
                                # 处理圆形，转换为多边形（简化处理）
                                cx, cy = points[0]
                                radius = ((points[1][0] - cx) ** 2 + (points[1][1] - cy) ** 2) ** 0.5
                                # 转换为16边形近似圆形
                                internal_points = []
                                for i in range(16):
                                    angle = (i / 16) * 2 * 3.14159
                                    x = cx + radius * math.cos(angle)
                                    y = cy + radius * math.sin(angle)
                                    internal_points.append([x, y])
                                internal_type = 'polygon'
                            elif shape_type == 'line' and len(points) >= 2:
                                internal_type = 'line'
                            else:
                                internal_type = 'polygon'
                            
                            # 创建标注对象
                            annotation = {
                                'class': label,
                                'color': color,
                                'points': internal_points,
                                'type': internal_type
                            }
                            image_annotations.append(annotation)
                
                # 保存此图像的标注
                annotations[image_filename] = image_annotations
                processed_annotations += 1
        
        # 保存更新后的类别和标注信息
        # 确保ANNOTATIONS_FOLDER目录存在
        os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)
        with open(CLASSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(classes, f, indent=2)
        
        with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(annotations, f, indent=2)
        
        return jsonify({
            'message': 'LabelMe dataset uploaded successfully', 
            'files': uploaded_files,
            'annotations_processed': processed_annotations
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process LabelMe dataset: {str(e)}'}), 500
        

@app.route('/api/ai-label', methods=['POST'])
def ai_label():
    """AI标注功能"""
    try:
        import os
        import json
        import logging
        import datetime
        
        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        images = data.get('images', [])
        selected_label = data.get('label')
        api_config = data.get('apiConfig', {})
        
        if not images:
            return jsonify({'success': False, 'error': 'No images provided'}), 400
        
        if not selected_label:
            return jsonify({'success': False, 'error': 'No label provided'}), 400
        
        # 获取API配置
        api_url = api_config.get('apiUrl', 'http://127.0.0.1:1234/v1')
        api_key = api_config.get('apiKey', '')
        timeout = int(api_config.get('timeout', 30))
        prompt = api_config.get('prompt', '检测图中物体，返回JSON：{"detections":[{"label":"类别","confidence":0.9,"bbox":[x1,y1,x2,y2]}]}')
        model = api_config.get('model', 'qwen/qwen3-vl-8b')
        inference_tool = api_config.get('inferenceTool', 'LMStudio')
        
        # 初始化AIAutoLabeler
        labeler = AIAutoLabeler(api_url, api_key, prompt, timeout, inference_tool, model)
        
        # 读取现有的标注信息
        annotations = {}
        if os.path.exists(ANNOTATIONS_FILE):
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
        
        processed_count = 0
        labeled_count = 0
        total_images = len(images)
        start_time = datetime.datetime.now()
        
        # 处理每张图片
        for image_name in images:
            # 构建图片路径
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_name)
            if not os.path.exists(image_path):
                logging.error(f"Image not found: {image_path}")
                continue
            
            processed_count += 1
            
            # 发送实时进度更新
            current_time = datetime.datetime.now()
            elapsed_seconds = int((current_time - start_time).total_seconds())
            progress_data = {
                'task_type': 'ai_label',
                'status': 'running',
                'processed': processed_count,
                'total': total_images,
                'elapsed_time': elapsed_seconds,
                'labeled': labeled_count,
                'message': f'正在处理第 {processed_count}/{total_images} 张图片'
            }
            socketio.emit('ai_label_progress', progress_data)
            
            # 调用API进行标注
            try:
                result = labeler.analyze_image(image_path)
                detections = result.get("detections", [])
                if isinstance(detections, dict):
                    detections = [detections]
                
                # 如果检测到目标，更新标注状态
                if detections:
                    # 为每张图片创建标注
                    image_annotations = []
                    for detection in detections:
                        # 确保detection是字典
                        if isinstance(detection, dict):
                            label = selected_label  # 使用选中的标签
                            confidence = detection.get("confidence", 0.0)
                            bbox = detection.get("bbox", [0, 0, 0, 0])
                            
                            # 转换为前端期望的标注格式
                            # 确保bbox是一个包含四个数值的列表
                            bbox = list(map(float, bbox)) if isinstance(bbox, (list, tuple)) else [0, 0, 0, 0]
                            # 确保bbox有四个值
                            if len(bbox) < 4:
                                bbox = bbox + [0] * (4 - len(bbox))
                            x1, y1, x2, y2 = bbox[:4]  # 只取前四个值
                            
                            annotation = {
                                "id": str(uuid.uuid4()),  # 添加唯一ID
                                "class": label,  # 前端使用class字段
                                "type": "rectangle",  # 前端需要type字段
                                "points": [
                                    [x1, y1],
                                    [x2, y1],
                                    [x2, y2],
                                    [x1, y2]
                                ],  # 转换为points数组
                                "confidence": confidence
                            }
                            image_annotations.append(annotation)
                    
                    # 更新标注信息
                    annotations[image_name] = image_annotations
                    labeled_count += 1
            except Exception as e:
                logging.error(f"Failed to process image {image_name}: {str(e)}")
                continue
        
        # 保存更新后的标注信息
        # 确保ANNOTATIONS_FOLDER目录存在
        os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)
        with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(annotations, f, indent=2, ensure_ascii=False)
        
        # 发送最终进度更新
        current_time = datetime.datetime.now()
        elapsed_seconds = int((current_time - start_time).total_seconds())
        final_progress = {
            'task_type': 'ai_label',
            'status': 'completed',
            'processed': processed_count,
            'total': total_images,
            'elapsed_time': elapsed_seconds,
            'labeled': labeled_count,
            'message': f'标注完成，成功处理 {processed_count} 张图片，其中 {labeled_count} 张标注成功'
        }
        socketio.emit('ai_label_progress', final_progress)
        
        return jsonify({
            'success': True,
            'processed': processed_count,
            'labeled': labeled_count,
            'message': f'成功处理 {processed_count} 张图片，其中 {labeled_count} 张标注成功'
        })
        
    except Exception as e:
        import traceback
        logging.error(f"AI label failed: {str(e)}")
        
        # 发送错误进度更新
        progress_data = {
            'task_type': 'ai_label',
            'status': 'error',
            'error': str(e),
            'message': f'标注失败: {str(e)}'
        }
        socketio.emit('ai_label_progress', progress_data)
        
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/upload/video', methods=['POST'])
def upload_video():
    """上传视频文件并抽帧"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    frame_interval = int(request.form.get('frame_interval', 30))  # 默认每隔30帧保存一帧
    
    if video_file.filename == '':
        return jsonify({'error': 'No video file selected'}), 400
    
    try:
        # 保存视频文件到临时位置
        temp_video_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_' + (video_file.filename or 'video'))
        video_file.save(temp_video_path)
        
        # 抽帧处理，传递原始文件名
        extracted_frames = extract_frames(temp_video_path, frame_interval, video_file.filename)
        
        # 删除临时视频文件
        os.remove(temp_video_path)
        
        return jsonify({
            'message': 'Video frames extracted successfully', 
            'frames': extracted_frames,
            'count': len(extracted_frames)
        })
    except Exception as e:
        return jsonify({'error': f'Failed to process video: {str(e)}'}), 500


def extract_frames(video_path, frame_interval, original_filename=None):
    """从视频中抽帧并保存为图片"""
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    saved_frame_count = 0
    extracted_frames = []
    
    # 生成文件名前缀
    if original_filename:
        # 使用原始视频文件名作为前缀
        video_name = os.path.splitext(os.path.basename(original_filename))[0]
    else:
        # 使用视频路径中的文件名作为前缀
        video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # 每隔frame_interval帧保存一帧
        if frame_count % frame_interval == 0:
            # 生成文件名
            frame_filename = f"{video_name}_frame_{saved_frame_count:06d}.jpg"
            frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
            
            # 保存帧为图片
            cv2.imwrite(frame_path, frame)
            extracted_frames.append(frame_filename)
            saved_frame_count += 1
            
        frame_count += 1
    
    cap.release()
    return extracted_frames


@app.route('/api/annotations/<image_name>')
def get_annotations(image_name):
    """获取特定图片的标注"""
    annotations = {}
    if os.path.exists(ANNOTATIONS_FILE):
        try:
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
        except json.JSONDecodeError:
            # 如果JSON文件无效或为空，使用空字典
            annotations = {}
        except Exception as e:
            # 处理其他可能的错误
            print(f"Error reading annotations file: {e}")
            annotations = {}
    
    image_annotations = annotations.get(image_name, [])
    return jsonify(image_annotations)


@app.route('/api/annotations/<image_name>', methods=['POST'])
def save_annotations(image_name):
    """保存特定图片的标注"""
    data = request.json
    
    annotations = {}
    if os.path.exists(ANNOTATIONS_FILE):
        try:
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
        except json.JSONDecodeError:
            # 如果JSON文件无效或为空，使用空字典
            annotations = {}
        except Exception as e:
            # 处理其他可能的错误
            print(f"Error reading annotations file: {e}")
            annotations = {}
    
    annotations[image_name] = data
    
    # 确保ANNOTATIONS_FOLDER目录存在
    os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)
    with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)
    
    return jsonify({'message': 'Annotations saved successfully'})


@app.route('/api/ai-annotate', methods=['POST'])
def ai_annotate():
    """执行AI自动标注 - 已停用"""
    return jsonify({
        'error': 'AI自动标注功能已停用',
        'details': '管理员已停用此功能'
    }), 400


# 自动标注相关API
@app.route('/api/save-api-config', methods=['POST'])
def save_api_config():
    """保存API配置"""
    try:
        # 获取配置数据
        config_data = request.json
        if not config_data:
            return jsonify({'success': False, 'error': 'No config data provided'}), 400
        
        # 确保uploads/config目录存在
        os.makedirs(os.path.join(UPLOAD_FOLDER, 'config'), exist_ok=True)
        
        # 保存配置到文件
        config_path = os.path.join(UPLOAD_FOLDER, 'config', 'ai_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'API配置保存成功'})
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/load-api-config', methods=['GET'])
def load_api_config():
    """加载API配置"""
    try:
        # 读取配置文件
        config_path = os.path.join(UPLOAD_FOLDER, 'config', 'ai_config.json')
        if not os.path.exists(config_path):
            # 返回默认配置
            default_config = {
                "inferenceTool": "LMStudio",
                "model": "qwen/qwen3-vl-8b",
                "apiUrl": "http://127.0.0.1:1234/v1",
                "apiKey": "",
                "timeout": 30,
                "prompt": "检测图中物体，返回JSON：{\"detections\":[{\"label\":\"类别\",\"confidence\":0.9,\"bbox\":[x1,y1,x2,y2]}]}"
            }
            return jsonify({'success': True, 'config': default_config})
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return jsonify({'success': True, 'config': config_data})
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/auto-label/test', methods=['POST'])
def api_test():
    """测试大模型API连接"""
    try:
        # 获取表单数据
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        api_url = request.form.get('api_url', 'http://127.0.0.1:1234/v1')
        api_key = request.form.get('api_key', '')
        timeout = int(request.form.get('timeout', 30))
        prompt = request.form.get('prompt', '检测图中物体，返回JSON：{"detections":[{"label":"类别","confidence":0.9,"bbox":[x1,y1,x2,y2]}]}')
        inference_tool = request.form.get('inferenceTool', 'LMStudio')
        model = request.form.get('model', 'qwen/qwen3-vl-8b')
        
        # 保存临时图片文件
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_file_path = temp_file.name
            image_file.save(temp_file_path)
        
        try:
            # 初始化AIAutoLabeler
            labeler = AIAutoLabeler(api_url, api_key, prompt, timeout, inference_tool, model)
            
            # 调用analyze_image方法测试API
            result = labeler.analyze_image(temp_file_path)
            
            return jsonify({
                'success': True,
                'result': result
            })
        finally:
            # 确保临时文件被删除
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# 修复后的auto_label_image函数
@app.route('/api/auto-label/image', methods=['POST'])
def auto_label_image():
    """图片自动标注"""
    try:
        import os
        import tempfile
        import logging
        
        # 获取表单数据
        files = request.files.getlist('images')
        output_dir = request.form.get('output_dir', 'output')
        api_url = request.form.get('api_url', 'http://127.0.0.1:1234/v1')
        api_key = request.form.get('api_key', '')
        timeout = int(request.form.get('timeout', 30))
        prompt = request.form.get('prompt', '检测图中物体，返回JSON：{"detections":[{"label":"类别","confidence":0.9,"bbox":[x1,y1,x2,y2]}]}')
        inference_tool = request.form.get('inferenceTool', 'LMStudio')
        
        if not files:
            return jsonify({'success': False, 'error': 'No image files provided'}), 400
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        raw_dir = os.path.join(output_dir, 'raw_frames')
        labeled_dir = os.path.join(output_dir, 'labeled_frames')
        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(labeled_dir, exist_ok=True)
        
        processed_count = 0
        total_detections = 0
        
        # 初始化图片列表，用于存储每张图片的处理结果和Base64数据
        images = []
        
        # 获取模型配置
        model = request.form.get('model', 'qwen/qwen3-vl-8b')
        
        # 初始化AIAutoLabeler
        labeler = AIAutoLabeler(api_url, api_key, prompt, timeout, inference_tool, model)
        
        # 处理每张图片
        for file in files:
            if file.filename == '':
                continue
            
            # 保存原始图片
            filename = os.path.basename(file.filename)
            raw_path = os.path.join(raw_dir, filename)
            file.save(raw_path)
            
            # 调用API进行标注
            try:
                result = labeler.analyze_image(raw_path)
                detections = result.get("detections", [])
                if isinstance(detections, dict):
                    detections = [detections]
            except Exception as e:
                error_msg = f"处理图片失败: {str(e)}"
                logging.error(error_msg)
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'processed': processed_count,
                    'detections': total_detections,
                    'output_dir': output_dir
                }), 500
            
            # 渲染检测结果
            rendered_path = labeler.render_detections(raw_path, detections)
            
            # 移动渲染后的图片到输出目录
            labeled_path = os.path.join(labeled_dir, filename)
            # 如果目标文件已存在，先删除
            if os.path.exists(labeled_path):
                os.remove(labeled_path)
            os.rename(rendered_path, labeled_path)
            
            # 生成原始图片的Base64数据
            import base64
            with open(raw_path, "rb") as f:
                raw_image_data = f.read()
            raw_image_base64 = base64.b64encode(raw_image_data).decode("utf-8")
            raw_image_base64 = f"data:image/jpeg;base64,{raw_image_base64}"
            
            # 生成渲染后图片的Base64数据
            with open(labeled_path, "rb") as f:
                labeled_image_data = f.read()
            labeled_image_base64 = base64.b64encode(labeled_image_data).decode("utf-8")
            labeled_image_base64 = f"data:image/jpeg;base64,{labeled_image_base64}"
            
            # 将图片信息添加到列表
            images.append({
                'filename': filename,
                'original_image': raw_image_base64,
                'labeled_image': labeled_image_base64,
                'detections': len(detections)
            })
            
            processed_count += 1
            total_detections += len(detections)
        
        return jsonify({
            'success': True,
            'processed': processed_count,
            'detections': total_detections,
            'output_dir': output_dir,
            'images': images
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# 修复后的auto_label_video函数
@app.route('/api/auto-label/video', methods=['POST'])
def auto_label_video():
    """视频自动标注"""
    try:
        import os
        import time
        from collections import deque
        import logging
        
        # 获取请求数据
        data = request.json
        video_path = data.get('video_path')
        frame_interval = int(data.get('frame_interval', 10))
        output_dir = data.get('output_dir', 'output')
        api_config = data.get('api_config', {})
        
        if not video_path:
            return jsonify({'success': False, 'error': 'No video path provided'}), 400
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        raw_dir = os.path.join(output_dir, 'raw_frames')
        labeled_dir = os.path.join(output_dir, 'labeled_frames')
        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(labeled_dir, exist_ok=True)
        
        # 获取API配置
        api_url = api_config.get('apiUrl', 'http://127.0.0.1:1234/v1')
        api_key = api_config.get('apiKey', '')
        timeout = int(api_config.get('timeout', 30))
        prompt = api_config.get('prompt', '检测图中物体，返回JSON：{"detections":[{"label":"类别","confidence":0.9,"bbox":[x1,y1,x2,y2]}]}')
        model = api_config.get('model', 'qwen/qwen3-vl-8b')
        inference_tool = api_config.get('inferenceTool', 'LMStudio')
        
        # 初始化AIAutoLabeler
        labeler = AIAutoLabeler(api_url, api_key, prompt, timeout, inference_tool, model)
        
        # 打开视频流
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({'success': False, 'error': f'Failed to open video: {video_path}'}), 400
        
        frame_count = 0
        processed_count = 0
        total_detections = 0
        
        # 处理视频帧
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 按照指定间隔处理帧
            if frame_count % frame_interval == 0:
                # 保存原始帧
                frame_filename = f"frame_{frame_count:06d}.jpg"
                raw_frame_path = os.path.join(raw_dir, frame_filename)
                cv2.imwrite(raw_frame_path, frame)
                
                # 调用API进行标注
                try:
                    result = labeler.analyze_image(raw_frame_path)
                    detections = result.get("detections", [])
                    if isinstance(detections, dict):
                        detections = [detections]
                except Exception as e:
                    error_msg = f"处理视频帧失败: {str(e)}"
                    logging.error(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg,
                        'processed': processed_count,
                        'detections': total_detections,
                        'output_dir': output_dir
                    }), 500
                
                # 渲染检测结果
                rendered_path = labeler.render_detections(raw_frame_path, detections)
                
                # 移动渲染后的图片到输出目录
                labeled_path = os.path.join(labeled_dir, frame_filename)
                # 如果目标文件已存在，先删除
                if os.path.exists(labeled_path):
                    os.remove(labeled_path)
                os.rename(rendered_path, labeled_path)
                
                processed_count += 1
                total_detections += len(detections)
            
            frame_count += 1
        
        # 释放资源
        cap.release()
        
        return jsonify({
            'success': True,
            'processed': processed_count,
            'detections': total_detections,
            'output_dir': output_dir
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/check-yolo11-install')
def check_yolo11_install():
    """检查YOLO11安装状态"""
    import os
    # 检查YOLO11安装路径是否存在
    yolo11_path = os.path.join(app.root_path, 'plugins', 'yolo11')
    is_installed = os.path.exists(yolo11_path) and os.path.isdir(yolo11_path)
    
    # 初始化安装信息
    install_info = {
        'is_installed': is_installed,
        'install_time': '',
        'has_cuda': False,
        'hardware': 'CPU'
    }
    
    # 如果已安装，读取详细的安装信息
    if is_installed:
        install_info_path = os.path.join(yolo11_path, 'install_info.json')
        if os.path.exists(install_info_path):
            try:
                with open(install_info_path, 'r', encoding='utf-8') as f:
                    saved_info = json.load(f)
                    # 更新安装信息
                    install_info.update(saved_info)
            except Exception as e:
                print(f"读取安装信息失败: {e}")
    
    return jsonify(install_info)


@app.route('/api/install-yolo11')
def install_yolo11():
    """安装YOLO11"""
    import os
    import subprocess
    import time
    import datetime
    import venv
    from flask import Response
    
    # 获取安装路径
    install_path = request.args.get('install_path', 'plugins/yolo11')
    # 确保安装路径是相对于项目根目录的
    if not os.path.isabs(install_path):
        install_path = os.path.join(app.root_path, install_path)
    
    def generate():
        # 发送初始状态
        yield f"data: {json.dumps({'status': 'started', 'message': '开始安装YOLO11...', 'progress': 0})}\n\n"
        time.sleep(0.5)
        
        try:
            # 1. 创建安装目录
            yield f"data: {json.dumps({'message': '创建安装目录...', 'progress': 10})}\n\n"
            os.makedirs(install_path, exist_ok=True)
            time.sleep(0.5)
            
            # 2. 创建Python虚拟环境
            yield f"data: {json.dumps({'message': '创建Python虚拟环境...', 'progress': 20})}\n\n"
            
            # 创建虚拟环境
            venv_path = os.path.join(install_path, 'venv')
            venv.create(venv_path, with_pip=True)
            time.sleep(0.5)
            
            # 3. 安装YOLO11的依赖
            yield f"data: {json.dumps({'message': '安装YOLO11依赖...', 'progress': 40})}\n\n"
            
            # 获取虚拟环境中的pip路径
            if os.name == 'nt':  # Windows
                pip_path = os.path.join(venv_path, 'Scripts', 'pip.exe')
                python_path = os.path.join(venv_path, 'Scripts', 'python.exe')
            else:  # Linux/macOS
                pip_path = os.path.join(venv_path, 'bin', 'pip')
                python_path = os.path.join(venv_path, 'bin', 'python')
            
            # 升级pip
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '--upgrade', 'pip'],
                capture_output=True,
                text=True,
                cwd=install_path
            )
            
            if result.returncode != 0:
                yield f"data: {json.dumps({'status': 'error', 'message': f'升级pip失败: {result.stderr}', 'progress': 40})}\n\n"
                return
            
            # 安装ultralytics
            result = subprocess.run(
                [pip_path, 'install', 'ultralytics'],
                capture_output=True,
                text=True,
                cwd=install_path
            )
            
            if result.returncode != 0:
                yield f"data: {json.dumps({'status': 'error', 'message': f'安装ultralytics失败: {result.stderr}', 'progress': 50})}\n\n"
                return
            
            time.sleep(0.5)
            
            # 4. 检查硬件支持
            yield f"data: {json.dumps({'message': '检查硬件支持...', 'progress': 70})}\n\n"
            
            # 检查是否支持CUDA
            has_cuda = False
            try:
                result = subprocess.run(
                    [python_path, '-c', 'import torch; print(torch.cuda.is_available())'],
                    capture_output=True,
                    text=True,
                    cwd=install_path
                )
                has_cuda = result.stdout.strip().lower() == 'true'
            except Exception as e:
                print(f"检查CUDA支持失败: {e}")
            
            time.sleep(0.5)
            
            # 5. 创建models目录
            yield f"data: {json.dumps({'message': '创建models目录...', 'progress': 80})}\n\n"
            models_dir = os.path.join(install_path, 'models')
            os.makedirs(models_dir, exist_ok=True)
            time.sleep(0.5)
            
            # 6. 记录安装信息
            yield f"data: {json.dumps({'message': '记录安装信息...', 'progress': 90})}\n\n"
            
            install_info = {
                'is_installed': True,
                'install_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'install_path': install_path,
                'has_cuda': has_cuda,
                'hardware': 'CUDA' if has_cuda else 'CPU'
            }
            
            # 保存安装信息到文件
            install_info_path = os.path.join(install_path, 'install_info.json')
            with open(install_info_path, 'w') as f:
                json.dump(install_info, f, indent=2, ensure_ascii=False)
            
            time.sleep(0.5)
            
            # 7. 安装完成
            yield f"data: {json.dumps({'message': 'YOLO11安装完成！', 'progress': 100, 'status': 'completed', 'has_cuda': has_cuda})}\n\n"
            
        except Exception as e:
            import traceback
            yield f"data: {json.dumps({'status': 'error', 'message': f'安装失败: {str(e)}', 'progress': 0, 'traceback': traceback.format_exc()})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/uninstall-yolo11')
def uninstall_yolo11():
    """卸载YOLO11"""
    import os
    import shutil
    import time
    from flask import Response
    
    # 获取安装路径
    install_path = request.args.get('install_path', 'plugins/yolo11')
    # 确保安装路径是相对于项目根目录的
    if not os.path.isabs(install_path):
        install_path = os.path.join(app.root_path, install_path)
    
    def generate():
        # 发送初始状态
        yield f"data: {json.dumps({'status': 'started', 'message': '开始卸载YOLO11...', 'progress': 0})}\n\n"
        time.sleep(0.5)
        
        try:
            # 检查YOLO11是否安装
            if not os.path.exists(install_path) or not os.path.isdir(install_path):
                yield f"data: {json.dumps({'status': 'error', 'message': 'YOLO11未安装', 'progress': 0})}\n\n"
                return
            
            # 1. 删除安装目录
            yield f"data: {json.dumps({'message': '删除YOLO11安装目录...', 'progress': 50})}\n\n"
            
            # 强制删除整个YOLO11目录，包括venv文件夹
            # 先尝试使用shutil.rmtree删除
            shutil.rmtree(install_path, ignore_errors=False)
            
            # 验证是否删除成功
            if os.path.exists(install_path):
                # 如果shutil.rmtree失败，尝试使用os.system强制删除（针对Windows系统）
                if os.name == 'nt':  # Windows系统
                    os.system(f'rmdir /s /q "{install_path}"')
                else:  # Linux/macOS系统
                    os.system(f'rm -rf "{install_path}"')
                
                # 再次验证
                if os.path.exists(install_path):
                    raise Exception(f'无法删除目录: {install_path}')
            
            time.sleep(0.5)
            
            # 2. 卸载完成
            yield f"data: {json.dumps({'message': 'YOLO11卸载完成！', 'progress': 100, 'status': 'completed'})}\n\n"
            
        except Exception as e:
            import traceback
            yield f"data: {json.dumps({'status': 'error', 'message': f'卸载失败: {str(e)}', 'progress': 0, 'traceback': traceback.format_exc()})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/download-models')
def download_models():
    """下载YOLO11预训练模型"""
    import os
    import subprocess
    import time
    from flask import Response
    
    # 获取模型列表和安装路径
    models_str = request.args.get('models', '')
    models = models_str.split(',') if models_str else []
    install_path = request.args.get('install_path', 'plugins/yolo11')
    
    # 确保安装路径是相对于项目根目录的
    if not os.path.isabs(install_path):
        install_path = os.path.join(app.root_path, install_path)
    
    def generate():
        # 发送初始状态
        yield f"data: {json.dumps({'status': 'started', 'message': '开始下载模型...', 'progress': 0})}\n\n"
        time.sleep(0.5)
        
        try:
            # 检查YOLO11是否安装
            if not os.path.exists(install_path) or not os.path.isdir(install_path):
                yield f"data: {json.dumps({'status': 'error', 'message': 'YOLO11未安装', 'progress': 0})}\n\n"
                return
            
            # 获取虚拟环境中的python路径
            if os.name == 'nt':  # Windows
                python_path = os.path.join(install_path, 'venv', 'Scripts', 'python.exe')
            else:  # Linux/macOS
                python_path = os.path.join(install_path, 'venv', 'bin', 'python')
            
            # 检查python路径是否存在
            if not os.path.exists(python_path):
                yield f"data: {json.dumps({'status': 'error', 'message': '虚拟环境未找到', 'progress': 0})}\n\n"
                return
            
            # 创建models目录
            models_dir = os.path.join(install_path, 'models')
            os.makedirs(models_dir, exist_ok=True)
            
            # 下载每个模型
            total_models = len(models)
            for i, model in enumerate(models):
                yield f"data: {json.dumps({'message': f'正在下载模型: {model}...', 'progress': int((i / total_models) * 50) + 10})}\n\n"
                
                # 使用ultralytics的CLI下载模型
                result = subprocess.run(
                    [python_path, '-c', f'from ultralytics import YOLO; YOLO("{model}.pt")'],
                    capture_output=True,
                    text=True,
                    cwd=models_dir
                )
                
                if result.returncode != 0:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'下载模型 {model} 失败: {result.stderr}', 'progress': 0})}\n\n"
                    return
                
                time.sleep(0.5)
            
            # 下载完成
            yield f"data: {json.dumps({'message': '模型下载完成！', 'progress': 100, 'status': 'completed'})}\n\n"
            
        except Exception as e:
            import traceback
            yield f"data: {json.dumps({'status': 'error', 'message': f'下载失败: {str(e)}', 'progress': 0, 'traceback': traceback.format_exc()})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/list-models')
def list_models():
    """获取已安装的YOLO11模型列表"""
    import os
    
    # 获取安装路径
    install_path = request.args.get('install_path', 'plugins/yolo11')
    # 确保安装路径是相对于项目根目录的
    if not os.path.isabs(install_path):
        install_path = os.path.join(app.root_path, install_path)
    
    # 初始化模型列表
    models = []
    
    # 检查YOLO11是否安装
    if os.path.exists(install_path) and os.path.isdir(install_path):
        # 检查models目录是否存在
        models_dir = os.path.join(install_path, 'models')
        if os.path.exists(models_dir) and os.path.isdir(models_dir):
            # 列出models目录下的所有.pt文件
            for file in os.listdir(models_dir):
                if file.endswith('.pt'):
                    models.append(file)
    
    return jsonify({'models': models})


@app.route('/api/upload-model', methods=['POST'])
def upload_model():
    """上传YOLO11模型文件"""
    import os
    
    # 获取安装路径
    install_path = request.headers.get('X-Install-Path', 'plugins/yolo11')
    # 确保安装路径是相对于项目根目录的
    if not os.path.isabs(install_path):
        install_path = os.path.join(app.root_path, install_path)
    
    # 检查YOLO11是否安装
    if not os.path.exists(install_path) or not os.path.isdir(install_path):
        return jsonify({'success': False, 'error': 'YOLO11未安装'})
    
    # 检查是否有文件上传
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'error': '未找到上传的文件'})
    
    # 创建models目录
    models_dir = os.path.join(install_path, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    # 保存上传的文件
    uploaded_files = []
    files = request.files.getlist('files[]')
    for file in files:
        if file.filename != '' and file.filename.endswith('.pt'):
            # 保存文件到models目录
            file_path = os.path.join(models_dir, file.filename)
            file.save(file_path)
            uploaded_files.append(file.filename)
    
    return jsonify({'success': True, 'uploaded_files': uploaded_files})


@app.route('/api/delete-model', methods=['POST'])
def delete_model():
    """删除YOLO11模型文件"""
    import os
    
    # 获取安装路径
    install_path = request.headers.get('X-Install-Path', 'plugins/yolo11')
    # 确保安装路径是相对于项目根目录的
    if not os.path.isabs(install_path):
        install_path = os.path.join(app.root_path, install_path)
    
    # 获取模型名称
    data = request.json or {}
    model_name = data.get('model_name', '')
    
    # 检查YOLO11是否安装
    if not os.path.exists(install_path) or not os.path.isdir(install_path):
        return jsonify({'success': False, 'error': 'YOLO11未安装'})
    
    # 检查模型名称是否为空
    if not model_name:
        return jsonify({'success': False, 'error': '模型名称不能为空'})
    
    # 构建模型文件路径
    models_dir = os.path.join(install_path, 'models')
    model_path = os.path.join(models_dir, model_name)
    
    # 检查模型文件是否存在
    if not os.path.exists(model_path):
        return jsonify({'success': False, 'error': '模型文件不存在'})
    
    try:
        # 删除模型文件
        os.remove(model_path)
        return jsonify({'success': True, 'message': f'模型 {model_name} 删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'删除模型失败: {str(e)}'})


@app.route('/api/export', methods=['POST'])
def export_dataset():
    """导出数据集"""
    try:
        import datetime
        
        data = request.json or {}
        # 确保比例值是有效的数字，处理前端可能发送的null或undefined
        train_ratio = float(data.get('train_ratio', 0.7)) if data.get('train_ratio') is not None else 0.7
        val_ratio = float(data.get('val_ratio', 0.2)) if data.get('val_ratio') is not None else 0.2
        test_ratio = float(data.get('test_ratio', 0.1)) if data.get('test_ratio') is not None else 0.1
        selected_classes = data.get('selected_classes', [])
        sample_selection = data.get('sample_selection', 'all')  # 获取样本选择参数，默认为'all'
        export_data_type = data.get('export_data_type', 'yolo')  # 获取导出数据类型参数，默认为'yolo'
        export_prefix = data.get('export_prefix', '')  # 获取导出文件前缀，默认为空字符串
        
        # 检查导出数据类型是否受支持
        if export_data_type not in ['yolo']:
            return jsonify({'error': '不支持的导出数据类型'}), 400
        
        # 前端已经检查了比例总和必须等于1，所以这里不需要再归一化
        # 直接使用前端传递的比例值
        
        # 获取全局类别列表
        classes = []
        if os.path.exists(CLASSES_FILE):
            with open(CLASSES_FILE, 'r', encoding='utf-8') as f:
                classes = json.load(f)
        
        # 创建临时目录用于生成数据集
        import tempfile
        import zipfile
        temp_dir = tempfile.mkdtemp()
        
        # 生成带时间戳的基础名称，格式：datasets_年月日时分秒
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        base_name = f"datasets_{timestamp}"
        
        # 不管有没有前缀，zip文件名和内部文件夹名称都使用datasets_年月日时分秒格式
        yolo_base = os.path.join(temp_dir, base_name)
        
        # 创建符合YOLOv11格式的目录结构
        for split in ['train', 'val', 'test']:
            os.makedirs(os.path.join(yolo_base, split, 'images'), exist_ok=True)
            os.makedirs(os.path.join(yolo_base, split, 'labels'), exist_ok=True)
        
        # 获取所有图片
        images = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                images.append(filename)
        
        # 根据样本选择参数过滤图片
        annotations = {}
        if os.path.exists(ANNOTATIONS_FILE):
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
        
        # 根据用户选择过滤图片
        if sample_selection == 'annotated':
            # 只选择有标注的图片
            images = [img for img in images if img in annotations and annotations[img]]
        elif sample_selection == 'unannotated':
            # 只选择没有标注的图片
            images = [img for img in images if img not in annotations or not annotations[img]]
        # 如果是'all'则不进行过滤，使用所有图片
        
        # 分割数据集
        np.random.shuffle(images)
        
        total_images = len(images)
        
        # 彻底重写数据集分割逻辑，确保严格按照比例分割
        # 0比例的数据集绝对为空，多余的数据直接扔掉
        train_images = []
        val_images = []
        test_images = []
        
        # 只处理比例大于0的数据集
        if train_ratio > 0:
            # 计算训练集数量
            train_count = int(total_images * train_ratio)
            # 只分配计算出的数量的图片
            train_images = images[:train_count]
        
        # 验证集只在train_ratio > 0时才处理，否则从0开始
        val_start = len(train_images) if train_ratio > 0 else 0
        if val_ratio > 0:
            # 计算验证集数量
            val_count = int(total_images * val_ratio)
            # 只分配计算出的数量的图片
            val_images = images[val_start:val_start + val_count]
        
        # 测试集只在train_ratio > 0或val_ratio > 0时才处理，否则从0开始
        test_start = (len(train_images) + len(val_images)) if (train_ratio > 0 or val_ratio > 0) else 0
        if test_ratio > 0:
            # 计算测试集数量
            test_count = int(total_images * test_ratio)
            # 只分配计算出的数量的图片
            test_images = images[test_start:test_start + test_count]
        
        # 确保0比例的数据集绝对为空
        if train_ratio == 0:
            train_images = []
        if val_ratio == 0:
            val_images = []
        if test_ratio == 0:
            test_images = []
        
        # 处理每个分割的数据集
        splits = [
            ('train', train_images),
            ('val', val_images),
            ('test', test_images)
        ]
        
        # 创建数据集配置文件 (YOLOv11格式)
        data_yaml = f"""path: .
train: train/images
val: val/images
test: test/images

nc: {len(selected_classes)}
names: {selected_classes}
"""
        
        with open(os.path.join(yolo_base, 'data.yaml'), 'w') as f:
            f.write(data_yaml)
        
        # 复制图片和生成标签文件
        for split_name, split_images in splits:
            for image_name in split_images:
                # 复制图片，添加前缀
                src_img_path = os.path.join(app.config['UPLOAD_FOLDER'], image_name)
                if export_prefix:
                    dst_img_name = f"{export_prefix}_{image_name}"
                else:
                    dst_img_name = image_name
                dst_img_path = os.path.join(yolo_base, split_name, 'images', dst_img_name)
                
                # 使用PIL读取图片尺寸
                try:
                    img = Image.open(src_img_path)
                    width, height = img.size
                except Exception as e:
                    print(f"无法读取图片 {src_img_path}: {str(e)}")
                    continue
                
                # 复制图片文件
                from shutil import copyfile
                copyfile(src_img_path, dst_img_path)
                
                # 生成YOLO格式的标签文件，添加前缀
                base_name = os.path.splitext(image_name)[0]
                if export_prefix:
                    label_name = f"{export_prefix}_{base_name}.txt"
                else:
                    label_name = f"{base_name}.txt"
                label_path = os.path.join(yolo_base, split_name, 'labels', label_name)
                
                image_annotations = annotations.get(image_name, [])
                
                # 对于未标注的图片，创建空的标签文件；对于标注的图片，写入标注信息
                with open(label_path, 'w') as f:
                    # 只有当是标注图片并且选择了相关类别时才写入标注信息
                    if image_annotations and sample_selection != 'unannotated':
                        for ann in image_annotations:
                            # 只导出选中的类别
                            if ann['class'] in selected_classes:
                                # 转换为YOLO格式: class_id center_x center_y width height (归一化)
                                # 修改这里，使用全局类别列表中的索引而不是选中类别列表中的索引
                                class_id = None
                                # 从全局类别列表中查找类别ID
                                for i, cls in enumerate(classes):
                                    if cls['name'] == ann['class']:
                                        class_id = i
                                        break
                                
                                # 如果在全局类别中找到了该类别，则写入标签文件
                                if class_id is not None:
                                    points = ann.get('points', [])
                                    
                                    # 处理不同格式的points数据
                                    if isinstance(points, list) and len(points) > 0:
                                        # 检查points是坐标对的数组还是对象数组
                                        valid_points = []
                                        if isinstance(points[0], dict):
                                            # 对象数组格式 [{x: ..., y: ...}, ...]
                                            for point in points:
                                                if 'x' in point and 'y' in point and point['x'] is not None and point['y'] is not None:
                                                    valid_points.append([point['x'], point['y']])
                                        else:
                                            # 坐标对数组格式 [[x, y], ...]
                                            for point in points:
                                                if isinstance(point, (list, tuple)) and len(point) >= 2 and point[0] is not None and point[1] is not None:
                                                    valid_points.append([point[0], point[1]])
                                            
                                        if len(valid_points) > 0:
                                            points = np.array(valid_points)
                                            
                                            x_min = np.min(points[:, 0])
                                            y_min = np.min(points[:, 1])
                                            x_max = np.max(points[:, 0])
                                            y_max = np.max(points[:, 1])
                                            
                                            # 确保坐标值有效
                                            if x_min is not None and y_min is not None and x_max is not None and y_max is not None:
                                                # 转换为YOLO格式
                                                center_x = ((x_min + x_max) / 2) / width
                                                center_y = ((y_min + y_max) / 2) / height
                                                bbox_width = (x_max - x_min) / width
                                                bbox_height = (y_max - y_min) / height
                                                
                                                f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {bbox_width:.6f} {bbox_height:.6f}\n")
                                    elif 'x' in ann and 'y' in ann and 'width' in ann and 'height' in ann:
                                        # 处理矩形格式的标注数据
                                        x = ann['x']
                                        y = ann['y']
                                        w = ann['width']
                                        h = ann['height']
                                        
                                        # 确保所有值都是有效的数字
                                        if x is not None and y is not None and w is not None and h is not None:
                                            x_min = x
                                            y_min = y
                                            x_max = x + w
                                            y_max = y + h
                                            
                                            # 转换为YOLO格式
                                            center_x = ((x_min + x_max) / 2) / width
                                            center_y = ((y_min + y_max) / 2) / height
                                            bbox_width = (x_max - x_min) / width
                                            bbox_height = (y_max - y_min) / height
                                            
                                            f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {bbox_width:.6f} {bbox_height:.6f}\n")
                                    else:
                                        # points数据格式无效，跳过该标注
                                        print(f"Invalid points data for annotation: {ann}")
                    # 对于未标注的图片，文件将保持为空（只需创建文件）
        
        # 创建zip文件，使用带时间戳的名称
        zip_filename = f"{base_name}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(yolo_base):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 使用yolo_base作为基准路径，这样zip文件中的目录结构就是直接的train/images/xxx.jpg
                    arc_name = os.path.relpath(file_path, yolo_base)
                    zipf.write(file_path, arc_name)
        
        # 返回zip文件
        return send_from_directory(temp_dir, zip_filename, as_attachment=True, download_name=zip_filename)
        
    except Exception as e:
        import traceback
        print(f"Export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# 异步视频标注相关API
@app.route('/api/auto-label/video/start', methods=['POST'])
def start_video_annotation():
    """启动视频标注任务"""
    try:
        import os
        
        # 获取请求数据
        data = request.json
        video_path = data.get('video_path')
        frame_interval = int(data.get('frame_interval', 10))
        output_dir = data.get('output_dir', 'output')
        api_config = data.get('api_config', {})
        
        if not video_path:
            return jsonify({'success': False, 'error': 'No video path provided'}), 400
        
        # 创建唯一任务ID
        task_id = str(uuid.uuid4())
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建视频标注任务
        task = VideoAnnotationTask(task_id, video_path, frame_interval, output_dir, api_config)
        
        # 保存任务到任务列表
        tasks[task_id] = task
        
        # 启动任务
        task.start()
        
        # 从请求上下文获取当前连接ID
        # 在API请求中，request对象来自flask，不直接包含socketio sid
        # 因此在API请求中我们无法直接获取socketio sid
        # 这里使用特殊的方式获取，通过flask的request对象的环境变量
        sid = None
        if hasattr(request, 'environ') and 'flask_socketio.sid' in request.environ:
            sid = request.environ['flask_socketio.sid']
        
        if sid:
            # 存储连接ID和任务ID的映射关系
            connection_task_map[sid] = task_id
            print(f"关联连接ID {sid} 到任务ID {task_id}")
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Video annotation task started successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auto-label/video/stop', methods=['POST'])
def stop_video_annotation():
    """停止视频标注任务"""
    try:
        # 获取请求数据
        data = request.json
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({'success': False, 'error': 'No task ID provided'}), 400
        
        # 查找任务
        if task_id not in tasks:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        # 停止任务
        task = tasks[task_id]
        task.stop()
        
        # 不要立即从任务列表中移除任务，让任务线程自己完成清理工作
        # 任务线程会在完成后发送最终的进度更新
        
        return jsonify({
            'success': True,
            'message': 'Video annotation task stopped successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auto-label/video/status/<task_id>', methods=['GET'])
def get_video_annotation_status(task_id):
    """获取视频标注任务状态"""
    try:
        # 查找任务
        if task_id not in tasks:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        
        # 获取任务状态
        task = tasks[task_id]
        status = task.get_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# SocketIO事件处理
@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect(sid):
    """处理客户端断开连接"""
    print(f'Client disconnected: {sid}')
    
    # 检查该连接是否有关联的任务
    if sid in connection_task_map:
        task_id = connection_task_map[sid]
        print(f'检测到断开连接的客户端有关联任务: {task_id}')
        
        # 检查任务是否存在且正在运行
        if task_id in tasks:
            task = tasks[task_id]
            if task.status == TASK_STATUS['RUNNING']:
                # 停止任务
                print(f'自动停止任务: {task_id}')
                task.stop()
        
        # 从映射字典中移除该连接
        del connection_task_map[sid]
        print(f'移除连接和任务的关联: {sid} -> {task_id}')

if __name__ == '__main__':
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='xclabel图像标注工具')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='绑定的IP地址，默认0.0.0.0')
    parser.add_argument('--port', type=int, default=5000, help='绑定的端口，默认5000')
    parser.add_argument('--debug', action='store_true', default=True, help='启用调试模式，默认开启')
    args = parser.parse_args()
    
    # 使用SocketIO运行应用，使用命令行参数
    socketio.run(app, debug=args.debug, host=args.host, port=args.port)


def process_content_data(content_data, annotations):
    """处理内容数据并提取标注"""
    print(f"处理内容数据: {content_data}")
    # TODO: 在这里添加您的自定义处理代码

def process_list_data(data_list, annotations):
    """处理列表数据并提取标注"""
    print(f"处理列表数据: {data_list}")
    # TODO: 在这里添加您的自定义处理代码
