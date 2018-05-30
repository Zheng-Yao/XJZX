from flask import Blueprint, render_template
from models import UserInfo

news_blueprint = Blueprint('news', __name__)


@news_blueprint.route('/')
def index():
    return render_template('/news/index.html')
