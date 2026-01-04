﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿
let currentImage = null;
let currentAnnotations = [];
let classes = [];
let isDrawing = false;
let startPoint = null;
let currentPoint = null;
let currentTool = 'rect'; // 默认工具
let imageCache = new Map(); // 图片缓存
let selectedAnnotationId = null; // 当前选中的标注ID
let isResizing = false; // 是否正在调整大小
let isMoving = false; // 是否正在移动标注
let resizeHandle = null; // 当前调整大小的控制点
let lastMousePos = null; // 上次鼠标位置
let polygonPoints = []; // 多边形绘制时的顶点数组
let isPolygonDrawing = false; // 是否正在绘制多边形
let updateAnnotationListDebounced = debounce(updateAnnotationList, 100); // 防抖后的标注列表更新函数

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// 初始化应用
function initializeApp() {
    loadClasses();
    loadImages();
    loadShortcutSettings();
    setupEventListeners();
}

// 设置事件监听器
function setupEventListeners() {
    // 导航按钮
    document.getElementById('openFolderBtn').addEventListener('click', showDatasetModal);
    document.getElementById('exportBtn').addEventListener('click', showExportModal);
    document.getElementById('settingsBtn').addEventListener('click', showSettingsModal);
    document.getElementById('clearAnnotationBtn').addEventListener('click', clearCurrentAnnotations);
    // 自动标注按钮
    document.getElementById('autoLabelBtn').addEventListener('click', function() {
        window.location.href = '/auto-label';
    });
    document.getElementById('saveAnnotationBtn').addEventListener('click', saveAnnotations);
    
    // 搜索框
    document.getElementById('imageSearch').addEventListener('input', filterImages);
    
    // 工具按钮
    document.getElementById('rectTool').addEventListener('click', () => switchTool('rect'));
    document.getElementById('polygonTool').addEventListener('click', () => switchTool('polygon'));
    document.getElementById('moveTool').addEventListener('click', () => switchTool('move'));
    
    // 类别管理
    document.getElementById('addClassBtn').addEventListener('click', addClass);
    document.getElementById('newClassInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') addClass();
    });
    
    // 画布事件
    const canvas = document.getElementById('imageCanvas');
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseLeave);
    canvas.addEventListener('dblclick', handleDoubleClick);
    
    // 模态框关闭事件
    setupModalCloseEvents();
    
    // 数据集上传事件
    setupDatasetUploadEvents();
    
    // 导出表单事件
    document.getElementById('exportForm').addEventListener('submit', handleExport);
    
    // 设置表单事件
    document.getElementById('settingsForm').addEventListener('submit', handleSettingsSave);
    
    // 编辑类别表单事件
    document.getElementById('editClassForm').addEventListener('submit', handleEditClass);
    
    // YOLO11安装和卸载按钮事件
    document.getElementById('installYolo11Btn').addEventListener('click', installYolo11);
    document.getElementById('uninstallYolo11Btn').addEventListener('click', uninstallYolo11);
    
    // YOLO11模型管理按钮事件
    document.getElementById('downloadModelsBtn').addEventListener('click', downloadModels);
    document.getElementById('refreshModelsBtn').addEventListener('click', refreshModels);
    
    // YOLO11模型拖放事件
    setupModelDropZoneEvents();
    
    // 快捷键
    document.addEventListener('keydown', handleKeyDown);
    
    // 全选和删除按钮
    document.getElementById('selectAllBtn').addEventListener('click', selectAllImages);
    document.getElementById('deleteSelectedBtn').addEventListener('click', deleteSelectedImages);
}



// 切换工具
function switchTool(tool) {
    // 更新UI状态
    document.querySelectorAll('.tool-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(tool + 'Tool').classList.add('active');
    
    // 重置所有绘制状态
    isDrawing = false;
    isPolygonDrawing = false;
    startPoint = null;
    currentPoint = null;
    polygonPoints = [];
    
    // 设置当前工具
    currentTool = tool;
    
    // 更新鼠标样式
    const canvas = document.getElementById('imageCanvas');
    canvas.style.cursor = 'crosshair';
    
    redrawCanvas();
}

// 处理鼠标按下事件
function handleMouseDown(e) {
    if (!currentImage) return;
    
    const rect = e.target.getBoundingClientRect();
    const canvas = e.target;
    
    // 获取图片的实际尺寸和位置
    const img = imageCache.get(currentImage);
    if (!img) return;
    
    // 计算图片在画布上的显示尺寸和位置（自适应居中）
    const container = document.getElementById('imageCanvasContainer');
    const maxWidth = container.clientWidth - 20;
    const maxHeight = container.clientHeight - 20;
    const ratio = Math.min(maxWidth / img.width, maxHeight / img.height);
    const scaledWidth = img.width * ratio;
    const scaledHeight = img.height * ratio;
    const imgX = (container.clientWidth - scaledWidth) / 2;
    const imgY = (container.clientHeight - scaledHeight) / 2;
    
    // 计算鼠标在画布上的坐标
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;
    
    // 计算鼠标在图片上的实际坐标
    const x = (canvasX - imgX) / ratio;
    const y = (canvasY - imgY) / ratio;
    
    // 检查是否点击了某个标注的控制点
    const resizeResult = checkResizeHandleClick(canvasX, canvasY, ratio, imgX, imgY);
    if (resizeResult) {
        isResizing = true;
        resizeHandle = resizeResult.handle;
        selectedAnnotationId = resizeResult.annotationId;
        lastMousePos = {x: e.clientX, y: e.clientY};
        updateAnnotationListDebounced();
        redrawCanvas();
        return;
    }
    
    // 检查是否点击了某个标注
    const annotationResult = checkAnnotationClick(canvasX, canvasY, ratio, imgX, imgY);
    if (annotationResult) {
        selectedAnnotationId = annotationResult.id;
        isMoving = true;
        lastMousePos = {x: e.clientX, y: e.clientY};
        updateAnnotationListDebounced();
        redrawCanvas();
        return;
    }
    
    // 如果点击了空白区域，取消选择
    selectedAnnotationId = null;
    updateAnnotationListDebounced();
    redrawCanvas();
    // 处理多边形绘制
    if (currentTool === 'polygon') {
        // 如果还没有开始绘制多边形，初始化
        if (!isPolygonDrawing) {
            isPolygonDrawing = true;
            polygonPoints = [];
        }
        
        // 添加当前点到多边形顶点数组
        polygonPoints.push({x: x, y: y});
        
        // 更新当前点用于绘制
        currentPoint = {x: x, y: y};
        
        redrawCanvas();
        return;
    }
    
    // 处理矩形绘制
    if (currentTool === 'rect') {
        // 绘制工具 - 开始绘制
        isDrawing = true;
        startPoint = {x: x, y: y};
        currentPoint = {x: x, y: y};
        redrawCanvas();
    }
}

// 检查是否点击了调整大小的控制点
function checkResizeHandleClick(canvasX, canvasY, ratio, imgX, imgY) {
    for (const annotation of currentAnnotations) {
        if (annotation.type !== 'rectangle' || annotation.points.length < 4) continue;
        
        // 计算矩形的四个角点
        const points = annotation.points;
        const x1 = points[0][0] * ratio + imgX;
        const y1 = points[0][1] * ratio + imgY;
        const x2 = points[2][0] * ratio + imgX;
        const y2 = points[2][1] * ratio + imgY;
        
        // 控制点位置
        const handles = [
            { x: x1, y: y1, type: 'nw' },
            { x: (x1 + x2) / 2, y: y1, type: 'n' },
            { x: x2, y: y1, type: 'ne' },
            { x: x2, y: (y1 + y2) / 2, type: 'e' },
            { x: x2, y: y2, type: 'se' },
            { x: (x1 + x2) / 2, y: y2, type: 's' },
            { x: x1, y: y2, type: 'sw' },
            { x: x1, y: (y1 + y2) / 2, type: 'w' }
        ];
        
        // 检查是否点击了某个控制点
        for (const handle of handles) {
            const distance = Math.sqrt(
                Math.pow(canvasX - handle.x, 2) + Math.pow(canvasY - handle.y, 2)
            );
            if (distance <= 8) {
                return { annotationId: annotation.id, handle: handle.type };
            }
        }
    }
    return null;
}

// 检查是否点击了某个标注
function checkAnnotationClick(canvasX, canvasY, ratio, imgX, imgY) {
    for (const annotation of currentAnnotations) {
        if (annotation.type !== 'rectangle' || annotation.points.length < 4) continue;
        
        // 计算矩形的边界
        const points = annotation.points;
        const x1 = points[0][0] * ratio + imgX;
        const y1 = points[0][1] * ratio + imgY;
        const x2 = points[2][0] * ratio + imgX;
        const y2 = points[2][1] * ratio + imgY;
        
        // 检查鼠标是否在矩形内部
        if (canvasX >= x1 && canvasX <= x2 && canvasY >= y1 && canvasY <= y2) {
            return annotation;
        }
    }
    return null;
}

// 处理鼠标移动事件
function handleMouseMove(e) {
    if (!currentImage) return;
    
    const rect = e.target.getBoundingClientRect();
    const canvas = e.target;
    
    // 获取图片的实际尺寸和位置
    const img = imageCache.get(currentImage);
    if (!img) return;
    
    // 计算图片在画布上的显示尺寸和位置（自适应居中）
    const container = document.getElementById('imageCanvasContainer');
    const maxWidth = container.clientWidth - 20;
    const maxHeight = container.clientHeight - 20;
    const ratio = Math.min(maxWidth / img.width, maxHeight / img.height);
    const scaledWidth = img.width * ratio;
    const scaledHeight = img.height * ratio;
    const imgX = (container.clientWidth - scaledWidth) / 2;
    const imgY = (container.clientHeight - scaledHeight) / 2;
    
    // 计算鼠标在画布上的坐标
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;
    
    // 计算鼠标在图片上的实际坐标
    const x = (canvasX - imgX) / ratio;
    const y = (canvasY - imgY) / ratio;
    
    // 处理调整大小
    if (isResizing && selectedAnnotationId && resizeHandle) {
        if (!lastMousePos) return;
        
        const dx = (e.clientX - lastMousePos.x) / ratio;
        const dy = (e.clientY - lastMousePos.y) / ratio;
        
        resizeAnnotation(selectedAnnotationId, resizeHandle, dx, dy);
        lastMousePos = {x: e.clientX, y: e.clientY};
        redrawCanvas();
        return;
    }
    
    // 处理移动标注
    if (isMoving && selectedAnnotationId) {
        if (!lastMousePos) return;
        
        const dx = (e.clientX - lastMousePos.x) / ratio;
        const dy = (e.clientY - lastMousePos.y) / ratio;
        
        moveAnnotation(selectedAnnotationId, dx, dy);
        lastMousePos = {x: e.clientX, y: e.clientY};
        redrawCanvas();
        return;
    }
    
    // 处理多边形绘制过程中的鼠标移动
    if (isPolygonDrawing) {
        // 更新当前鼠标位置，用于绘制从最后一个顶点到当前鼠标位置的连线
        currentPoint = {x: x, y: y};
        redrawCanvas();
        return;
    }
    
    // 处理矩形绘制过程中的鼠标移动
    if (isDrawing) {
        // 更新当前点
        currentPoint = {x: x, y: y};
        redrawCanvas();
    } else if (currentTool === 'rect' || currentTool === 'polygon') {
        // 绘制十字引导线，但不重绘画布以避免闪烁
        drawCrosshair(e);
    }
}

// 调整标注大小
function resizeAnnotation(annotationId, handle, dx, dy) {
    const annotation = currentAnnotations.find(a => a.id === annotationId);
    if (!annotation || annotation.type !== 'rectangle') return;
    
    const points = annotation.points;
    if (points.length < 4) return;
    
    // 计算当前矩形的边界
    let x1 = points[0][0];
    let y1 = points[0][1];
    let x2 = points[2][0];
    let y2 = points[2][1];
    
    // 根据不同的控制点调整矩形大小
    switch (handle) {
        case 'nw': // 左上
            x1 += dx;
            y1 += dy;
            break;
        case 'n': // 上中
            y1 += dy;
            break;
        case 'ne': // 右上
            x2 += dx;
            y1 += dy;
            break;
        case 'e': // 右中
            x2 += dx;
            break;
        case 'se': // 右下
            x2 += dx;
            y2 += dy;
            break;
        case 's': // 下中
            y2 += dy;
            break;
        case 'sw': // 左下
            x1 += dx;
            y2 += dy;
            break;
        case 'w': // 左中
            x1 += dx;
            break;
    }
    
    // 确保矩形的宽高为正
    if (x2 < x1) [x1, x2] = [x2, x1];
    if (y2 < y1) [y1, y2] = [y2, y1];
    
    // 更新矩形的四个角点
    annotation.points = [
        [x1, y1],
        [x2, y1],
        [x2, y2],
        [x1, y2]
    ];
}

// 移动标注
function moveAnnotation(annotationId, dx, dy) {
    const annotation = currentAnnotations.find(a => a.id === annotationId);
    if (!annotation) return;
    
    // 更新所有点的坐标
    annotation.points = annotation.points.map(point => [
        point[0] + dx,
        point[1] + dy
    ]);
}

// 处理鼠标抬起事件
function handleMouseUp(e) {
    if (!currentImage) return;
    
    // 结束调整大小
    if (isResizing) {
        isResizing = false;
        resizeHandle = null;
        saveAnnotations();
        return;
    }
    
    // 结束移动标注
    if (isMoving) {
        isMoving = false;
        saveAnnotations();
        return;
    }
    
    // 处理矩形绘制完成
    if (isDrawing && startPoint && currentPoint && currentTool === 'rect') {
        // 矩形工具 - 创建矩形标注
        const width = Math.abs(currentPoint.x - startPoint.x);
        const height = Math.abs(currentPoint.y - startPoint.y);
        const minX = Math.min(startPoint.x, currentPoint.x);
        const minY = Math.min(startPoint.y, currentPoint.y);
        
        if (width > 5 && height > 5) { // 避免误触创建太小的矩形
            const selectedClass = getSelectedClass();
            if (selectedClass) {
                const annotation = {
                    id: Date.now(),
                    class: selectedClass.name,
                    points: [
                        [minX, minY],
                        [minX + width, minY],
                        [minX + width, minY + height],
                        [minX, minY + height]
                    ],
                    type: 'rectangle'
                };
                currentAnnotations.push(annotation);
                saveAnnotations();
                updateAnnotationList();
            }
        }
        isDrawing = false;
        startPoint = null;
        currentPoint = null;
        redrawCanvas();
    }
}

// 处理双击事件，完成多边形绘制
function handleDoubleClick(e) {
    if (!currentImage || currentTool !== 'polygon' || !isPolygonDrawing || polygonPoints.length < 3) return;
    
    // 完成多边形绘制
    const selectedClass = getSelectedClass();
    if (selectedClass) {
        // 将多边形顶点转换为所需格式
        const points = polygonPoints.map(point => [point.x, point.y]);
        
        const annotation = {
            id: Date.now(),
            class: selectedClass.name,
            points: points,
            type: 'polygon'
        };
        
        currentAnnotations.push(annotation);
        saveAnnotations();
        updateAnnotationListDebounced();
    }
    
    // 重置多边形绘制状态
    isPolygonDrawing = false;
    polygonPoints = [];
    currentPoint = null;
    
    redrawCanvas();
}

// 处理鼠标离开画布事件
function handleMouseLeave() {
    if (isDrawing) {
        isDrawing = false;
        startPoint = null;
        currentPoint = null;
        redrawCanvas();
    }
    
    // 如果正在绘制多边形，重置绘制状态
    if (isPolygonDrawing) {
        isPolygonDrawing = false;
        polygonPoints = [];
        currentPoint = null;
        redrawCanvas();
    }
}

// 获取选中的类别
function getSelectedClass() {
    const selectedElement = document.querySelector('.class-item.selected');
    if (!selectedElement) return null;
    
    const className = selectedElement.querySelector('.class-name').textContent;
    return classes.find(c => c.name === className);
}

// 重绘画布
function redrawCanvas() {
    const canvas = document.getElementById('imageCanvas');
    const ctx = canvas.getContext('2d');
    const container = document.getElementById('imageCanvasContainer');
    
    // 设置画布尺寸为容器大小
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    
    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (!currentImage) return;
    
    // 使用图像缓存避免重复加载
    if (!imageCache.has(currentImage)) {
        const img = new Image();
        img.onload = function() {
            imageCache.set(currentImage, img);
            drawImageAndAnnotations(ctx, img, container);
        };
        img.src = `/api/image/${currentImage}`;
    } else {
        const img = imageCache.get(currentImage);
        drawImageAndAnnotations(ctx, img, container);
    }
}

function drawImageAndAnnotations(ctx, img, container) {
    // 计算图片在画布上的显示尺寸和位置（自适应居中）
    const maxWidth = container.clientWidth - 20;
    const maxHeight = container.clientHeight - 20;
    const ratio = Math.min(maxWidth / img.width, maxHeight / img.height);
    const scaledWidth = img.width * ratio;
    const scaledHeight = img.height * ratio;
    const imgX = (container.clientWidth - scaledWidth) / 2;
    const imgY = (container.clientHeight - scaledHeight) / 2;
    
    // 绘制图片
    ctx.drawImage(img, imgX, imgY, scaledWidth, scaledHeight);
    
    // 绘制所有标注
    currentAnnotations.forEach(annotation => {
        drawAnnotation(ctx, annotation, ratio, ratio, imgX, imgY);
    });
    
    // 绘制当前正在绘制的形状
    if (isDrawing && startPoint && currentPoint && currentTool === 'rect') {
        // 设置绘制样式为实线
        ctx.strokeStyle = '#ff0000';
        ctx.lineWidth = 2;
        ctx.setLineDash([]); // 使用实线而不是虚线
        
        // 计算实际绘制的矩形坐标（考虑缩放和偏移）
        const rectX = startPoint.x * ratio + imgX;
        const rectY = startPoint.y * ratio + imgY;
        const rectWidth = (currentPoint.x - startPoint.x) * ratio;
        const rectHeight = (currentPoint.y - startPoint.y) * ratio;
        
        ctx.strokeRect(rectX, rectY, rectWidth, rectHeight);
        
        // 绘制控制点
        drawControlPoints(ctx, 
            {x: startPoint.x * ratio + imgX, y: startPoint.y * ratio + imgY}, 
            {x: currentPoint.x * ratio + imgX, y: currentPoint.y * ratio + imgY}
        );
    }
    
    // 绘制多边形
    if (isPolygonDrawing && polygonPoints.length > 0) {
        ctx.save();
        ctx.strokeStyle = '#ff0000';
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        
        // 1. 绘制连线（从第一个点到当前鼠标位置）
        ctx.beginPath();
        
        // 绘制已添加的顶点之间的连线
        for (let i = 0; i < polygonPoints.length; i++) {
            const point = polygonPoints[i];
            const canvasX = point.x * ratio + imgX;
            const canvasY = point.y * ratio + imgY;
            
            if (i === 0) {
                ctx.moveTo(canvasX, canvasY);
            } else {
                ctx.lineTo(canvasX, canvasY);
            }
        }
        
        // 绘制从最后一个点到当前鼠标位置的连线
        if (currentPoint && polygonPoints.length > 0) {
            const lastPoint = polygonPoints[polygonPoints.length - 1];
            const lastCanvasX = lastPoint.x * ratio + imgX;
            const lastCanvasY = lastPoint.y * ratio + imgY;
            const currentCanvasX = currentPoint.x * ratio + imgX;
            const currentCanvasY = currentPoint.y * ratio + imgY;
            
            ctx.moveTo(lastCanvasX, lastCanvasY);
            ctx.lineTo(currentCanvasX, currentCanvasY);
        }
        
        ctx.stroke();
        
        // 2. 绘制已添加的顶点
        ctx.fillStyle = '#ff0000';
        for (const point of polygonPoints) {
            const canvasX = point.x * ratio + imgX;
            const canvasY = point.y * ratio + imgY;
            
            ctx.beginPath();
            ctx.arc(canvasX, canvasY, 4, 0, Math.PI * 2);
            ctx.fill();
        }
        
        ctx.restore();
    }
}

// 绘制控制点
function drawControlPoints(ctx, startPoint, currentPoint) {
    if (!startPoint || !currentPoint) return;
    
    const pointRadius = 4;
    ctx.fillStyle = '#ff0000';
    
    // 起始点
    ctx.beginPath();
    ctx.arc(startPoint.x, startPoint.y, pointRadius, 0, Math.PI * 2);
    ctx.fill();
    
    // 当前点
    ctx.beginPath();
    ctx.arc(currentPoint.x, currentPoint.y, pointRadius, 0, Math.PI * 2);
    ctx.fill();
}

// 绘制所有标注
function drawAnnotations(ctx, scaleX = 1, scaleY = 1, offsetX = 0, offsetY = 0) {
    currentAnnotations.forEach(annotation => {
        drawAnnotation(ctx, annotation, scaleX, scaleY, offsetX, offsetY);
    });
}

// 绘制单个标注
function drawAnnotation(ctx, annotation, scaleX = 1, scaleY = 1, offsetX = 0, offsetY = 0) {
    if (!annotation.points || annotation.points.length === 0) return;
    
    const classInfo = classes.find(c => c.name === annotation.class);
    const color = classInfo ? classInfo.color : '#ff0000';
    
    // 检查是否为选中状态
    const isSelected = annotation.id === selectedAnnotationId;
    
    ctx.beginPath();
    ctx.moveTo(annotation.points[0][0] * scaleX + offsetX, annotation.points[0][1] * scaleY + offsetY);
    
    for (let i = 1; i < annotation.points.length; i++) {
        ctx.lineTo(annotation.points[i][0] * scaleX + offsetX, annotation.points[i][1] * scaleY + offsetY);
    }
    
    if (annotation.type === 'rectangle' || annotation.points.length > 2) {
        ctx.closePath();
        ctx.fillStyle = color + '40'; // 半透明填充
        ctx.fill();
    }
    
    // 绘制边框
    ctx.strokeStyle = isSelected ? '#ff0000' : color;
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.stroke();
    
    // 绘制标签名
    if (annotation.points.length > 0) {
        const textX = annotation.points[0][0] * scaleX + offsetX;
        const textY = annotation.points[0][1] * scaleY + offsetY - 5;
        
        ctx.fillStyle = isSelected ? '#ff0000' : color;
        ctx.font = '14px Arial';
        ctx.fillText(annotation.class, textX, textY);
    }
    
    // 如果是选中状态，绘制控制点
    if (isSelected && annotation.type === 'rectangle') {
        drawResizeHandles(ctx, annotation, scaleX, scaleY, offsetX, offsetY);
    }
}

// 绘制调整大小的控制点
function drawResizeHandles(ctx, annotation, scaleX, scaleY, offsetX, offsetY) {
    const points = annotation.points;
    if (points.length < 4) return;
    
    // 计算矩形的四个角点
    const x1 = points[0][0] * scaleX + offsetX;
    const y1 = points[0][1] * scaleY + offsetY;
    const x2 = points[2][0] * scaleX + offsetX;
    const y2 = points[2][1] * scaleY + offsetY;
    
    // 控制点位置
    const handles = [
        { x: x1, y: y1, type: 'nw' }, // 左上
        { x: (x1 + x2) / 2, y: y1, type: 'n' }, // 上中
        { x: x2, y: y1, type: 'ne' }, // 右上
        { x: x2, y: (y1 + y2) / 2, type: 'e' }, // 右中
        { x: x2, y: y2, type: 'se' }, // 右下
        { x: (x1 + x2) / 2, y: y2, type: 's' }, // 下中
        { x: x1, y: y2, type: 'sw' }, // 左下
        { x: x1, y: (y1 + y2) / 2, type: 'w' }  // 左中
    ];
    
    // 绘制控制点
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#ff0000';
    ctx.lineWidth = 1;
    
    handles.forEach(handle => {
        ctx.beginPath();
        ctx.arc(handle.x, handle.y, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    });
}

// 加载类别
function loadClasses() {
    fetch('/api/classes')
        .then(response => response.json())
        .then(data => {
            classes = data;
            updateClassList();
        })
        .catch(error => console.error('加载类别失败:', error));
}

// 更新类别列表
function updateClassList() {
    const classList = document.getElementById('classList');
    classList.innerHTML = '';
    
    classes.forEach((cls, index) => {
        const li = document.createElement('li');
        li.className = 'class-item';
        // 设置CSS变量，用于背景色
        li.style.setProperty('--class-color', cls.color);
        li.innerHTML = `
            <div class="class-color" style="background-color: ${cls.color};"></div>
            <span class="class-name">${cls.name}</span>
            <div class="class-actions">
                <button class="class-edit-btn" data-index="${index}">
                    <i class="fas fa-pencil-alt"></i>
                </button>
            </div>
            <button class="class-delete-btn" data-index="${index}">
                <i class="fas fa-times"></i>
            </button>
        `;
        classList.appendChild(li);
    });
    
    // 添加事件监听器
    document.querySelectorAll('.class-item').forEach((item, index) => {
        // 点击选中类别
        item.addEventListener('click', function() {
            document.querySelectorAll('.class-item').forEach(i => i.classList.remove('selected'));
            this.classList.add('selected');
        });
        
        // 编辑按钮事件
        const editBtn = item.querySelector('.class-edit-btn');
        if (editBtn) {
            editBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                editClass(index);
            });
        }
        
        // 删除按钮事件
        const deleteBtn = item.querySelector('.class-delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                deleteClass(index);
            });
        }
    });
    
    // 默认选中第一个类别
    const firstClassItem = document.querySelector('.class-item');
    if (firstClassItem) {
        firstClassItem.classList.add('selected');
    }
}

// 添加类别
function addClass() {
    const nameInput = document.getElementById('newClassInput');
    const colorInput = document.getElementById('newClassColor');
    const name = nameInput.value.trim();
    
    if (!name) {
        showToast('请输入标签名称');
        return;
    }
    
    // 检查是否已存在同名类别
    if (classes.some(cls => cls.name === name)) {
        showToast('类别名称已存在');
        return;
    }
    
    const newClass = {
        name: name,
        color: colorInput.value
    };
    
    classes.push(newClass);
    updateClassList();
    saveClasses();
    
    // 清空输入框
    nameInput.value = '';
}

// 编辑类别
function editClass(index) {
    const cls = classes[index];
    document.getElementById('editClassIndex').value = index;
    document.getElementById('editClassName').value = cls.name;
    document.getElementById('editClassColor').value = cls.color;
    
    const modal = document.getElementById('editClassModal');
    modal.style.display = 'block';
}

// 处理类别编辑表单提交
function handleEditClass(e) {
    e.preventDefault();
    
    const index = document.getElementById('editClassIndex').value;
    const name = document.getElementById('editClassName').value.trim();
    const color = document.getElementById('editClassColor').value;
    
    if (!name) {
        showToast('请输入类别名称');
        return;
    }
    
    // 检查是否与其他类别重名
    if (classes.some((cls, i) => i != index && cls.name === name)) {
        showToast('类别名称已存在');
        return;
    }
    
    classes[index] = {
        name: name,
        color: color
    };
    
    updateClassList();
    saveClasses();
    
    // 关闭模态框
    document.getElementById('editClassModal').style.display = 'none';
}

// 删除类别
function deleteClass(index) {
    if (confirm(`确定要删除类别 "${classes[index].name}" 吗？`)) {
        classes.splice(index, 1);
        updateClassList();
        saveClasses();
    }
}

// 保存类别
function saveClasses() {
    fetch('/api/classes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(classes)
    }).catch(error => console.error('保存类别失败:', error));
}

// 加载图片列表
function loadImages() {
    fetch('/api/images')
        .then(response => response.json())
        .then(data => {
            window.allImages = data.images;
            updateImageList(data.images);
            updateImageCount(data.images.length);
            
            // 检查URL参数，看是否需要直接打开某个图片
            const urlParams = new URLSearchParams(window.location.search);
            const imageName = urlParams.get('image');
            
            if (imageName) {
                // 如果URL参数指定了图片，检查该图片是否存在
                const imageExists = data.images.some(img => img.name === imageName);
                if (imageExists) {
                    selectImage(imageName);
                    return;
                }
            }
            
            // 如果URL参数无效或未指定，默认选中第一张图片（如果有）
            if (data.images.length > 0) {
                selectImage(data.images[0].name);
            } else {
                // 如果没有图片，显示无图片提示
                document.getElementById('noImageMessage').style.display = 'block';
                document.getElementById('imageCanvasContainer').style.display = 'none';
                currentImage = null;
            }
        })
        .catch(error => {
            console.error('加载图片列表失败:', error);
            showToast('加载图片列表失败');
        });
}

// 更新图片列表
function updateImageList(images) {
    const imageList = document.getElementById('imageList');
    imageList.innerHTML = '';
    
    images.forEach((image, index) => {
        const li = document.createElement('li');
        li.className = 'image-item';
        li.dataset.image = image.name;
        
        // 检查是否有标注
        const hasAnnotations = image.annotation_count > 0;
        
        li.innerHTML = `
            <div class="image-checkbox">
                <input type="checkbox" class="image-checkbox-input">
            </div>
            <div class="annotation-status">
                ${hasAnnotations ? 
                  '<i class="fas fa-check-circle annotated" title="已标注"></i>' : 
                  '<i class="far fa-circle unannotated" title="未标注"></i>'}
            </div>
            <div class="image-index">${index + 1}</div>
            <div class="image-name" title="${image.name}">${image.name}</div>
        `;
        imageList.appendChild(li);
    });
    
    // 添加点击事件
    document.querySelectorAll('.image-item').forEach(item => {
        item.addEventListener('click', function(e) {
            if (e.target.type !== 'checkbox') {
                const imageName = this.dataset.image;
                selectImage(imageName);
            }
        });
    });
    
    // 添加复选框事件
    document.querySelectorAll('.image-checkbox-input').forEach(checkbox => {
        checkbox.addEventListener('change', updateDeleteButtonState);
    });
    
    // 不再需要删除按钮事件监听器
}

// 更新图片计数
function updateImageCount(count) {
    document.getElementById('imageCount').textContent = `共 ${count} 张图片`;
}

// 筛选图片
function filterImages() {
    const searchTerm = document.getElementById('imageSearch').value.toLowerCase();
    const filteredImages = window.allImages.filter(image => 
        image.name.toLowerCase().includes(searchTerm)
    );
    updateImageList(filteredImages);
}

// 选择图片
function selectImage(imageName, skipLoadAnnotations = false) {
    // 更新UI选中状态
    document.querySelectorAll('.image-item').forEach(item => {
        item.classList.remove('selected');
        if (item.dataset.image === imageName) {
            item.classList.add('selected');
        }
    });
    
    currentImage = imageName;
    
    // 隐藏无图片提示
    document.getElementById('noImageMessage').style.display = 'none';
    
    // 显示画布容器
    document.getElementById('imageCanvasContainer').style.display = 'block';
    
    // 加载标注，除非跳过
    if (!skipLoadAnnotations) {
        loadAnnotations(imageName);
    }
}

// 加载标注
function loadAnnotations(imageName) {
    fetch(`/api/annotations/${imageName}`)
        .then(response => response.json())
        .then(data => {
            currentAnnotations = data || [];
            updateAnnotationListDebounced();
            redrawCanvas();
        })
        .catch(error => {
            console.error('加载标注失败:', error);
            currentAnnotations = [];
            updateAnnotationListDebounced();
            redrawCanvas();
        });
}

// 更新标注列表
function updateAnnotationList() {
    const annotationList = document.getElementById('currentAnnotations');
    annotationList.innerHTML = '';
    
    currentAnnotations.forEach((annotation, index) => {
        const li = document.createElement('li');
        li.className = `annotation-item ${annotation.id === selectedAnnotationId ? 'selected' : ''}`;
        li.dataset.annotationId = annotation.id;
        li.innerHTML = `
            <div class="annotation-color" style="background-color: ${getClassColor(annotation.class)};"></div>
            <span class="annotation-class">${annotation.class}</span>
            <div class="annotation-actions">
                <button class="btn btn-small btn-danger delete-annotation-btn" data-index="${index}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        annotationList.appendChild(li);
    });
    
    // 添加事件监听器
    document.querySelectorAll('.annotation-item').forEach((item, index) => {
        // 点击选中标注
        item.addEventListener('click', function() {
            const annotationId = parseInt(this.dataset.annotationId);
            selectedAnnotationId = annotationId;
            updateAnnotationList();
            redrawCanvas();
        });
        
        // 删除按钮事件
        const deleteBtn = item.querySelector('.delete-annotation-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                deleteAnnotation(index);
            });
        }
    });
}

// 获取类别颜色
function getClassColor(className) {
    const cls = classes.find(c => c.name === className);
    return cls ? cls.color : '#ff0000';
}

// 删除标注
function deleteAnnotation(index) {
    if (confirm('确定要删除这个标注吗？')) {
        const annotation = currentAnnotations[index];
        // 如果删除的是当前选中的标注，重置选中状态
        if (annotation.id === selectedAnnotationId) {
            selectedAnnotationId = null;
        }
        currentAnnotations.splice(index, 1);
        updateAnnotationListDebounced();
        saveAnnotations();
        redrawCanvas();
    }
}

// 清除当前标注
function clearCurrentAnnotations() {
    if (currentAnnotations.length === 0) {
        showToast('当前没有标注可清除');
        return;
    }
    
    currentAnnotations = [];
    selectedAnnotationId = null; // 重置选中状态
    updateAnnotationListDebounced();
    saveAnnotations();
    redrawCanvas();
    showToast('标注已清除');
}

// 保存标注
function saveAnnotations() {
    if (!currentImage) return;
    
    const annotationData = {
        image: currentImage,
        annotations: currentAnnotations
    };
    
    fetch(`/api/annotations/${annotationData.image}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(annotationData.annotations)
    })
    .then(response => {
        if (response.ok) {
            showToast('标注已保存');
            // 重新获取图片列表，更新标注计数
            fetch('/api/images')
                .then(response => response.json())
                .then(data => {
                    window.allImages = data.images;
                    updateImageList(data.images);
                    updateImageCount(data.images.length);
                    // 保持当前选中的图片不变，跳过重新加载标注
                    selectImage(currentImage, true);
                })
                .catch(error => {
                    console.error('更新图片列表失败:', error);
                });
        } else {
            throw new Error('保存失败');
        }
    })
    .catch(error => {
        console.error('保存标注失败:', error);
        showToast('保存标注失败');
    });
}

// 全选图片
function selectAllImages() {
    const checkboxes = document.querySelectorAll('.image-checkbox-input');
    const allSelected = Array.from(checkboxes).every(cb => cb.checked);
    
    checkboxes.forEach(cb => {
        cb.checked = !allSelected;
    });
    
    updateDeleteButtonState();
}

// 更新删除按钮状态
function updateDeleteButtonState() {
    const checkedCount = document.querySelectorAll('.image-checkbox-input:checked').length;
    const deleteBtn = document.getElementById('deleteSelectedBtn');
    
    if (checkedCount > 0) {
        deleteBtn.disabled = false;
        deleteBtn.title = `删除选中的 ${checkedCount} 张图片`;
    } else {
        deleteBtn.disabled = true;
        deleteBtn.title = '删除选中';
    }
}

// 删除选中图片
function deleteSelectedImages() {
    const checkedItems = document.querySelectorAll('.image-checkbox-input:checked');
    
    if (checkedItems.length === 0) {
        showToast('请先选择要删除的图片');
        return;
    }
    
    if (!confirm(`确定要删除选中的 ${checkedItems.length} 张图片吗？`)) {
        return;
    }
    
    const imageNames = Array.from(checkedItems).map(cb => {
        return cb.closest('.image-item').dataset.image;
    });
    
    fetch('/api/images/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({images: imageNames})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`成功删除 ${imageNames.length} 张图片`);
            // 重新加载图片列表
            loadImages();
            // 清除选中状态
            checkedItems.forEach(cb => cb.checked = false);
            updateDeleteButtonState();
        } else {
            throw new Error(data.error || '删除失败');
        }
    })
    .catch(error => {
        console.error('删除图片失败:', error);
        showToast('删除图片失败: ' + error.message);
    });
}

// 显示数据集模态框
function showDatasetModal() {
    document.getElementById('datasetModal').style.display = 'block';
}

// 显示导出模态框
function showExportModal() {
    // 加载类别到导出表单
    const container = document.getElementById('classCheckboxes');
    container.innerHTML = '';
    
    classes.forEach(cls => {
        const label = document.createElement('label');
        label.className = 'class-checkbox-label';
        label.innerHTML = `
            <input type="checkbox" name="exportClasses" value="${cls.name}" checked>
            <span class="class-color-inline" style="background-color: ${cls.color};"></span>
            ${cls.name}
        `;
        container.appendChild(label);
    });
    
    // 设置默认比例
    document.getElementById('trainRatio').value = 0.7;
    document.getElementById('valRatio').value = 0.2;
    document.getElementById('testRatio').value = 0.1;
    
    document.getElementById('exportModal').style.display = 'block';
}

// 检查YOLO11安装状态并更新UI
function checkYolo11InstallStatus() {
    // 发送请求检查YOLO11安装状态
    fetch('/api/check-yolo11-install')
        .then(response => response.json())
        .then(data => {
            const isInstalled = data.is_installed;
            const modelsSection = document.querySelector('.yolo11-models-section');
            const downloadModelsBtn = document.getElementById('downloadModelsBtn');
            const refreshModelsBtn = document.getElementById('refreshModelsBtn');
            const modelDropZone = document.getElementById('modelDropZone');
            const modelsContainer = document.getElementById('modelsContainer');
            const installBtn = document.getElementById('installYolo11Btn');
            const uninstallBtn = document.getElementById('uninstallYolo11Btn');
            
            // 更新安装信息显示
            const installInfoElement = document.getElementById('yolo11InstallInfo');
            if (isInstalled) {
                // 显示详细安装信息
                const installTime = data.install_time || '未知';
                const hardware = data.has_cuda ? 'CUDA (GPU)' : 'CPU';
                installInfoElement.innerHTML = `
                    <p style="margin: 5px 0;"><strong>安装时间:</strong> ${installTime}</p>
                    <p style="margin: 5px 0;"><strong>硬件支持:</strong> ${hardware}</p>
                `;
                installInfoElement.style.display = 'block';
                
                // 更新按钮状态
                modelsSection.style.opacity = '1';
                modelsSection.style.pointerEvents = 'auto';
                downloadModelsBtn.disabled = false;
                refreshModelsBtn.disabled = false;
                installBtn.disabled = true;
                uninstallBtn.disabled = false;
            } else {
                // 隐藏安装信息
                installInfoElement.innerHTML = '';
                installInfoElement.style.display = 'none';
                
                // 更新按钮状态
                modelsSection.style.opacity = '0.5';
                modelsSection.style.pointerEvents = 'none';
                downloadModelsBtn.disabled = true;
                refreshModelsBtn.disabled = true;
                installBtn.disabled = false;
                uninstallBtn.disabled = true;
            }
        })
        .catch(error => {
            console.error('检查YOLO11安装状态失败:', error);
        });
}

// 安装YOLO11
function installYolo11() {
    const installBtn = document.getElementById('installYolo11Btn');
    const uninstallBtn = document.getElementById('uninstallYolo11Btn');
    const statusElement = document.getElementById('yolo11InstallStatus');
    const statusText = document.getElementById('yolo11StatusText');
    const progressElement = document.getElementById('yolo11InstallProgress');
    const progressBar = document.getElementById('yolo11ProgressBar');
    const progressPercent = document.getElementById('yolo11ProgressPercent');
    const installPath = document.getElementById('yolo11InstallPath').value;
    
    // 禁用按钮
    installBtn.disabled = true;
    uninstallBtn.disabled = true;
    
    // 显示状态和进度
    statusElement.style.display = 'block';
    statusText.textContent = '正在安装YOLO11...';
    progressElement.style.display = 'block';
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    
    // 使用EventSource实现服务器推送进度
    const eventSource = new EventSource(`/api/install-yolo11?install_path=${encodeURIComponent(installPath)}`);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // 更新状态文本
            statusText.textContent = data.message;
            
            // 更新进度条
            if (data.progress !== undefined) {
                const progress = Math.min(100, Math.max(0, data.progress));
                progressBar.style.width = `${progress}%`;
                progressPercent.textContent = `${progress}%`;
            }
            
            // 检查是否安装完成
            if (data.status === 'completed') {
                eventSource.close();
                installBtn.disabled = true;
                uninstallBtn.disabled = false;
                statusText.textContent = 'YOLO11安装完成';
                // 更新YOLO11安装状态
                checkYolo11InstallStatus();
                // 5秒后隐藏状态
                setTimeout(() => {
                    statusElement.style.display = 'none';
                    progressElement.style.display = 'none';
                }, 5000);
            }
            
            // 检查是否安装失败
            if (data.status === 'error') {
                eventSource.close();
                installBtn.disabled = false;
                uninstallBtn.disabled = true;
                statusText.textContent = `安装失败: ${data.error}`;
                // 5秒后隐藏状态
                setTimeout(() => {
                    statusElement.style.display = 'none';
                    progressElement.style.display = 'none';
                }, 5000);
            }
        } catch (error) {
            console.error('解析安装进度失败:', error);
        }
    };
    
    eventSource.onerror = function() {
        eventSource.close();
        installBtn.disabled = false;
        uninstallBtn.disabled = true;
        statusText.textContent = '安装过程中发生错误';
        // 5秒后隐藏状态
        setTimeout(() => {
            statusElement.style.display = 'none';
            progressElement.style.display = 'none';
        }, 5000);
    };
}

// 卸载YOLO11
function uninstallYolo11() {
    const installBtn = document.getElementById('installYolo11Btn');
    const uninstallBtn = document.getElementById('uninstallYolo11Btn');
    const statusElement = document.getElementById('yolo11InstallStatus');
    const statusText = document.getElementById('yolo11StatusText');
    const progressElement = document.getElementById('yolo11InstallProgress');
    const progressBar = document.getElementById('yolo11ProgressBar');
    const progressPercent = document.getElementById('yolo11ProgressPercent');
    const installPath = document.getElementById('yolo11InstallPath').value;
    
    // 确认卸载
    if (!confirm('确定要卸载YOLO11吗？')) {
        return;
    }
    
    // 禁用按钮
    installBtn.disabled = true;
    uninstallBtn.disabled = true;
    
    // 显示状态和进度
    statusElement.style.display = 'block';
    statusText.textContent = '正在卸载YOLO11...';
    progressElement.style.display = 'block';
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    
    // 使用EventSource实现服务器推送进度
    const eventSource = new EventSource(`/api/uninstall-yolo11?install_path=${encodeURIComponent(installPath)}`);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // 更新状态文本
            statusText.textContent = data.message;
            
            // 更新进度条
            if (data.progress !== undefined) {
                const progress = Math.min(100, Math.max(0, data.progress));
                progressBar.style.width = `${progress}%`;
                progressPercent.textContent = `${progress}%`;
            }
            
            // 检查是否卸载完成
            if (data.status === 'completed') {
                eventSource.close();
                installBtn.disabled = false;
                uninstallBtn.disabled = true;
                statusText.textContent = 'YOLO11卸载完成';
                // 更新YOLO11安装状态
                checkYolo11InstallStatus();
                // 5秒后隐藏状态
                setTimeout(() => {
                    statusElement.style.display = 'none';
                    progressElement.style.display = 'none';
                }, 5000);
            }
            
            // 检查是否卸载失败
            if (data.status === 'error') {
                eventSource.close();
                installBtn.disabled = true;
                uninstallBtn.disabled = false;
                statusText.textContent = `卸载失败: ${data.error}`;
                // 5秒后隐藏状态
                setTimeout(() => {
                    statusElement.style.display = 'none';
                    progressElement.style.display = 'none';
                }, 5000);
            }
        } catch (error) {
            console.error('解析卸载进度失败:', error);
        }
    };
    
    eventSource.onerror = function() {
        eventSource.close();
        installBtn.disabled = true;
        uninstallBtn.disabled = false;
        statusText.textContent = '卸载过程中发生错误';
        // 5秒后隐藏状态
        setTimeout(() => {
            statusElement.style.display = 'none';
            progressElement.style.display = 'none';
        }, 5000);
    };
}

// 下载YOLO11预训练模型
function downloadModels() {
    // 获取选中的模型
    const selectedModels = Array.from(document.querySelectorAll('input[name="yolo11Models"]:checked'))
        .map(cb => cb.value);
    
    if (selectedModels.length === 0) {
        showToast('请至少选择一个模型');
        return;
    }
    
    // 获取安装路径
    const installPath = document.getElementById('yolo11InstallPath').value;
    
    // 显示状态
    const statusElement = document.getElementById('modelDownloadStatus');
    const statusText = document.getElementById('modelStatusText');
    statusElement.style.display = 'block';
    statusText.textContent = `正在下载模型: ${selectedModels.join(', ')}...`;
    
    // 禁用下载按钮
    const downloadBtn = document.getElementById('downloadModelsBtn');
    const refreshBtn = document.getElementById('refreshModelsBtn');
    downloadBtn.disabled = true;
    refreshBtn.disabled = true;
    
    // 使用EventSource实现服务器推送进度
    const eventSource = new EventSource(`/api/download-models?models=${selectedModels.join(',')}&install_path=${encodeURIComponent(installPath)}`);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // 更新状态文本
            statusText.textContent = data.message;
            
            // 检查是否下载完成
            if (data.status === 'completed') {
                eventSource.close();
                statusText.textContent = `模型下载完成: ${selectedModels.join(', ')}`;
                // 刷新模型列表
                refreshModels();
                // 恢复按钮状态
                downloadBtn.disabled = false;
                refreshBtn.disabled = false;
                // 5秒后隐藏状态
                setTimeout(() => {
                    statusElement.style.display = 'none';
                }, 5000);
            }
            
            // 检查是否下载失败
            if (data.status === 'error') {
                eventSource.close();
                statusText.textContent = `下载失败: ${data.error}`;
                // 恢复按钮状态
                downloadBtn.disabled = false;
                refreshBtn.disabled = false;
                // 5秒后隐藏状态
                setTimeout(() => {
                    statusElement.style.display = 'none';
                }, 5000);
            }
        } catch (error) {
            console.error('解析下载进度失败:', error);
        }
    };
    
    eventSource.onerror = function() {
        eventSource.close();
        statusText.textContent = '下载过程中发生错误';
        // 恢复按钮状态
        downloadBtn.disabled = false;
        refreshBtn.disabled = false;
        // 5秒后隐藏状态
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 5000);
    };
}

// 刷新模型列表
function refreshModels() {
    // 获取安装路径
    const installPath = document.getElementById('yolo11InstallPath').value;
    
    // 显示加载状态
    const modelsList = document.getElementById('modelsList');
    modelsList.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在加载模型列表...';
    
    // 发送请求获取模型列表
    fetch(`/api/list-models?install_path=${encodeURIComponent(installPath)}`)
        .then(response => response.json())
        .then(data => {
            // 更新模型列表
            if (data.models && data.models.length > 0) {
                modelsList.innerHTML = '';
                data.models.forEach(model => {
                    const modelItem = document.createElement('div');
                    modelItem.className = 'model-item';
                    modelItem.innerHTML = `
                        <i class="fas fa-file-code"></i>
                        <span class="model-name">${model}</span>
                        <button class="delete-model-btn" onclick="deleteModel('${model}')">
                            <i class="fas fa-times"></i>
                        </button>
                    `;
                    modelsList.appendChild(modelItem);
                });
            } else {
                modelsList.innerHTML = '<i class="fas fa-info-circle"></i> 暂无已安装的模型';
            }
        })
        .catch(error => {
            console.error('获取模型列表失败:', error);
            modelsList.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 获取模型列表失败';
        });
}

// 删除模型
function deleteModel(modelName) {
    // 确认删除
    if (!confirm(`确定要删除模型 ${modelName} 吗？`)) {
        return;
    }
    
    // 获取安装路径
    const installPath = document.getElementById('yolo11InstallPath').value;
    
    // 显示状态
    const statusElement = document.getElementById('modelDownloadStatus');
    const statusText = document.getElementById('modelStatusText');
    statusElement.style.display = 'block';
    statusText.textContent = `正在删除模型: ${modelName}...`;
    
    // 发送删除请求
    fetch('/api/delete-model', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Install-Path': installPath
        },
        body: JSON.stringify({model_name: modelName})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            statusText.textContent = `模型删除成功: ${modelName}`;
            // 刷新模型列表
            refreshModels();
        } else {
            statusText.textContent = `删除失败: ${data.error}`;
        }
        // 5秒后隐藏状态
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 5000);
    })
    .catch(error => {
        console.error('删除模型失败:', error);
        statusText.textContent = `删除失败: ${error.message}`;
        // 5秒后隐藏状态
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 5000);
    });
}

// 设置模型拖放区域事件
function setupModelDropZoneEvents() {
    const dropZone = document.getElementById('modelDropZone');
    
    // 阻止默认拖放行为
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    // 高亮拖放区域
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });
    
    // 取消高亮拖放区域
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });
    
    // 处理文件拖放
    dropZone.addEventListener('drop', handleDrop, false);
}

// 阻止默认拖放行为
function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

// 高亮拖放区域
function highlight(e) {
    const dropZone = document.getElementById('modelDropZone');
    dropZone.style.borderColor = '#339af0';
    dropZone.style.backgroundColor = '#e3f2fd';
}

// 取消高亮拖放区域
function unhighlight(e) {
    const dropZone = document.getElementById('modelDropZone');
    dropZone.style.borderColor = '#ced4da';
    dropZone.style.backgroundColor = '#f8f9fa';
}

// 处理文件拖放
function handleDrop(e) {
    const files = e.dataTransfer.files;
    if (files.length === 0) return;
    
    // 显示状态
    const statusElement = document.getElementById('modelDownloadStatus');
    const statusText = document.getElementById('modelStatusText');
    statusElement.style.display = 'block';
    statusText.textContent = `正在上传模型文件...`;
    
    // 获取安装路径
    const installPath = document.getElementById('yolo11InstallPath').value;
    
    // 创建FormData对象
    const formData = new FormData();
    Array.from(files).forEach(file => {
        formData.append('files[]', file, file.name);
    });
    
    // 发送文件上传请求
    fetch('/api/upload-model', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Install-Path': installPath
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            statusText.textContent = `模型文件上传成功: ${data.uploaded_files.join(', ')}`;
            // 刷新模型列表
            refreshModels();
        } else {
            statusText.textContent = `上传失败: ${data.error}`;
        }
    })
    .catch(error => {
        console.error('上传模型文件失败:', error);
        statusText.textContent = `上传失败: ${error.message}`;
    })
    .finally(() => {
        // 5秒后隐藏状态
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 5000);
    });
}

// 显示设置模态框
function showSettingsModal() {
    document.getElementById('settingsModal').style.display = 'block';
    // 检查YOLO11安装状态并更新UI
    checkYolo11InstallStatus();
    // 刷新模型列表
    refreshModels();
}

// 处理导出表单提交
function handleExport(e) {
    e.preventDefault();
    
    // 获取表单数据
    const formData = new FormData(e.target);
    const trainRatio = parseFloat(formData.get('trainRatio'));
    const valRatio = parseFloat(formData.get('valRatio'));
    const testRatio = parseFloat(formData.get('testRatio'));

    console.log("trainRatio:", typeof trainRatio, trainRatio);
    console.log("valRatio:", typeof valRatio, valRatio);
    console.log("testRatio:", typeof testRatio,testRatio)


    // 获取选中的类别
    const selectedClasses = Array.from(document.querySelectorAll('input[name="exportClasses"]:checked'))
        .map(cb => cb.value);
    
    if (selectedClasses.length === 0) {
        showToast('请至少选择一个类别');
        return;
    }
    
    // 检查比例总和
    // const total = trainRatio + valRatio + testRatio;
    // if (Math.abs(total - 1.0) > 0.001) {
    //     showToast('训练集、验证集和测试集比例之和必须等于1');
    //     return;
    // }
    
    // 获取样本选择选项和文件前缀
    const sampleSelection = formData.get('sampleSelection');
    const exportDataType = formData.get('exportDataType');
    const exportPrefix = document.getElementById('exportPrefix').value;
    
    // 显示加载指示器
    document.getElementById('exportSubmitBtn').style.display = 'none';
    document.getElementById('exportLoadingIndicator').style.display = 'block';
    
    // 发送导出请求
    fetch('/api/export', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            train_ratio: trainRatio,
            val_ratio: valRatio,
            test_ratio: testRatio,
            selected_classes: selectedClasses,
            sample_selection: sampleSelection,
            export_data_type: exportDataType,
            export_prefix: exportPrefix
        })
    })
    .then(response => {
        if (response.ok) {
            return response.blob().then(blob => {
                // 生成带时间戳的文件名，格式：datasets_年月日时分秒.zip
                const now = new Date();
                const year = now.getFullYear();
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const day = String(now.getDate()).padStart(2, '0');
                const hours = String(now.getHours()).padStart(2, '0');
                const minutes = String(now.getMinutes()).padStart(2, '0');
                const seconds = String(now.getSeconds()).padStart(2, '0');
                const filename = `datasets_${year}${month}${day}${hours}${minutes}${seconds}.zip`;
                
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                // 隐藏模态框
                document.getElementById('exportModal').style.display = 'none';
            });
        } else {
            return response.json().then(data => {
                throw new Error(data.error || '导出失败');
            });
        }
    })
    .catch(error => {
        console.error('导出失败:', error);
        showToast('导出失败: ' + error.message);
    })
    .finally(() => {
        // 隐藏加载指示器
        document.getElementById('exportSubmitBtn').style.display = 'block';
        document.getElementById('exportLoadingIndicator').style.display = 'none';
    });
}

// 处理设置保存
function handleSettingsSave(e) {
    e.preventDefault();
    
    const clearShortcut = document.getElementById('clearShortcut').value;
    const saveShortcut = document.getElementById('saveShortcut').value;
    const prevImageShortcut = document.getElementById('prevImageShortcut').value;
    const nextImageShortcut = document.getElementById('nextImageShortcut').value;
    
    // 保存设置到localStorage
    const settings = {
        clearShortcut,
        saveShortcut,
        prevImageShortcut,
        nextImageShortcut
    };
    localStorage.setItem('xclabelSettings', JSON.stringify(settings));
    
    showToast('设置已保存');
    document.getElementById('settingsModal').style.display = 'none';
    
    // 重新加载快捷键设置
    loadShortcutSettings();
}

// 快捷键设置
let shortcutSettings = {
    clearShortcut: 'Ctrl+Shift+D',
    saveShortcut: 'Ctrl+S',
    prevImageShortcut: 'ArrowUp',
    nextImageShortcut: 'ArrowDown'
};

// 加载快捷键设置
function loadShortcutSettings() {
    const savedSettings = localStorage.getItem('xclabelSettings');
    if (savedSettings) {
        shortcutSettings = { ...shortcutSettings, ...JSON.parse(savedSettings) };
        
        // 更新设置表单中的值
        document.getElementById('clearShortcut').value = shortcutSettings.clearShortcut;
        document.getElementById('saveShortcut').value = shortcutSettings.saveShortcut;
        document.getElementById('prevImageShortcut').value = shortcutSettings.prevImageShortcut;
        document.getElementById('nextImageShortcut').value = shortcutSettings.nextImageShortcut;
    }
}

// 解析快捷键字符串，返回包含key和修饰键的对象
function parseShortcut(shortcutStr) {
    const parts = shortcutStr.toLowerCase().split('+');
    const key = parts.pop();
    return {
        key: key === 'arrowup' ? 'ArrowUp' : 
             key === 'arrowdown' ? 'ArrowDown' :
             key === 'arrowleft' ? 'ArrowLeft' :
             key === 'arrowright' ? 'ArrowRight' :
             key === 'space' ? ' ' :
             key === 'esc' ? 'Escape' :
             key === 'enter' ? 'Enter' :
             key === 'backspace' ? 'Backspace' :
             key.charAt(0).toUpperCase() + key.slice(1),
        ctrlKey: parts.includes('ctrl'),
        shiftKey: parts.includes('shift'),
        altKey: parts.includes('alt')
    };
}

// 处理键盘快捷键
function handleKeyDown(e) {
    // 保存
    const saveShortcut = parseShortcut(shortcutSettings.saveShortcut);
    if (e.ctrlKey === saveShortcut.ctrlKey && 
        e.shiftKey === saveShortcut.shiftKey && 
        e.altKey === saveShortcut.altKey && 
        e.key.toLowerCase() === saveShortcut.key.toLowerCase()) {
        e.preventDefault();
        saveAnnotations();
    }
    
    // 清除标注
    const clearShortcut = parseShortcut(shortcutSettings.clearShortcut);
    if (e.ctrlKey === clearShortcut.ctrlKey && 
        e.shiftKey === clearShortcut.shiftKey && 
        e.altKey === clearShortcut.altKey && 
        e.key.toLowerCase() === clearShortcut.key.toLowerCase()) {
        e.preventDefault();
        clearCurrentAnnotations();
    }
    
    // 上一张图片
    const prevShortcut = parseShortcut(shortcutSettings.prevImageShortcut);
    if (e.ctrlKey === prevShortcut.ctrlKey && 
        e.shiftKey === prevShortcut.shiftKey && 
        e.altKey === prevShortcut.altKey && 
        e.key.toLowerCase() === prevShortcut.key.toLowerCase()) {
        e.preventDefault();
        switchImage('prev');
    }
    
    // 下一张图片
    const nextShortcut = parseShortcut(shortcutSettings.nextImageShortcut);
    if (e.ctrlKey === nextShortcut.ctrlKey && 
        e.shiftKey === nextShortcut.shiftKey && 
        e.altKey === nextShortcut.altKey && 
        e.key.toLowerCase() === nextShortcut.key.toLowerCase()) {
        e.preventDefault();
        switchImage('next');
    }
}

// 切换图片
function switchImage(direction) {
    if (!currentImage || !window.allImages) return;
    
    // 获取当前图片在列表中的索引
    const currentIndex = window.allImages.findIndex(img => img.name === currentImage);
    if (currentIndex === -1) return;
    
    let nextIndex;
    if (direction === 'prev') {
        // 上一张图片
        nextIndex = currentIndex > 0 ? currentIndex - 1 : window.allImages.length - 1;
    } else {
        // 下一张图片
        nextIndex = currentIndex < window.allImages.length - 1 ? currentIndex + 1 : 0;
    }
    
    // 获取下一张图片的名称
    const nextImageName = window.allImages[nextIndex].name;
    
    // 切换到下一张图片
    selectImage(nextImageName);
}

// 设置模态框关闭事件
function setupModalCloseEvents() {
    document.querySelectorAll('.modal .close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            this.closest('.modal').style.display = 'none';
        });
    });
    
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    });
}

// 设置数据集上传事件
function setupDatasetUploadEvents() {
    // 图片文件夹上传
    const selectFolderBtn = document.getElementById('selectFolderBtn');
    const folderInput = document.getElementById('folderInput');
    const uploadImagesBtn = document.getElementById('uploadImagesBtn');
    if (selectFolderBtn && folderInput && uploadImagesBtn) {
        selectFolderBtn.addEventListener('click', function() {
            folderInput.click();
        });
        
        folderInput.addEventListener('change', function(e) {
            // 处理选中的图片文件
            const files = Array.from(e.target.files);
            if (files.length > 0) {
                // 显示选中的文件数量
                const uploadArea = document.getElementById('imageUploadArea');
                const fileCount = document.createElement('div');
                fileCount.className = 'file-count';
                fileCount.textContent = `已选择 ${files.length} 个文件`;
                fileCount.style.marginTop = '10px';
                fileCount.style.fontSize = '0.9em';
                fileCount.style.color = '#666';
                
                // 移除之前的文件数量显示
                const existingCount = uploadArea.querySelector('.file-count');
                if (existingCount) {
                    existingCount.remove();
                }
                
                uploadArea.appendChild(fileCount);
                
                // 启用上传按钮
                uploadImagesBtn.disabled = false;
            }
        });
        
        // 上传图片按钮事件
        uploadImagesBtn.addEventListener('click', function() {
            const files = Array.from(folderInput.files);
            if (files.length === 0) {
                showToast('请先选择图片文件');
                return;
            }
            
            // 显示上传中状态
            uploadImagesBtn.disabled = true;
            uploadImagesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';
            
            // 创建FormData对象，用于发送文件
            const formData = new FormData();
            files.forEach(file => {
                formData.append('files[]', file, file.name);
            });
            
            // 发送真实的文件上传请求
            fetch('/api/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // 重置按钮状态
                uploadImagesBtn.innerHTML = '<i class="fas fa-upload"></i> 上传图片到数据集';
                uploadImagesBtn.disabled = false;
                
                // 显示成功提示
                showToast(`成功上传 ${files.length} 张图片`);
                
                // 关闭模态框
                document.getElementById('datasetModal').style.display = 'none';
                
                // 重新加载图片列表
                loadImages();
            })
            .catch(error => {
                console.error('上传失败:', error);
                
                // 重置按钮状态
                uploadImagesBtn.innerHTML = '<i class="fas fa-upload"></i> 上传图片到数据集';
                uploadImagesBtn.disabled = false;
                
                // 显示错误提示
                showToast('上传失败，请重试');
            });
        });
    }
    
    // 视频文件上传
    const selectVideoBtn = document.getElementById('selectVideoBtn');
    const videoInput = document.getElementById('videoInput');
    const videoUploadArea = document.getElementById('videoUploadArea');
    if (selectVideoBtn && videoInput && videoUploadArea) {
        selectVideoBtn.addEventListener('click', function() {
            videoInput.click();
        });
        
        videoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                handleVideoFileSelect(file);
            }
        });
        
        // 添加拖入功能
        videoUploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('drag-over');
        });
        
        videoUploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');
        });
        
        videoUploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');
            
            // 获取拖入的文件
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                // 只处理第一个文件
                const file = files[0];
                // 检查是否为视频文件
                if (file.type.startsWith('video/')) {
                    // 更新videoInput的files属性
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    videoInput.files = dataTransfer.files;
                    
                    // 处理视频文件
                    handleVideoFileSelect(file);
                } else {
                    showToast('请拖入视频文件');
                }
            }
        });
    }
    
    // 处理视频文件选择
    function handleVideoFileSelect(file) {
        if (file) {
            const selectedVideoInfo = document.getElementById('selectedVideoInfo');
            const selectedVideoName = document.getElementById('selectedVideoName');
            selectedVideoName.textContent = file.name;
            selectedVideoInfo.style.display = 'block';
            
            // 启用抽帧按钮
            const extractFramesBtn = document.getElementById('extractFramesBtn');
            if (extractFramesBtn) {
                extractFramesBtn.disabled = false;
            }
        }
    }
    
    // 视频抽帧按钮
    const extractFramesBtn = document.getElementById('extractFramesBtn');
    const frameIntervalInput = document.getElementById('frameInterval');
    if (extractFramesBtn && videoInput && frameIntervalInput) {
        extractFramesBtn.addEventListener('click', function() {
            const files = videoInput.files;
            if (files.length === 0) {
                showToast('请先选择视频文件');
                return;
            }
            
            // 获取抽帧间隔
            const frameInterval = parseInt(frameIntervalInput.value) || 30;
            
            // 显示上传中状态
            extractFramesBtn.disabled = true;
            extractFramesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 抽帧中...';
            
            // 创建FormData对象，用于发送视频文件和抽帧间隔
            const formData = new FormData();
            formData.append('video', files[0], files[0].name);
            formData.append('frame_interval', frameInterval);
            
            // 发送真实的视频抽帧请求
            fetch('/api/upload/video', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // 重置按钮状态
                extractFramesBtn.innerHTML = '<i class="fas fa-film"></i> 抽帧并添加到数据集';
                extractFramesBtn.disabled = false;
                
                if (data.error) {
                    // 显示错误提示
                    showToast(`抽帧失败: ${data.error}`);
                } else {
                    // 显示成功提示
                    showToast(`成功从视频中提取 ${data.count} 帧图片`);
                    
                    // 关闭模态框
                    document.getElementById('datasetModal').style.display = 'none';
                    
                    // 重新加载图片列表
                    loadImages();
                }
            })
            .catch(error => {
                console.error('抽帧失败:', error);
                
                // 重置按钮状态
                extractFramesBtn.innerHTML = '<i class="fas fa-film"></i> 抽帧并添加到数据集';
                extractFramesBtn.disabled = false;
                
                // 显示错误提示
                showToast('抽帧失败，请重试');
            });
        });
    }
    
    // LabelMe数据集上传
    const selectLabelMeBtn = document.getElementById('selectLabelMeBtn');
    const labelmeInput = document.getElementById('labelmeInput');
    const uploadLabelMeBtn = document.getElementById('uploadLabelMeBtn');
    if (selectLabelMeBtn && labelmeInput && uploadLabelMeBtn) {
        selectLabelMeBtn.addEventListener('click', function() {
            labelmeInput.click();
        });
        
        labelmeInput.addEventListener('change', function(e) {
            // 处理选中的LabelMe文件
            const files = Array.from(e.target.files);
            if (files.length > 0) {
                // 显示选中的文件数量
                const uploadArea = document.getElementById('labelmeUploadArea');
                const fileCount = document.createElement('div');
                fileCount.className = 'file-count';
                fileCount.textContent = `已选择 ${files.length} 个文件`;
                fileCount.style.marginTop = '10px';
                fileCount.style.fontSize = '0.9em';
                fileCount.style.color = '#666';
                
                // 移除之前的文件数量显示
                const existingCount = uploadArea.querySelector('.file-count');
                if (existingCount) {
                    existingCount.remove();
                }
                
                uploadArea.appendChild(fileCount);
                
                // 启用上传按钮
                uploadLabelMeBtn.disabled = false;
            }
        });
        
        // 上传LabelMe数据集按钮事件
        uploadLabelMeBtn.addEventListener('click', function() {
            const files = Array.from(labelmeInput.files);
            if (files.length === 0) {
                showToast('请先选择LabelMe数据集文件');
                return;
            }
            
            // 显示上传中状态
            uploadLabelMeBtn.disabled = true;
            uploadLabelMeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';
            
            // 创建FormData对象，用于发送文件
            const formData = new FormData();
            files.forEach(file => {
                formData.append('files', file, file.name);
            });
            
            // 发送真实的文件上传请求
            fetch('/api/upload-labelme', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // 重置按钮状态
                uploadLabelMeBtn.innerHTML = '<i class="fas fa-upload"></i> 上传labelme数据集';
                uploadLabelMeBtn.disabled = false;
                
                // 显示成功提示
                showToast(`成功上传 ${files.length} 个LabelMe文件`);
                
                // 关闭模态框
                document.getElementById('datasetModal').style.display = 'none';
                
                // 重新加载图片列表和类别列表
                loadImages();
                loadClasses();
            })
            .catch(error => {
                console.error('上传失败:', error);
                
                // 重置按钮状态
                uploadLabelMeBtn.innerHTML = '<i class="fas fa-upload"></i> 上传labelme数据集';
                uploadLabelMeBtn.disabled = false;
                
                // 显示错误提示
                showToast('上传失败，请重试');
            });
        });
    }
    
    // 标签页切换事件
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除所有标签页的active状态
            tabBtns.forEach(b => b.classList.remove('active'));
            
            // 添加当前标签页的active状态
            this.classList.add('active');
            
            // 隐藏所有内容面板
            const tabContents = document.querySelectorAll('.tab-pane');
            tabContents.forEach(content => content.classList.remove('active'));
            
            // 显示对应内容面板
            const tabId = this.getAttribute('data-tab');
            const targetTab = document.getElementById(`${tabId}-tab`);
            if (targetTab) {
                targetTab.classList.add('active');
            }
        });
    });
}

// 显示Toast提示
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.style.display = 'block';
    
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// 页面卸载前确认
window.addEventListener('beforeunload', function(e) {
    // 如果有未保存的更改，显示确认提示
    // 这里可以根据需要实现
});

// 绘制十字引导线 - 移除直接在主画布上绘制的逻辑，避免重影
function drawCrosshair(e) {
    // 不再直接在画布上绘制十字线，避免重影问题
    // 重绘画布时会清除所有临时绘制
    return;
}
