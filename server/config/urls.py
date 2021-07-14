"""config URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http.response import HttpResponse
from django.shortcuts import render
from django.urls import path, re_path, include
from django.views.generic import TemplateView

import app.urls


def favicon(request):
    # テンプレートのあるフォルダから favicon.ico を読み取って表示
    # render() や TemplateView はテキスト以外は非対応だが、どうしてもルートで表示させたい
    from .settings import TEMPLATES
    templates_folder = TEMPLATES[0]['DIRS'][0]
    with open(templates_folder / 'favicon.ico', 'rb') as f:
        return HttpResponse(f.read(), content_type='image/x-icon')

def manifest(request):
    return render(request, 'manifest.json', content_type='application/json')

def precache_manifest(request):
    return render(request, request.path.strip('/'), content_type='text/javascript')

def robots_txt(request):
    return render(request, 'robots.txt', content_type='text/plain')

def serviceworker_js(request):
    return render(request, 'service-worker.js', content_type='text/javascript')

urlpatterns = [

    # Django-Admin
    path('admin/', admin.site.urls),

    # API
    path('api/', include(app.urls)),

    # 直下に置く必要のある静的ファイル
    path('favicon.ico', favicon),
    path('manifest.json', manifest),
    re_path('^precache-manifest\..*\.js$', precache_manifest),
    path('robots.txt', robots_txt),
    path('service-worker.js', serviceworker_js),

    # それ以外は index.html を返す
    re_path('^.*$', TemplateView.as_view(template_name='index.html')),
]
