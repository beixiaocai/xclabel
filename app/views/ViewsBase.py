import json
import os
import base64
import platform
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session
from app.utils.Config import Config
from app.utils.Utils import buildPageLabels
from app.utils.Logger import CreateLogger
from app.utils.OSSystem import OSSystem
from app.models import db
from flask_sqlalchemy import SQLAlchemy

__log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
if not os.path.exists(__log_dir):
    os.makedirs(__log_dir)

g_logger = CreateLogger(filepath=os.path.join(__log_dir, "xclabel%s.log" % (datetime.now().strftime("%Y%m%d-%H%M%S"))), is_show_console=True)
g_logger.info("xclabel %s,%s" % ("1.0", "xclabel"))
g_logger.info("BASE_DIR:%s" % os.path.dirname(os.path.abspath(__file__)))
if platform.system() == "Linux" or platform.system() == "Darwin":
    g_config = Config(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config-linux.json"))
    g_logger.info("config-linux.json:%s" % g_config.getConfigStr())
else:
    g_config = Config(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
    g_logger.info("config.json:%s" % g_config.getConfigStr())
g_osSystem = OSSystem()

g_session_key_user = "user"

class Database():
    def select(self, sql):
        result = db.session.execute(sql)
        data = []
        try:
            for row in result:
                d = {}
                for index, value in enumerate(row):
                    d[row.keys()[index]] = value
                data.append(d)
        except Exception as e:
            g_logger.error("SQLAlchemy select error: %s" % str(e))
            g_logger.error(sql)
        return data

    def select_ex(self, sql):
        result = db.session.execute(sql)
        data = []
        for row in result:
            d = {}
            for index, value in enumerate(row):
                d[row.keys()[index]] = value
            data.append(d)
        return data

    def insert(self, tb_name, d):
        sql = "insert into %s(%s) values(%s)" % (
            tb_name, ",".join(d.keys()), ",".join(map(lambda x: "'" + str(x) + "'", d.values())))
        return self.execute(sql)

    def execute(self, sql):
        ret = False
        try:
            db.session.execute(sql)
            db.session.commit()
            ret = True
        except Exception as e:
            g_logger.error("SQLAlchemy execute error: %s" % str(e))
            g_logger.error(sql)
        return ret

    def execute_ex(self, sql):
        db.session.execute(sql)
        db.session.commit()

g_database = Database()

def f_readSampleCountAndAnnotationCount(task_code):
    sample_count = g_database.select("select count(id) as count from xc_task_sample where task_code='%s'" % task_code)
    sample_count = int(sample_count[0]["count"])
    sample_annotation_count = g_database.select(
        "select count(id) as count from xc_task_sample where task_code='%s' and annotation_state=1" % task_code)
    sample_annotation_count = int(sample_annotation_count[0]["count"])
    return sample_count, sample_annotation_count

def readUser(request):
    user = session.get(g_session_key_user)
    return user

def parse_get_params(request):
    params = {}
    try:
        for k in request.args:
            params.__setitem__(k, request.args.get(k))
    except Exception as e:
        params = {}
    return params

def parse_post_params(request):
    params = {}
    for k in request.form:
        params.__setitem__(k, request.form.get(k))
    if not params:
        try:
            params = request.get_json()
        except:
            params = {}
    return params

def HttpResponseJson(res):
    def json_dumps_default(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        else:
            raise TypeError
    return jsonify(res)
