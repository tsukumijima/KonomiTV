
# Ubuntu 20.04 LTS をベースイメージとして利用
FROM nvidia/cuda:11.4.1-runtime-ubuntu20.04
ENV TZ=Asia/Tokyo
ARG DEBIAN_FRONTEND=noninteractive

# アプリケーションをマウント
ADD ./ /code
WORKDIR /code/server

# ロケールの日本語化と初期パッケージのインストール
RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install -y gpg-agent locales language-pack-ja-base language-pack-ja
RUN locale-gen ja_JP.UTF-8
ENV LANG ja_JP.UTF-8

# サードパーティライブラリが必要とするパッケージのインストール
RUN apt-get install -y ffmpeg libv4l-0 libxcb1 libva2 libmfx1 intel-media-va-driver-non-free

# NVEncC 向けライブラリにシンボリックリンクを付与
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvcuvid.so.1 /usr/lib/x86_64-linux-gnu/libnvcuvid.so
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvidia-encode.so.1 /usr/lib/x86_64-linux-gnu/libnvidia-encode.so

# サードパーティライブラリに実行権限を付与
RUN chmod 755 ./thirdparty/arib-subtitle-timedmetadater/arib-subtitle-timedmetadater.elf && \
    chmod 755 ./thirdparty/FFmpeg/ffmpeg.elf && \
    chmod 755 ./thirdparty/FFmpeg/ffprobe.elf && \
    chmod 755 ./thirdparty/QSVEncC/QSVEncC.elf && \
    chmod 755 ./thirdparty/NVEncC/NVEncC.elf && \
    chmod 755 ./thirdparty/VCEEncC/VCEEncC.elf

# Python 3.9 のインストール
RUN apt-get install -y python3.9 python3-pip

# 依存パッケージのインストール
RUN pip install pipenv
## 仮想環境 (.venv) をプロジェクト直下に作成する
ENV PIPENV_VENV_IN_PROJECT true
## 既に pipenv sync を実行している場合に発生するエラーを回避
RUN rm -rf .venv
RUN pipenv sync

# データベースを必要な場合にアップグレードし、起動
ENTRYPOINT pipenv run aerich upgrade && exec pipenv run serve
