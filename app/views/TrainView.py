import json
import os
import shutil
import time
from datetime import datetime
import subprocess
import sys
import cv2
from app.utils.OSSystem import OSSystem
from app.utils.TrainUtils import TrainUtils
from app.views.ViewsBase import *
from app.models import *
from django.shortcuts import render, redirect
import random
from app.utils.Utils import buildPageLabels, gen_random_code_s
from app.utils.UploadUtils import UploadUtils
import threading
def index(request):
    context = {

    }
    data = []

    params = parse_get_params(request)

    page = params.get('p', 1)
    page_size = params.get('ps', 10)
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
    sql_data = "select * from xc_task_train order by id desc limit %d,%d " % (
        skip, page_size)
    sql_data_num = "select count(id) as count from xc_task_train "

    count = g_database.select(sql_data_num)

    if len(count) > 0:
        count = int(count[0]["count"])
        mTrainUtils = TrainUtils(g_logger)
        data = g_database.select(sql_data)
        for d in data:
            if d["train_state"] == 1:
                if not mTrainUtils.checkProcessByPid(pid=d["train_pid"]):
                    d["train_state"] = 2
                    d["train_stop_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    train = TaskTrain.objects.filter(id=d["id"]).first()
                    train.train_state = 2
                    train.train_stop_time = datetime.now()
                    train.save()

    else:
        count = 0

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

    context["data"] = data
    context["pageData"] = pageData

    return render(request, 'app/train/index.html', context)
def add(request):

    if request.method == 'POST':
        ret = False
        msg = "未知错误"

        params = parse_post_params(request)
        task_code = params.get("task_code", "").strip()
        train_code = params.get("train_code", "").strip()
        algorithm_code = params.get("algorithm_code", "").strip()
        device = params.get("device", "cpu").strip()
        imgsz = int(params.get("imgsz", 640))
        epochs = int(params.get("epochs", 300))
        batch = int(params.get("batch", 32))
        save_period = int(params.get("save_period", 5))
        sample_ratio = int(params.get("sample_ratio", 5))
        extra = params.get("extra", "").strip()

        try:
            train = TaskTrain.objects.filter(code=train_code)
            if len(train) > 0:
                raise Exception("该训练编号已存在！")

            task = Task.objects.filter(code=task_code)
            if len(task) > 0:
                task = task[0]
            else:
                raise Exception("任务不存在！")

            user = readUser(request)

            train = TaskTrain()
            train.sort = 0
            train.code = train_code
            train.user_id = user.get("id")
            train.username = user.get("username")
            train.task_code = task_code
            train.algorithm_code = algorithm_code
            train.device = device
            train.imgsz = imgsz
            train.epochs = epochs
            train.batch = batch
            train.save_period = save_period
            train.sample_ratio = sample_ratio
            train.extra = extra
            train.create_time = datetime.now()
            train.train_datasets = ""
            train.train_process_name = ""
            train.train_pid = 0
            train.train_count = 0
            train.train_state = 0
            train.save()

            ret = True
            msg = "添加成功"

        except Exception as e:
            msg = str(e)

        res = {
            "code": 1000 if ret else 0,
            "msg": msg
        }
        return HttpResponseJson(res)
    else:

        context = {

        }

        params = parse_get_params(request)
        task_code = params.get('task_code',"").strip()
        train_code = "train"+datetime.now().strftime("%Y%m%d%H%M%S") # 随机生成一个训练编号
        tasks = g_database.select("select * from xc_task")
        algorithms = [
            {
                "name":"YOLO8",
                "code":"yolo8"
            },
            {
                "name": "YOLO11",
                "code": "yolo11"
            }

        ]
        context["handle"] = "add"
        context["task_code"] = task_code
        context["train_code"] = train_code
        context["tasks"] = tasks
        context["algorithms"] = algorithms


        return render(request, 'app/train/add.html', context)

def manage(request):
    context = {

    }

    params = parse_get_params(request)

    train_code = params.get("code")
    if train_code:
        train = TaskTrain.objects.filter(code=train_code)
        if len(train) > 0:
            train = train[0]

            train_dir = os.path.join(g_config.storageDir, "train", train.code)
            train_best_model_filepath = os.path.join(train_dir, "train", "weights", "best.pt")
            if not os.path.exists(train_best_model_filepath):
                train_best_model_filepath = ""


            context["handle"] = "manage"
            context["storageDir_www"] = g_config.storageDir_www
            context["train_code"] = train_code
            context["train_best_model_filepath"] = train_best_model_filepath
            context["train"] = train


            return render(request, 'app/train/manage.html', context)

    return redirect("/train/index")


def api_postDel(request):
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = parse_post_params(request)
        train_code = params.get("code", "").strip()
        train = TaskTrain.objects.filter(code=train_code)
        if len(train) > 0:
            train = train[0]
            if train.train_state == 1:
                msg = "训练中的任务不允许删除"
            else:
                del_sql = "delete from xc_task_train_test where train_code='%s'" % train_code
                if not g_database.execute(del_sql):
                    g_logger.error("del_sql=%s"%del_sql)

                # 训练根目录
                train_dir = os.path.join(g_config.storageDir, "train", train.code)
                try:
                    if os.path.exists(train_dir):
                        shutil.rmtree(train_dir)
                except Exception as e:
                    g_logger.error("api_postDel train_dir=%s,e=%s"%(train_dir,str(e)))
                train.delete()

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
    return HttpResponseJson(res)
def api_postTaskCreateDatasets(request):
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = parse_post_params(request)

        train_code = params.get("train_code", "").strip()
        # try:
        train = TaskTrain.objects.filter(code=train_code)

        if len(train) > 0:
            train = train[0]
        else:
            raise Exception("该训练任务不存在!")

        task = Task.objects.filter(code=train.task_code)
        if len(task) > 0:
            task = task[0]
        else:
            raise Exception("标注任务不存在!")

        names = []
        try:
            __labels = json.loads(task.labels)
            if __labels:
                for __label in __labels:
                    names.append(__label["labelName"])
        except Exception as e:
            g_logger.error("api_postTaskCreateDatasets json.loads(task.labels) e=%s"%(str(e)))

        if len(names) == 0:
            raise Exception("标注任务的标签不能为空！")
        def getLabelIndex(labelName):
            i = 0
            for name in names:
                if labelName == name:
                    return i
                i += 1

            # TODO 临时测试
            if labelName == "未命名":
                return 0

            return -1

        samples = g_database.select("select * from xc_task_sample where task_code='%s' and annotation_state=1 order by id asc" % task.code)
        if len(samples) < 50:
            raise Exception("标注样本数量不能低于50")

        train_dir = os.path.join(g_config.storageDir, "train", train.code)
        train_datasets_dir = os.path.join(train_dir, "datasets")
        if os.path.exists(train_datasets_dir):
            shutil.rmtree(train_datasets_dir)

        train_datasets_train_dir = os.path.join(train_datasets_dir, "train")
        train_datasets_train_images_dir = os.path.join(train_datasets_train_dir, "images")
        train_datasets_train_labels_dir = os.path.join(train_datasets_train_dir, "labels")
        train_datasets_valid_dir = os.path.join(train_datasets_dir, "valid")
        train_datasets_valid_images_dir = os.path.join(train_datasets_valid_dir, "images")
        train_datasets_valid_labels_dir = os.path.join(train_datasets_valid_dir, "labels")
        if not os.path.exists(train_datasets_train_images_dir):
            os.makedirs(train_datasets_train_images_dir)
        if not os.path.exists(train_datasets_train_labels_dir):
            os.makedirs(train_datasets_train_labels_dir)
        if not os.path.exists(train_datasets_valid_images_dir):
            os.makedirs(train_datasets_valid_images_dir)
        if not os.path.exists(train_datasets_valid_labels_dir):
            os.makedirs(train_datasets_valid_labels_dir)

        train_datasets = os.path.join(train_datasets_dir, "data.yaml")
        f = open(train_datasets, "w")
        f.write("train: %s\n" % train_datasets_train_dir)
        f.write("val: %s\n" % train_datasets_valid_dir)
        f.write("nc: %d\n" % len(names))
        f.write("names: [%s]\n" % ",".join(map(lambda x: "'" + str(x) + "'", names)))
        f.close()

        # 开始生成训练样本文件start
        total_sample_count = 0
        for __sample in samples:
            new_filename = __sample["new_filename"]
            if new_filename.endswith(".jpg"):
                new_filename_prefix = new_filename[0:-4]
                src_image_filepath = os.path.join(g_config.storageDir, "task", task.code, "sample", new_filename)

                if os.path.exists(src_image_filepath):

                    image = cv2.imread(src_image_filepath)
                    if image is not None:
                        total_sample_count += 1

                        imageHeight, imageWidth, _ = image.shape
                        __annotation_content = json.loads(__sample["annotation_content"])

                        dst_lines = []
                        # 开始读取所有框start
                        for d in __annotation_content:
                            content = d["content"]
                            labels = d["labels"]
                            contentType = d["contentType"]
                            labelName = labels["labelName"]
                            labelIndex = getLabelIndex(labelName)

                            if labelIndex > -1 and contentType == "rect" and len(content) == 4:

                                x1 = float(content[0]["x"])
                                y1 = float(content[0]["y"])
                                x2 = float(content[2]["x"])
                                y2 = float(content[2]["y"])
                                if x1 > 0 and y1 > 0 and x2 < imageWidth and y2 < imageHeight:
                                    x_center = (x1 + x2) / 2 / float(imageWidth)
                                    y_center = (y1 + y2) / 2 / float(imageHeight)
                                    w = (x2 - x1) / float(imageWidth)
                                    h = (y2 - y1) / float(imageHeight)

                                    dst_line = "%d %.6f %.6f %.6f %.6f\n" % (labelIndex, x_center, y_center, w, h)
                                    dst_lines.append(dst_line)
                        # 开始读取所有框end

                        dst_image_filepath = os.path.join(train_datasets_train_images_dir, new_filename)
                        dst_label_filepath = os.path.join(train_datasets_train_labels_dir, "%s.txt" % new_filename_prefix)

                        shutil.copy(src_image_filepath, dst_image_filepath)
                        f = open(dst_label_filepath, "w")
                        for dst_line in dst_lines:
                            f.write(dst_line)
                        f.close()

                        print(total_sample_count, dst_lines, "><", __annotation_content)
        # 开始生成训练样本文件end

        # 训练集分割验证集start
        train_count, valid_count = TrainUtils.detect2detect(src_detect_dir=train_datasets_train_dir,
                                                            dst_detect_dir=train_datasets_valid_dir,
                                                            freq=train.sample_ratio + 1)
        # 训练集分割验证集end

        train.train_datasets = train_datasets
        train.train_datasets_remark = "总数量:%d 训练:%d 验证:%d" % (total_sample_count, train_count, valid_count)
        train.train_datasets_time = datetime.now()
        train.save()

        ret = True
        msg = "生成训练集成功"
        # except Exception as e:
        #     msg = str(e)
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return HttpResponseJson(res)
def api_postTaskStartTrain(request):
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = parse_post_params(request)

        train_code = params.get("train_code", "").strip()
        try:

            train = TaskTrain.objects.filter(code=train_code)
            if len(train) > 0:
                train = train[0]
            else:
                raise Exception("该训练不存在！")

            if train.train_state == 1:
                raise Exception("该任务正在训练中！")

            if train.train_datasets == "":
                raise Exception("训练集暂未生成！")

            if not os.path.exists(train.train_datasets):
                raise Exception("训练集路径不存在！")

            # 训练根目录
            train_dir = os.path.join(g_config.storageDir, "train", train.code)
            if not os.path.exists(train_dir):
                os.makedirs(train_dir)
            train_log_filepath = os.path.join(train_dir, "train.log") # 训练日志
            if os.path.exists(train_log_filepath):
                os.remove(train_log_filepath)

            __train_save_dir = os.path.join(train_dir, "train") # 训练模型的保存路径
            if os.path.exists(__train_save_dir):
                shutil.rmtree(__train_save_dir)

            __start_process_info = None
            __train_command = None

            if train.algorithm_code == "yolo8" or train.algorithm_code == "yolo11":

                yolo8_install_dir = getattr(g_config, train.algorithm_code)["install_dir"]
                yolo8_venv = getattr(g_config, train.algorithm_code)["venv"]
                yolo8_name = getattr(g_config, train.algorithm_code)["name"]
                yolo8_model = os.path.join(yolo8_install_dir, getattr(g_config, train.algorithm_code)["model"])


                osSystem = OSSystem()
                if osSystem.getSystemName() == "Windows":
                    # Windows系统，需要执行下切换盘符的步骤
                    dirve, tail = os.path.splitdrive(yolo8_install_dir)
                    cd_dirve = "%s &&" % dirve
                else:
                    cd_dirve = ""

                __command_run = "{yolo8_name} detect train model={yolo8_model} data={datasets} batch={batch}  epochs={epochs} imgsz={imgsz} save_period={save_period} device={device} project={project} > {train_log_filepath}".format(
                    yolo8_name=yolo8_name,
                    yolo8_model=yolo8_model,
                    datasets=train.train_datasets,
                    batch=train.batch,
                    epochs=train.epochs,
                    imgsz=train.imgsz,
                    save_period=train.save_period,
                    device=train.device,
                    project=train_dir,
                    train_log_filepath=train_log_filepath
                )
                __train_command = "{cd_dirve} cd {yolo8_install_dir} && {yolo8_venv} && {command_run}".format(
                    cd_dirve=cd_dirve,
                    yolo8_install_dir=yolo8_install_dir,
                    yolo8_venv=yolo8_venv,
                    command_run=__command_run
                )
                g_logger.info("训练启动命令行：%s" % __train_command)

                def __run(command):
                    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8')
                    # print(type(proc),proc)
                    # print("proc.pid=",proc.pid)
                    stdout, stderr = proc.communicate()
                    # print(type(stdout), stdout)
                    # print(type(stderr), stderr)

                t = threading.Thread(target=__run, args=(__train_command,))
                t.daemon = True
                t.start()

                # 检测训练是否正常启动
                mTrainUtils = TrainUtils(g_logger)
                for i in range(5):
                    time.sleep(i)
                    __info = mTrainUtils.getProcessInfoByName(processName=yolo8_name)
                    if __info["state"]:
                        __start_process_info = __info
                        break
            else:
                raise Exception("不支持的训练算法")



            if __start_process_info and __start_process_info["state"]:
                g_logger.info("训练启动成功: %s" % str(__start_process_info))
                if __train_command:
                    train.train_command = __train_command
                train.train_count += 1
                train.train_process_name = __start_process_info["process_name"]
                train.train_pid = __start_process_info["pid"]
                train.train_state = __start_process_info["state"] # 1:训练中 0:已停止
                train.train_start_time = datetime.now()
                train.train_stop_time = None
                train.save()

                ret = True
                msg = "训练启动成功"
            else:
                g_logger.error("训练启动失败: %s" % str(__start_process_info))
                msg = "训练启动失败"

        except Exception as e:
            msg = str(e)
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return HttpResponseJson(res)

def api_postTaskStopTrain(request):
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = parse_post_params(request)

        train_code = params.get("train_code", "").strip()
        train = TaskTrain.objects.filter(code=train_code)
        if len(train) > 0:
            train = train[0]
            if train.train_state == 1:
                mTrainUtils = TrainUtils(g_logger)
                mTrainUtils.stopProcessByPid(train.train_pid)
                train.train_state = 2
                train.train_stop_time = datetime.now()
                train.save()

                ret = True
                msg = "停止训练成功"
            else:
                msg = "该训练任务已经停止"
        else:
            msg = "该训练任务不存在！"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return HttpResponseJson(res)

def api_getTrainLog(request):
    ret = False
    msg = "未知错误"
    log_lines = []

    if request.method == 'GET':
        params = parse_get_params(request)
        task_code = params.get("task_code", "").strip()
        train_code = params.get("train_code", "").strip()
        train_log_index = int(params.get("train_log_index", 0))

        task = Task.objects.filter(code=task_code)
        if len(task) > 0:
            task = task[0]
            train_dir = os.path.join(g_config.storageDir, "train" , train_code)
            train_log_filepath = os.path.join(train_dir, "train.log")
            if os.path.exists(train_log_filepath):
                f = open(train_log_filepath, "r")
                lines = f.readlines()
                f.close()

                log_lines = lines[train_log_index:]
                ret = True
                msg = "success"
            else:
                msg = "train.log does not exist"
        else:
            msg = "任务不存在！"
    else:
        msg = "request method not supported"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg,
        "log_lines": log_lines
    }
    return HttpResponseJson(res)


def __checkTrainThread():
    i = 0
    mTrainUtils = TrainUtils(g_logger)
    while True:
        i += 1
        trains = TaskTrain.objects.filter(train_state=1)
        if len(trains) > 0:
            for train in trains:
                if not mTrainUtils.checkProcessByPid(pid=train.train_pid):
                    train.train_state = 2
                    train.train_stop_time = datetime.now()
                    train.save()
        # labelu

        time.sleep(30)

t = threading.Thread(target=__checkTrainThread,)
t.daemon = True
t.start()