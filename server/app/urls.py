
from django.urls import path
from .views import LiveMPEGTSStreamAPI


urlpatterns = [
    path('streams/live/<str:livestream_id>/mpegts', LiveMPEGTSStreamAPI.as_view()),
]
