from flask import Flask, render_template, request, jsonify, redirect, session
from app.views.ViewsBase import *
from app.models import User
from datetime import datetime

app = Flask(__name__)

@app.route('/user')
def index():
    context = {}
    data = []

    params = request.args

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
    sql_data = "select * from auth_user order by id desc limit %d,%d " % (
        skip, page_size)
    sql_data_num = "select count(id) as count from auth_user "

    count = g_database.select(sql_data_num)

    if len(count) > 0:
        count = int(count[0]["count"])
        data = g_database.select(sql_data)

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

    return render_template('app/user/index.html', **context)


@app.route('/user/add', methods=['GET', 'POST'])
def add():
    login_user_is_superuser = False
    login_user = readUser(request)
    if login_user:
        login_user_is_superuser = login_user.get("is_superuser")
    if not login_user_is_superuser:
        return render_template('app/message.html',
                      {"msg": "无权限", "is_success": False, "redirect_url": "/user/index"})
    else:
        context = {}

        if request.method == 'POST':
            __ret = False
            __msg = "未知错误"

            params = request.form

            username = params.get("username", "").strip()
            email = params.get("email", "").strip()
            password = params.get("password", "").strip()
            is_active = params.get("is_active")

            try:
                is_active = int(is_active)

                if username == "":
                    raise Exception("用户名不能为空")
                if email == "":
                    raise Exception("邮箱不能为空")
                if len(password) < 6 or len(password) > 16:
                    raise Exception("密码的长度需满足6-16位")

                user = User.query.filter_by(username=username).all()
                if len(user) > 0:
                    raise Exception("用户名已存在")
                else:
                    now = datetime.now()
                    user = User()
                    user.username = username
                    user.set_password(password)
                    user.email = email
                    user.date_joined = now
                    user.is_superuser = 0  # 表单创建均为非超级管理员
                    user.is_staff = 1
                    user.is_active = is_active
                    user.save()

                    if user.id > 0:
                        __ret = True
                        __msg = "添加成功"
                    else:
                        __msg = "添加失败"

            except Exception as e:
                __msg = str(e)
            if __ret:
                redirect_url = "/user/index"
            else:
                redirect_url = "/user/add"

            return render_template('app/message.html',
                          {"msg": __msg, "is_success": __ret, "redirect_url": redirect_url})
        else:

            context["user"] = {
                "is_active": 1,
            }
            context["handle"] = "add"
            return render_template('app/user/add.html', **context)


@app.route('/user/edit', methods=['GET', 'POST'])
def edit():
    login_user_is_superuser = False
    login_user = readUser(request)
    if login_user:
        login_user_is_superuser = login_user.get("is_superuser")

    if not login_user_is_superuser:
        return render_template('app/message.html',
                      {"msg": "无权限", "is_success": False, "redirect_url": "/user/index"})
    else:

        context = {}

        if request.method == 'POST':
            __ret = False
            __msg = "未知错误"
            params = request.form
            handle = params.get("handle")

            user_id = params.get("id")  # 被操作用户id
            is_active = params.get("is_active")
            username = params.get("username", "").strip()
            email = params.get("email", "").strip()

            new_password = params.get("new_password", "")
            re_password = params.get("re_password", "")

            try:
                user_id = int(user_id)
                is_active = int(is_active)

                if username == "":
                    raise Exception("用户名不能为空")
                if email == "":
                    raise Exception("邮箱不能为空")
                if re_password == "" and new_password == "":
                    pass
                else:
                    if new_password == "":
                        raise Exception("新密码不能为空")
                    if re_password == "":
                        raise Exception("确认新密码不能为空")
                    if new_password != re_password:
                        raise Exception("两次输入的密码不一致")
                    if len(new_password) < 6 or len(new_password) > 16:
                        raise Exception("新密码的长度需满足6-16位")

                user = User.query.filter_by(id=user_id).all()
                if len(user) > 0:
                    user = user[0]

                    if user.username == username:
                        pass
                    else:
                        filter_username = g_database.select(
                            "select count(1) as count from auth_user where id!=%d and username='%s'" % (
                            user_id, username))
                        filter_username_count = int(filter_username[0]["count"])
                        if filter_username_count > 0:
                            raise Exception("新用户名已经存在！")
                        user.username = username

                    if re_password == "" and new_password == "":
                        pass
                    else:
                        user.set_password(new_password)

                    user.email = email
                    user.is_active = is_active
                    user.save()
                    __ret = True
                    __msg = "编辑成功"

                    context["user"] = user
                else:
                    raise Exception("该数据不存在！")
            except Exception as e:
                __msg = str(e)

            if __ret:
                redirect_url = "/user/index"
            else:
                redirect_url = "/user/edit?id=" + str(user_id)

            return render_template('app/message.html',
                          {"msg": __msg, "is_success": __ret, "redirect_url": redirect_url})

        else:
            params = request.args
            user_id = params.get("id")
            if user_id:
                user = User.query.filter_by(id=user_id).all()
                if len(user) > 0:
                    user = user[0]
                    context["handle"] = "edit"
                    context["user"] = user
                    return render_template('app/user/add.html', context)
                else:
                    return render_template('app/message.html',
                                  {"msg": "该用户不存在", "is_success": False, "redirect_url": "/user/index"})

            else:
                return redirect("/user/index")


@app.route('/user/api/postDel', methods=['POST'])
def api_postDel():
    ret = False
    msg = "未知错误"
    if request.method == 'POST':
        params = request.form
        try:
            login_user = readUser(request)
            if not login_user:
                raise Exception("未登录")
            login_user_is_superuser = login_user.get("is_superuser")
            if not login_user_is_superuser:
                raise Exception("无权限")

            user_id = int(params.get("id"))
            if not user_id:
                raise Exception("参数不合法")

            login_user_id = int(login_user.get("id"))
            if login_user_id == user_id:
                raise Exception("超级管理员不允许删除自己的账号")

            user = User.query.filter_by(id=user_id).all()
            if len(user) > 0:
                user = user[0]
                if user.is_superuser == 1:
                    raise Exception("超级管理员不允许被删除！")
                else:
                    if user.delete():
                        ret = True
                        msg = "删除成功"
                    else:
                        msg = "删除失败！"
            else:
                raise Exception("该数据不存在！")
        except Exception as e:
            msg = str(e)
    else:
        msg = "request method not supported！"

    res = {
        "code": 1000 if ret else 0,
        "msg": msg
    }
    return jsonify(res)


@app.route('/user/logout')
def web_logout():
    if g_session_key_user in session:
        session.pop(g_session_key_user)

    return redirect("/")


@app.route('/user/login', methods=['GET', 'POST'])
def web_login():
    context = {}

    if request.method == 'POST':
        code = 0
        msg = "未知错误"

        params = request.form

        username = params.get("username", None)
        password = params.get("password", None)
        if username and password:
            context["username"] = username
            context["password"] = password
            user = User.query.filter_by(username=username).all()
            if len(user) > 0:
                user = user[0]
                if user.check_password(password):
                    if user.is_active:
                        user.last_login = datetime.now()
                        user.save()
                        session[g_session_key_user] = {
                            "id": user.id,
                            "username": username,
                            "email": user.email,
                            "is_superuser": user.is_superuser,
                            "is_active": user.is_active,
                            "is_staff": user.is_staff,
                        }
                        code = 1000
                        msg = "登录成功"
                    else:
                        msg = "账号已禁用"
                else:
                    msg = "密码错误"
            else:
                msg = "用户名未注册"
        else:
            msg = "请求参数不完整"
        res = {
            "code": code,
            "msg": msg
        }
        return jsonify(res)

    return render_template('app/web_login.html', context)
