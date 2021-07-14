
from app.tasks import LiveEncodingTask
from app.utils import LiveStreamID
from config.celery import celery

celery.register_task(LiveEncodingTask)


# ネットワーク ID (NID)・サービス ID (SID)
network_id = 32736
service_id = 1024
# 画質
quality = '1080p'

# エンコーダー
encoder_type = 'ffmpeg'
# 音声タイプ
audio_type = 'normal'


# ライブストリーム ID を取得
livestream_id = LiveStreamID.buildLiveStreamID(network_id, service_id, quality)

# タスクを実行
instance = LiveEncodingTask()
instance.run(livestream_id, encoder_type=encoder_type, audio_type=audio_type)
