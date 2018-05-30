from flask import Blueprint, make_response, session, request, jsonify, current_app, render_template, redirect
from utils.captcha.captcha import captcha
from utils.ytx_sdk.ytx_send import sendTemplateSMS
import random, functools
import re
from models import db, UserInfo, NewsInfo, NewsCategory
from utils.qiniu_xjzx import upload_pic
from datetime import datetime

user_blueprint = Blueprint('user', __name__, url_prefix='/user')


# 图片验证码
@user_blueprint.route('/image_yzm')
def image_yzm():
    name, yzm, buffer = captcha.generate_captcha()
    response = make_response(buffer)
    response.mimetype = 'image/png'
    session['image_yzm'] = yzm
    print('调用了验证码')
    return response


# 短信验证码
@user_blueprint.route('/sms_yzm')
def sms_yzm():
    dict1 = request.args
    mobile = dict1.get('mobile')
    image_yzm = dict1.get('image_yzm')
    if image_yzm != session['image_yzm']:
        return jsonify(result=1)
    yzm = random.randint(1000, 9999)
    session['sms_yzm'] = yzm
    sendTemplateSMS(mobile, {yzm, 5}, 1)
    print(yzm)
    return jsonify(result=2)


# 注册页面提交请求，并且加入CSRF保护
@user_blueprint.route('/register', methods=['POST'])
def register():
    print('请求')
    dict1 = request.form
    mobile = dict1.get('mobile')
    image_yzm = dict1.get('image_yzm')
    sms_yzm = int(dict1.get('sms_yzm'))
    pwd = dict1.get('pwd')
    print(sms_yzm)
    print(type(sms_yzm))
    print(session['sms_yzm'])
    print(type(session['sms_yzm']))
    if not all([mobile, image_yzm, sms_yzm, pwd]):
        # 参数不完整
        return jsonify(result=1)
    if image_yzm != session['image_yzm']:
        return jsonify(result=2)
    if sms_yzm != session['sms_yzm']:
        return jsonify(result=3)
    # 验证密码
    if not re.match(r'[a-zA-Z0-9_]{6,20}', pwd):
        return jsonify(result=4)
    # 判断手机是否存在
    mobile_count = UserInfo.query.filter_by(mobile=mobile).count()
    if mobile_count > 0:
        return jsonify(result=5)
    try:
        # 插入数据
        user = UserInfo()
        user.nick_name = mobile
        user.mobile = mobile
        user.password = pwd
        # 提交
        db.session.add(user)
        db.session.commit()
    except:
        # 输出错误日志
        current_app.logger_xjzx.error('注册用户时，数据库访问失败')
        return jsonify(result=6)
    return jsonify(result=7)


# 登陆
@user_blueprint.route('/login', methods=['POST'])
def login():
    dict1 = request.form
    mobile = dict1.get('mobile')
    pwd = dict1.get('password')
    user = UserInfo.query.filter_by(mobile=mobile).first()
    # 输入空
    if not all([mobile, pwd]):
        return jsonify(result=1)
    if user:
        # 登陆成功
        # 状态保持
        session['user_id'] = user.id
        print(user.check_pwd)
        if user.check_pwd(pwd):
            return jsonify(result=2, avatar=user.avatar, nick_name=user.nick_name)

        else:
            # 密码不正确
            return jsonify(result=3)
    else:
        # 用户不存在
        return jsonify(result=4)


# 退出
@user_blueprint.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id')
    return jsonify(result=1)


# 定义登陆状态失效跳转首页的装饰器
def login_required(f):
    # 为了让路径指向
    @functools.wraps(f)
    def fun2(*args, **kwargs):
        if 'user_id' in session:
            return redirect('/')
        return f(*args, **kwargs)

    return fun2


# 用户中心首页index
@login_required
@user_blueprint.route('/')
def index():
    user_id = session['user_id']
    user = UserInfo.query.get(user_id)
    return render_template('news/user.html', user=user, title='用户中心')


# 右侧视图：基本资料
@login_required
@user_blueprint.route('/base', methods=['GET', 'POST'])
def base():
    user_id = session['user_id']
    user = UserInfo.query.get(user_id)
    if request.method == 'GET':
        return render_template('news/user_base_info.html', user=user)
    elif request.method == 'POST':
        dict1 = request.form
        user.signature = dict1.get('signature')
        user.nick_name = dict1.get('nick_name')
        user.gender = True if dict1.get('gender') == 'True' else False
        try:
            db.session.commit()
        except:
            current_app.logger_xjzx.error('修改用户基本信息连接数据库失败')
            return jsonify(result=1)
        return jsonify(result=2)


# 头像
@login_required
@user_blueprint.route('/pic', methods=['GET', 'POST'])
def pic():
    user_id = session['user_id']
    user = UserInfo.query.get(user_id)
    if request.method == 'GET':
        return render_template('news/user_pic_info.html', user=user)
    elif request.method == 'POST':
        f1 = request.files.get('avatar')
        f1_name = upload_pic(f1)
        user.avatar = f1_name
        try:
            db.session.commit()
        except:
            current_app.logger_xjzx.error('修改用户头像连接数据库失败')
            return jsonify(result=1)
        return jsonify(result=2, avatar_url=user.avatar_url)


@login_required
@user_blueprint.route('/follow')
def follow():
    user_id = session['user_id']
    user = UserInfo.query.get(user_id)
    page = int(request.args.get('page', default='1'))
    pagination = user.follow_user.paginate(page, 4, False)
    # 获取当前页的用户数据
    user_list = pagination.items
    total_page = pagination.pages
    return render_template(
        'news/user_follow.html',
        user_list=user_list,
        total_page=total_page,
        user=user,
        page=page
    )


@login_required
@user_blueprint.route('/collect')
def collect():
    user_id = session['user_id']
    user = UserInfo.query.get(user_id)
    page = int(request.args.get('page', default='1'))
    pagination = user.news_collect.order_by(NewsInfo.id.desc()).paginate(page, 6, False)
    news_list = pagination.items
    total_pages = pagination.pages
    return render_template(
        'news/user_collection.html',
        news_list=news_list,
        page=page,
        total_pages=total_pages,
    )


@login_required
@user_blueprint.route('/newslist')
def newslist():
    user_id = session['user_id']
    user = UserInfo.query.get(user_id)
    page = int(request.args.get('page', default='1'))
    pagination = user.news.order_by(NewsInfo.update_time.desc()).paginate(page, 6, False)
    news_list = pagination.items
    total_pages = pagination.pages
    # print("测试", news_list)
    return render_template(
        'news/user_news_list.html',
        page=page,
        news_list=news_list,
        total_pages=total_pages,
    )


@login_required
@user_blueprint.route('/pwd', methods=['GET', "POST"])
def pwd():
    if request.method == 'GET':
        return render_template('news/user_pass_info.html')
    elif request.method == 'POST':
        msg = '修改成功'
        dict1 = request.form
        pwd = dict1.get('current_pwd')
        new_pwd = dict1.get('new_pwd')
        new_pwd2 = dict1.get('new_pwd2')
        if not all([pwd, new_pwd, new_pwd2]):
            return render_template('news/user_pass_info.html', msg='密码都不能为空')
        if not re.match(r'[a-zA-Z0-9_]{6,20}', new_pwd):
            return render_template('news/user_pass_info.html', msg='密码格式不正确')
        if new_pwd != new_pwd2:
            return render_template('news/user_pass_info.html', msg='两次输入密码不一致')
        user = UserInfo.query.get(session['user_id'])
        if not user.check_pwd(pwd):
            return render_template('news/user_pass_info.html', msg='当前密码错误')
        user.password = new_pwd
        db.session.commit()
        return render_template('news/user_pass_info.html', msg=msg)


@login_required
@user_blueprint.route('/release', methods=['GET', 'POST'])
def release():
    category_list = NewsCategory.query.all()
    news_id = request.args.get('news_id')
    if request.method == 'GET':
        if news_id is None:

            return render_template('news/user_news_release.html', category_list=category_list, news=None)
        else:
            news = NewsInfo.query.get(int(news_id))
            return render_template(
                'news/user_news_release.html',
                category_list=category_list,
                news=news
            )
    elif request.method == 'POST':
        dict1 = request.form
        title = dict1.get('title')
        summary = dict1.get('summary')
        content = dict1.get('content')
        news_pic = request.files.get('news_pic')
        category_id = dict1.get('category')
        if news_id is None:
            if not all([title, summary, content, news_pic]):
                return render_template(
                    'news/user_news_release.html',
                    msg='请将数据填写完整',
                    category_list=category_list
                )
        else:
            if not all([title, category_id, summary, content]):
                return render_template(
                    'news/user_news_release.html',
                    category_list=category_list,
                    msg='请将数据填写完整'
                )
        if news_pic:
            # 将图片数据上传七牛云
            filename = upload_pic(news_pic)

        # 添加
        # 3.添加
        if news_id is None:
            news = NewsInfo()
        else:
            news = NewsInfo.query.get(news_id)
        news.category_id = int(category_id)
        if news_pic:
            news.pic = filename
        news.title = title
        news.summary = summary
        news.content = content
        news.status = 1
        news.update_time = datetime.now()
        news.user_id = session['user_id']

        # 4.提交到数据库
        db.session.add(news)
        db.session.commit()

        return redirect('/user/newslist')
