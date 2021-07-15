
from django.urls import path

from .views import *


urlpatterns = [
    path('streams/live/<str:livestream_id>', LiveStreamAPI.as_view()),
    path('streams/live/<str:livestream_id>/mpegts', LiveMPEGTSStreamAPI.as_view()),
]
