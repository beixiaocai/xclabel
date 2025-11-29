import os
import json
import math
import numpy as np
import base64
import traceback
import cv2
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image
from openai import OpenAI

# OpenAI库用于调用DashScope API
OPENAI_AVAILABLE = True

app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = 'uploads'
DATASET_FOLDER = 'datasets'
STATIC_FOLDER = 'static'
ANNOTATIONS_FOLDER = os.path.join(STATIC_FOLDER, 'annotations')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATASET_FOLDER'] = DATASET_FOLDER
app.config['STATIC_FOLDER'] = STATIC_FOLDER
app.config['ANNOTATIONS_FOLDER'] = ANNOTATIONS_FOLDER

# 创建必要的目录
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATASET_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)
os.makedirs(ANNOTATIONS_FOLDER, exist_ok=True)

# 模拟数据库存储标注信息
ANNOTATIONS_FILE = os.path.join(ANNOTATIONS_FOLDER, 'annotations.json')
CLASSES_FILE = os.path.join(ANNOTATIONS_FOLDER, 'classes.json')

# 初始化注释文件
if not os.path.exists(ANNOTATIONS_FILE):
    with open(ANNOTATIONS_FILE, 'w') as f:
        json.dump({}, f)
        
# 初始化类别文件
if not os.path.exists(CLASSES_FILE):
    # 默认类别
    default_classes = [
        {'name': 'person', 'color': '#3aa757'},
        {'name': 'car', 'color': '#4c9ffd'},
        {'name': 'animal', 'color': '#ff9d00'}
    ]
    with open(CLASSES_FILE, 'w') as f:
        json.dump(default_classes, f)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/classes')
def get_classes():
    """获取所有类别"""
    classes = []
    if os.path.exists(CLASSES_FILE):
        with open(CLASSES_FILE, 'r') as f:
            classes = json.load(f)
    return jsonify(classes)


@app.route('/api/classes', methods=['POST'])
def save_classes():
    """保存所有类别"""
    data = request.json
    
    with open(CLASSES_FILE, 'w') as f:
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
            with open(ANNOTATIONS_FILE, 'r') as f:
                annotations = json.load(f)
        except json.JSONDecodeError:
            # 如果JSON文件无效或为空，使用空字典
            annotations = {}
        except Exception as e:
            # 处理其他可能的错误
            print(f"Error reading annotations file: {e}")
            annotations = {}
    
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            # 获取图片尺寸信息
            try:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
                    with open(ANNOTATIONS_FILE, 'r') as f:
                        annotations = json.load(f)
                    
                    if image_name in annotations:
                        del annotations[image_name]
                        with open(ANNOTATIONS_FILE, 'w') as f:
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


@app.route('/api/image/<filename>')
def get_image(filename):
    """获取指定图片"""
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
            with open(CLASSES_FILE, 'r') as f:
                classes = json.load(f)
        
        annotations = {}
        if os.path.exists(ANNOTATIONS_FILE):
            with open(ANNOTATIONS_FILE, 'r') as f:
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
        with open(CLASSES_FILE, 'w') as f:
            json.dump(classes, f, indent=2)
        
        with open(ANNOTATIONS_FILE, 'w') as f:
            json.dump(annotations, f, indent=2)
        
        return jsonify({
            'message': 'LabelMe dataset uploaded successfully', 
            'files': uploaded_files,
            'annotations_processed': processed_annotations
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process LabelMe dataset: {str(e)}'}), 500


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
        
        # 抽帧处理
        extracted_frames = extract_frames(temp_video_path, frame_interval)
        
        # 删除临时视频文件
        os.remove(temp_video_path)
        
        return jsonify({
            'message': 'Video frames extracted successfully', 
            'frames': extracted_frames,
            'count': len(extracted_frames)
        })
    except Exception as e:
        return jsonify({'error': f'Failed to process video: {str(e)}'}), 500


def extract_frames(video_path, frame_interval):
    """从视频中抽帧并保存为图片"""
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    saved_frame_count = 0
    extracted_frames = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # 每隔frame_interval帧保存一帧
        if frame_count % frame_interval == 0:
            # 生成文件名
            video_name = os.path.splitext(os.path.basename(video_path))[0]
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
            with open(ANNOTATIONS_FILE, 'r') as f:
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
            with open(ANNOTATIONS_FILE, 'r') as f:
                annotations = json.load(f)
        except json.JSONDecodeError:
            # 如果JSON文件无效或为空，使用空字典
            annotations = {}
        except Exception as e:
            # 处理其他可能的错误
            print(f"Error reading annotations file: {e}")
            annotations = {}
    
    annotations[image_name] = data
    
    with open(ANNOTATIONS_FILE, 'w') as f:
        json.dump(annotations, f, indent=2)
    
    return jsonify({'message': 'Annotations saved successfully'})


@app.route('/api/ai-annotate', methods=['POST'])
def ai_annotate():
    """执行AI自动标注 - 已停用"""
    return jsonify({
        'error': 'AI自动标注功能已停用',
        'details': '管理员已停用此功能'
    }), 400


@app.route('/api/export', methods=['POST'])
def export_dataset():
    """导出数据集"""
    try:
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
            with open(CLASSES_FILE, 'r') as f:
                classes = json.load(f)
        
        # 创建临时目录用于生成数据集
        import tempfile
        import zipfile
        temp_dir = tempfile.mkdtemp()
        yolo_base = os.path.join(temp_dir, 'yolo_dataset')
        
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
            with open(ANNOTATIONS_FILE, 'r') as f:
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
        
        # 创建zip文件，添加前缀
        if export_prefix:
            zip_filename = f"{export_prefix}_yolo_dataset.zip"
        else:
            zip_filename = "yolo_dataset.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(yolo_base):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arc_name)
        
        # 返回zip文件
        return send_from_directory(temp_dir, zip_filename, as_attachment=True, download_name=zip_filename)
        
    except Exception as e:
        import traceback
        print(f"Export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def process_content_data(content_data, annotations):
    """处理内容数据并提取标注"""
    print(f"处理内容数据: {content_data}")
    # TODO: 在这里添加您的自定义处理代码

def process_list_data(data_list, annotations):
    """处理列表数据并提取标注"""
    print(f"处理列表数据: {data_list}")
    # TODO: 在这里添加您的自定义处理代码
