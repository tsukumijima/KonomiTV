
# Django の起動時に Celery を初期化する
from .celery import app as celery_app
__all__ = ['celery_app']
