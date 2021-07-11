
from app.tasks import LiveEncodingTask
from config.celery import celery

celery.register_task(LiveEncodingTask)

instance = LiveEncodingTask()
instance.run() # 同期実行
# instance.delay() # 非同期実行
