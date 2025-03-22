import json
import os
import shutil
import time
from datetime import datetime
import subprocess
import sys
import cv2
from flask import Flask, request, jsonify
from app.utils.OSSystem import OSSystem
from app.utils.TrainUtils import TrainUtils
from app.views.ViewsBase import *
from app.models import *
import random
from app.utils.UploadUtils import UploadUtils

app = Flask(__name__)

@app.route('/api/trainTest/postDel', methods=['POST'])
def api_postDel():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        test_code = params.get("code", "").strip()
        test = TaskTrainTest.query.filter_by(code=test_code).first()
        if test:
            test_save_dir = os.path.join(g_config.storageDir, "test", test_code)
            try:
                if os.path.exists(test_save_dir):
                    shutil.rmtree(test_save_dir)
            except Exception as e:
                g_logger.error("api_postDel test_save_dir=%s,e=%s" % (test_save_dir, str(e)))

            test.delete()
            ret = True
            msg = "删除成功"
        else:
            msg = "数据不存在！"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)

@app.route('/api/trainTest/postAdd', methods=['POST'])
def api_postAdd():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        train_code = params.get("train_code", "").strip()
        file_type = int(params.get("file_type", 0))

        try:
            train = TaskTrain.query.filter_by(code=train_code).first()
            if not train:
                raise Exception("该训练任务不存在！")

            train_best_model_filepath = os.path.join(g_config.storageDir, "train", train.code, "train/weights/best.pt")
            if not os.path.exists(train_best_model_filepath):
                raise Exception("该训练任务暂无模型！")

            file = request.files.get("file0")
            if not file:
                raise Exception("请选择上传文件！")

            test_code = "test" + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))  # 随机生成一个测试编号
            test_save_dir = os.path.join(g_config.storageDir, "train", train.code, "test", test_code)
            if not os.path.exists(test_save_dir):
                os.makedirs(test_save_dir)

            upload_utils = UploadUtils()

            if file_type == 1:
                __ret, __msg, __info = upload_utils.upload_model_test_image(test_save_dir=test_save_dir, file=file)
            elif file_type == 2:
                __ret, __msg, __info = upload_utils.upload_model_test_video(test_save_dir=test_save_dir, file=file)
            else:
                raise Exception("不支持的文件类型")

            if not __ret:
                raise Exception(__msg)

            test_filepath = __info["test_filepath"]
            file_name = __info["file_name"]
            file_size = __info["file_size"]

            test_predict_log_filepath = os.path.join(test_save_dir, "predict.log")  # 训练日志

            calcu_start_time = time.time()

            if train.algorithm_code == "yolo8" or train.algorithm_code == "yolo11":

                yolo8_install_dir = getattr(g_config, train.algorithm_code)["install_dir"]
                yolo8_venv = getattr(g_config, train.algorithm_code)["venv"]
                yolo8_name = getattr(g_config, train.algorithm_code)["name"]

                osSystem = OSSystem()
                if osSystem.getSystemName() == "Windows":
                    # Windows系统，需要执行下切换盘符的步骤
                    dirve, tail = os.path.splitdrive(yolo8_install_dir)
                    cd_dirve = "%s &&" % dirve
                else:
                    cd_dirve = ""

                __command_run = "{yolo8_name} detect predict model={model} source={source} device=cpu project={project} > {test_predict_log_filepath}".format(
                    yolo8_name=yolo8_name,
                    model=train_best_model_filepath,
                    source=test_filepath,
                    project=test_save_dir,
                    test_predict_log_filepath=test_predict_log_filepath
                )
                __predict_command = "{cd_dirve} cd {yolo8_install_dir} && {yolo8_venv} && {command_run}".format(
                    cd_dirve=cd_dirve,
                    yolo8_install_dir=yolo8_install_dir,
                    yolo8_venv=yolo8_venv,
                    command_run=__command_run
                )
                g_logger.info("测试模型命令行：%s" % __predict_command)

                proc = subprocess.Popen(__predict_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8')
                stdout, stderr = proc.communicate()

            else:
                raise Exception("不支持的训练算法")

            calcu_end_time = time.time()
            calcu_seconds = calcu_end_time - calcu_start_time

            user = readUser(request)

            test = TaskTrainTest()
            test.sort = 0
            test.code = test_code
            test.user_id = user.get("id")
            test.username = user.get("username")
            test.task_code = train.task_code
            test.train_code = train.code
            test.file_name = file_name
            test.file_size = file_size
            test.file_type = file_type
            test.calcu_seconds = round(calcu_seconds, 3)
            test.create_time = datetime.now()
            test.save()

            ret = True
            msg = "success"

        except Exception as e:
            msg = str(e)
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)

@app.route('/api/trainTest/getIndex')
def api_getIndex():
    ret = False
    msg = "未知错误"
    data = []

    if request.method == 'GET':
        params = request.args
        train_code = params.get("train_code", "").strip()
        sql = "select * from xc_task_train_test where train_code='%s' order by id desc" % train_code
        data = g_database.select(sql)
        for d in data:
            d["create_time_str"] = d["create_time"].strftime("%Y/%m/%d %H:%M")

        ret = True
        msg = "success"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg,
        "data": data
    }
    return jsonify(res)
