
# サードパーティーライブラリのダウンロードを行うステージ
# 念のため最終イメージに合わせて ubuntu20.04 にしておく
# 中間イメージなので、サイズは（ビルドするマシンのディスク容量以外は）気にしなくて良い
FROM ubuntu:20.04 AS thirdparty-downloader

# apt-get に対話的に設定確認されないための設定
ENV DEBIAN_FRONTEND=noninteractive

# パッケージ一覧更新、全体の更新
RUN apt-get update -y && apt-get upgrade -y

# ダウンロード・展開に必要なパッケージのインストール
RUN apt-get install -y --no-install-recommends \
    aria2 \
    binutils \
    ca-certificates \
    gpg-agent \
    p7zip-full \
    xz-utils

# VCEEncC が依存する AMD AMF ライブラリをダウンロードし、展開
# サードパーティーライブラリよりも更新されにくいので先にする
RUN aria2c -x10 https://drivers.amd.com/drivers/linux/amdgpu-pro-21.30-1290604-ubuntu-20.04.tar.xz --referer=www.amd.com
RUN tar xvf amdgpu-pro-21.30-1290604-ubuntu-20.04.tar.xz && rm amdgpu-pro-21.30-1290604-ubuntu-20.04.tar.xz && \
    cd amdgpu-pro-21.30-1290604-ubuntu-20.04 && ar vx amf-amdgpu-pro_21.30-1290604_amd64.deb && tar xvf data.tar.xz && \
    cp -r opt/amdgpu-pro/lib/x86_64-linux-gnu/libamfrt64.so.0.0.0 /usr/lib/x86_64-linux-gnu/libamfrt64.so
RUN ln -s /usr/lib/x86_64-linux-gnu/libamfrt64.so /usr/lib/x86_64-linux-gnu/libamfrt64.so.1

# サードパーティーライブラリをダウンロード
WORKDIR /thirdparty
RUN aria2c -x10 https://github.com/tsukumijima/KonomiTV/releases/download/v0.5.0/thirdparty.7z
RUN 7z x -y thirdparty.7z

# サードパーティーライブラリに実行権限を付与
RUN chmod 755 ./thirdparty/FFmpeg/ffmpeg.elf && \
    chmod 755 ./thirdparty/FFmpeg/ffprobe.elf && \
    chmod 755 ./thirdparty/QSVEncC/QSVEncC.elf && \
    chmod 755 ./thirdparty/NVEncC/NVEncC.elf && \
    chmod 755 ./thirdparty/tsreadex/tsreadex.elf && \
    chmod 755 ./thirdparty/VCEEncC/VCEEncC.elf

# client のビルド
FROM node:16 AS client-builder

# 依存パッケージリストをコピー
COPY ./client/package.json ./client/yarn.lock /code/client/
WORKDIR /code/client
RUN yarn

# アプリケーションをコピー
COPY ./client /code/client

# クライアントをビルド、/code/client/dist に成果物が作成される
RUN yarn build

# server のセットアップ兼実行時のイメージ
# Ubuntu 20.04 LTS をベースイメージとして利用
FROM nvidia/cuda:11.4.1-runtime-ubuntu20.04

# タイムゾーンを東京に設定
ENV TZ=Asia/Tokyo

# apt-get に対話的に設定確認されないための設定
ENV DEBIAN_FRONTEND=noninteractive

# パッケージのインストール（実行時イメージなのでRUNの最後に掃除する）
RUN apt-get update -y && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    python3.9 \
    python3-pip \
    ffmpeg \
    libv4l-0 \
    libxcb1 \
    libva2 \
    libmfx1 \
    intel-media-va-driver-non-free && \
    apt-get -y autoremove && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# pipenv をインストール
RUN pip install pipenv

# NVEncC が依存する NVENC ライブラリにシンボリックリンクを付与
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvcuvid.so.1 /usr/lib/x86_64-linux-gnu/libnvcuvid.so
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvidia-encode.so.1 /usr/lib/x86_64-linux-gnu/libnvidia-encode.so

# VCEEncC が依存する AMD AMF ライブラリにシンボリックリンクを付与
COPY --from=thirdparty-downloader /usr/lib/x86_64-linux-gnu/libamfrt64.so* /usr/lib/x86_64-linux-gnu/

# パッケージリストだけをコピー
COPY ./server/Pipfile* /code/server/
WORKDIR /code/server

# 依存パッケージのインストール
## 仮想環境 (.venv) をプロジェクト直下に作成する
ENV PIPENV_VENV_IN_PROJECT true
RUN pipenv sync

# 残りのアプリケーションをコピー
COPY ./server /code/server

# ダウンロードしておいたサードパーティライブラリをコピー
COPY --from=thirdparty-downloader /thirdparty/thirdparty /code/server/thirdparty

# client の成果物をコピー (dist だけで良い)
COPY --from=client-builder /code/client/dist /code/client/dist

# データベースを必要な場合にアップグレードし、起動
ENTRYPOINT pipenv run aerich upgrade && exec pipenv run serve
