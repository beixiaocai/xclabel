import os
import time
from datetime import datetime
import random
from flask import Flask, render_template, request, jsonify, redirect
from app.models import *
from app.utils.Utils import buildPageLabels, gen_random_code_s
from app.utils.UploadUtils import UploadUtils
import cv2

app = Flask(__name__)

@app.route('/sample')
def index():
    context = {}
    params = request.args

    task_code = params.get('task_code', "").strip()
    sample_code = params.get('sample_code', "").strip()

    context["task_code"] = task_code
    context["sample_code"] = sample_code
    context["storageDir_www"] = g_config.storageDir_www

    return render_template('app/sample/index.html', **context)

@app.route('/api/sample/getIndex')
def api_getIndex():
    ret = False
    msg = "未知错误"

    params = request.args
    page = params.get('p', 1)
    page_size = params.get('ps', 10)
    task_code = params.get('task_code', "").strip()

    try:
        page = int(page)
    except:
        page = 1
    try:
        page_size = int(page_size)
        if page_size > 20 or page_size < 10:
            page_size = 10
    except:
        page_size = 10

    skip = (page - 1) * page_size
    sql_data = "select * from xc_task_sample where task_code='%s' order by id desc limit %d,%d " % (task_code, skip, page_size)
    count = g_database.select("select count(id) as count from xc_task_sample where task_code='%s'" % task_code)
    count = int(count[0]["count"])
    if count > 0:
        data = g_database.select(sql_data)
    else:
        data = []

    page_num = int(count / page_size)  # 总页数
    if count % page_size > 0:
        page_num += 1

    pageLabels = buildPageLabels(page=page, page_num=page_num)
    pageData = {
        "page": page,
        "page_size": page_size,
        "page_num": page_num,
        "count": count,
        "pageLabels": pageLabels
    }
    ret = True
    msg = "success"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg,
        "data": data,
        "pageData": pageData
    }
    return jsonify(res)

@app.route('/api/sample/postAdd', methods=['POST'])
def api_postAdd():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        task_code = params.get("task_code", "").strip()
        task_type = int(params.get("task_type", 0))
        upload_type = int(params.get("upload_type", 0))  # 1:图片文件 2:图片文件夹 3:视频文件 4:labelme文件夹

        task = Task.query.filter_by(code=task_code).first()
        task_state = 1 if task else 0
        user = readUser(request)

        success_count = 0
        error_count = 0
        labelme_jpg_dict = {}
        labelme_json_dict = {}

        upload_utils = UploadUtils()
        filenames = request.files.keys()
        for filename in filenames:
            file = request.files.get(filename)
            if upload_type == 1 or upload_type == 2:
                __ret, __msg, __info = upload_utils.upload_sample_image(storageDir=g_config.storageDir, task_code=task_code, file=file)

                if __ret:
                    old_filename = __info.get("old_filename")
                    new_filename = __info.get("new_filename")

                    sample_code = "sample" + datetime.now().strftime("%Y%m%d%H%M%S") + str(
                        random.randint(1000, 9999))  # 随机生成一个训练编号

                    sample = TaskSample()
                    sample.sort = 0
                    sample.code = sample_code
                    sample.user_id = user.get("id")
                    sample.username = user.get("username")
                    sample.task_type = task_type
                    sample.task_code = task_code
                    sample.old_filename = old_filename
                    sample.new_filename = new_filename
                    sample.remark = ""
                    sample.create_time = datetime.now()
                    sample.state = task_state
                    sample.annotation_user_id = 0
                    sample.annotation_state = 0
                    sample.save()

                    success_count += 1
                else:
                    error_count += 1
            elif upload_type == 3:
                __ret, __msg, __info = upload_utils.upload_sample_video(storageDir=g_config.storageDir,
                                                                        task_code=task_code, file=file)
                if __ret:
                    old_filename = __info.get("old_filename")
                    new_filenames = __info.get("new_filenames")

                    sample_code = "sample" + datetime.now().strftime("%Y%m%d%H%M%S") + str(
                        random.randint(1000, 9999))  # 随机生成一个训练编号
                    i = 0
                    for new_filename in new_filenames:
                        sample = TaskSample()
                        sample.sort = 0
                        sample.code = sample_code + "-" + str(i)
                        sample.user_id = user.get("id")
                        sample.username = user.get("username")
                        sample.task_type = task_type
                        sample.task_code = task_code
                        sample.old_filename = old_filename
                        sample.new_filename = new_filename
                        sample.remark = ""
                        sample.create_time = datetime.now()
                        sample.state = task_state
                        sample.annotation_user_id = 0
                        sample.annotation_state = 0
                        sample.save()
                        i += 1
                        success_count += 1

                else:
                    error_count += 1
            elif upload_type == 4:
                __ret, __msg, __info = upload_utils.upload_sample_labelme(storageDir=g_config.storageDir,
                                                                          task_code=task_code, file=file)
                if __ret:
                    old_filename_prefix = __info["old_filename_prefix"]
                    old_filename_suffix = __info["old_filename_suffix"]
                    if old_filename_suffix == "jpg":
                        labelme_jpg_dict[old_filename_prefix] = __info
                    elif old_filename_suffix == "json":
                        labelme_json_dict[old_filename_prefix] = __info

        if upload_type == 4:
            sample_code = "sample" + datetime.now().strftime("%Y%m%d%H%M%S") + str(
                random.randint(1000, 9999))  # 随机生成一个训练编号
            labelName_dict = {}
            i = 0
            for k in labelme_jpg_dict.keys():
                __jpg_info = labelme_jpg_dict.get(k)
                __json_info = labelme_json_dict.get(k)
                if __jpg_info and __json_info:
                    old_filename = __jpg_info.get("old_filename")
                    new_filename = __jpg_info.get("new_filename")

                    annotation_content = []
                    annotation = __json_info.get("annotation")

                    shapes = annotation.get("shapes")
                    imageWidth = annotation.get("imageWidth")
                    imageHeight = annotation.get("imageHeight")

                    for shape in shapes:
                        label = shape.get("label")  # drive
                        labelName_dict[label] = labelName_dict.get(label, 0) + 1

                        shape_type = shape.get("shape_type")
                        points = shape.get("points")

                        x1 = float(points[0][0])
                        y1 = float(points[0][1])
                        x2 = float(points[1][0])
                        y2 = float(points[1][1])

                        width = x2 - x1
                        height = y2 - y1

                        annotation_content.append({
                            "content": [
                                {"x": x1, "y": y1},
                                {"x": x1, "y": y1},
                                {"x": x2, "y": y2},
                                {"x": x1, "y": y2}
                            ],
                            "rectMask": {
                                "xMin": x1,
                                "yMin": y1,
                                "width": width,
                                "height": height,
                            },
                            "labels": {
                                "labelName": label,
                                "labelColor": "#ff0000",
                                "labelColorRGB": "255,0,0",
                                "visibility": False
                            },
                            "labelLocation": {
                                "x": (x1 + x2) / 2,
                                "y": (y1 + y2) / 2
                            },
                            "contentType": "rect"
                        })

                    sample = TaskSample()
                    sample.sort = 0
                    sample.code = sample_code + "-" + str(i)
                    sample.user_id = user.get("id")
                    sample.username = user.get("username")
                    sample.task_type = task_type
                    sample.task_code = task_code
                    sample.old_filename = old_filename
                    sample.new_filename = new_filename
                    sample.remark = ""
                    sample.create_time = datetime.now()
                    sample.state = task_state
                    sample.annotation_user_id = user.get("id")
                    sample.annotation_state = 1
                    sample.annotation_content = json.dumps(annotation_content)
                    sample.save()

                    i += 1
                    success_count += 1

            if task:
                task_labels = []
                task_labels_dict = {}
                try:
                    task_labels = json.loads(task.labels)
                    for task_label in task_labels:
                        task_labels_dict[task_label["labelName"]] = 1

                except:
                    pass

                for labelName in labelName_dict.keys():
                    if not task_labels_dict.get(labelName):
                        task_labels.append({
                            "labelName": labelName,
                            "labelColor": "#ff0000",
                            "labelColorR": "255",
                            "labelColorG": "0",
                            "labelColorB": "0"
                        })
                task.labels = json.dumps(task_labels)
                task.save()

        msg = "成功：%d，失败：%d" % (success_count, error_count)
        if success_count > 0:
            ret = True

    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)

@app.route('/api/sample/postDel', methods=['POST'])
def api_postDel():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        code = params.get("code", "").strip()
        sample = TaskSample.query.filter_by(code=code).first()
        if sample:
            new_filename_abs = os.path.join(
                g_config.storageDir,
                'task',
                sample.task_code,
                'sample',
                sample.new_filename
            )
            if os.path.exists(new_filename_abs):
                os.remove(new_filename_abs)
            sample.delete()

            ret = True
            msg = "删除成功"

        else:
            msg = "该样本不存在！"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)

@app.route('/api/sample/getInfo')
def api_getInfo():
    ret = False
    msg = "未知错误"

    params = request.args
    task_code = params.get('task_code', "").strip()
    sample_code = params.get('sample_code', "").strip()

    sample = {}
    sample_data = g_database.select("select code from xc_task_sample where task_code='%s' and state=1" % task_code)

    if len(sample_data) > 0:
        sample_index = 0
        i = 0
        for d in sample_data:
            if d["code"] == sample_code:
                sample_index = i
                sample_code = d["code"]
                break
            i += 1
        if sample_index == 0:
            sample_code = sample_data[0]["code"]

        sample = g_database.select("select xc_task_sample.*, xc_task.labels from xc_task_sample left join xc_task on xc_task_sample.task_code=xc_task.code where xc_task_sample.code='%s' limit 1" % sample_code)
        if len(sample) > 0:
            sample = sample[0]

        ret = True
        msg = "success"

    else:
        msg = "empty data"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg,
        "sample": sample,
        "sample_data": sample_data
    }
    return jsonify(res)

@app.route('/api/sample/postSaveAnnotation', methods=['POST'])
def api_postSaveAnnotation():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        sample_code = params.get("sample_code", "").strip()
        annotation_content = params.get("annotation_content", "").strip()
        labels = params.get("labels", "").strip()

        user = readUser(request)
        user_id = user.get("id")
        username = user.get("username")

        sample = TaskSample.query.filter_by(code=sample_code).first()
        if sample:
            sample.annotation_user_id = user_id
            sample.annotation_username = username
            sample.annotation_time = datetime.now()
            sample.annotation_content = annotation_content
            sample.annotation_state = 1
            sample.save()

            task = Task.query.filter_by(code=sample.task_code).first()
            if task:
                task.labels = labels
                task.save()

            ret = True
            msg = "保存标注成功"
        else:
            msg = "该样本不存在！"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)

@app.route('/api/sample/postDelAnnotation', methods=['POST'])
def api_postDelAnnotation():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        sample_code = params.get("sample_code", "").strip()

        sample = TaskSample.query.filter_by(code=sample_code).first()
        if sample:
            sample.annotation_state = 0
            sample.annotation_content = None
            sample.save()

            ret = True
            msg = "删除标注成功"
        else:
            msg = "该样本不存在！"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)
