
from app.tasks import LiveEncodingTask
from config.celery import celery

instance = LiveEncodingTask()
celery.register_task(instance)
instance.delay()
