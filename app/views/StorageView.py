from flask import Flask, request, send_file, jsonify
from app.views.ViewsBase import *
import os

app = Flask(__name__)

@app.route('/storage/download')
def download():
    params = request.args
    filename = params.get("filename")
    try:
        if filename:
            if filename.endswith(".mp4") \
                    or filename.endswith(".jpg") \
                    or filename.endswith(".xcsettings") \
                    or filename.endswith(".xclogs"):
                filepath = os.path.join(g_config.storageTempDir, filename)

                if os.path.exists(filepath):
                    return send_file(filepath, as_attachment=True, attachment_filename=filename)
                else:
                    raise Exception("storage/download filepath not found")
            else:
                raise Exception("storage/download unsupported filename format")
        else:
            raise Exception("storage/download filename not found")

    except Exception as e:
        return jsonify({"msg": str(e)})

@app.route('/storage/access')
def access():
    params = request.args
    filename = params.get("filename")
    try:
        if filename:
            if (filename.endswith(".avi") or filename.endswith(".flv") or filename.endswith(".mp4")
                    or filename.endswith(".jpg") or filename.endswith(".png")  or filename.endswith(".jpeg")):
                filepath = os.path.join(g_config.storageDir, filename)
                if os.path.exists(filepath):
                    return send_file(filepath)
                else:
                    raise Exception("storage/folder filepath not found")
            else:
                raise Exception("storage/folder unsupported filename format")
        else:
            raise Exception("storage/folder filename not exist")

    except Exception as e:
        return jsonify({"msg": str(e)})
