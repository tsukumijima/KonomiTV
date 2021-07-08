
import celery
import celery.utils.log


class LiveEncodingTask(celery.Task):

    def __init__(self):

        # タスク名
        self.name = 'LiveEncodingTask'

        # ロガー
        self.logger = celery.utils.log.get_task_logger(__name__)

    def run(self):

        self.logger.info('******** Hello World ********')

