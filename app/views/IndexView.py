from flask import Flask, render_template, jsonify
from app.models import *
from framework.settings import PROJECT_ADMIN_START_TIMESTAMP
from app.utils.OSSystem import OSSystem

app = Flask(__name__)

@app.route('/')
def index():
    context = {}
    return render_template('app/web_index.html', **context)

@app.route('/api/getIndex')
def api_getIndex():
    ret = False
    msg = "未知错误"
    osInfo = {}
    appInfo = {
        "project_version": PROJECT_VERSION,
        "project_flag": PROJECT_FLAG,
        "start_timestamp": PROJECT_ADMIN_START_TIMESTAMP
    }
    try:
        osSystem = OSSystem()
        osInfo = osSystem.getOSInfo()

        ret = True
        msg = "success"
    except Exception as e:
        msg = str(e)

    res = {
        "code": 1000 if ret else 0,
        "msg": msg,
        "osInfo": osInfo,
        "appInfo": appInfo
    }
    return jsonify(res)
