
from django.apps import AppConfig

class AppConfig(AppConfig):

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    # ストリームデータを格納する変数
    livestream = {}
