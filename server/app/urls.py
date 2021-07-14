
from django.urls import path

from .views import *


urlpatterns = [
    path('test', TestAPI.as_view()),
    path('streams/live/<str:livestream_id>/mpegts', LiveMPEGTSStreamAPI.as_view()),
]
