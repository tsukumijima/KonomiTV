
import os
from celery import Celery

from app import tasks

# Django の設定のあるモジュールのパスを定義
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Celery を初期化し、設定を読み込む
celery = Celery('config')
celery.config_from_object('django.conf:settings', namespace='CELERY')

# Celery に登録するタスク
# 参考: https://qiita.com/kaki_k/items/c2166323942b651989cc
celery.register_task(tasks.LiveEncodingTask)
