
# Ubuntu 20.04 LTS をベースイメージとして利用
FROM nvidia/cuda:11.4.1-runtime-ubuntu20.04

# タイムゾーンを東京に設定
ENV TZ=Asia/Tokyo

# アプリケーションをマウント
ADD ./ /code
WORKDIR /code/server

# Python 3.9 のインストールとロケールの日本語化
## DEBIAN_FRONTEND=noninteractive はダイヤログを無視するおまじない
RUN apt-get update -y && apt-get upgrade -y
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y aria2 gpg-agent language-pack-ja-base language-pack-ja locales p7zip-full python3.9 python3-pip
RUN locale-gen ja_JP.UTF-8
ENV LANG ja_JP.UTF-8

# サードパーティライブラリが必要とするパッケージのインストール
RUN apt-get install -y ffmpeg libv4l-0 libxcb1 libva2 libmfx1 intel-media-va-driver-non-free

# サードパーティライブラリをダウンロード
RUN aria2c -x10 https://github.com/tsukumijima/KonomiTV/releases/download/v0.4.0/thirdparty.7z
RUN 7z x -y thirdparty.7z && rm thirdparty.7z

# サードパーティライブラリに実行権限を付与
RUN chmod 755 ./thirdparty/FFmpeg/ffmpeg.elf && \
    chmod 755 ./thirdparty/FFmpeg/ffprobe.elf && \
    chmod 755 ./thirdparty/QSVEncC/QSVEncC.elf && \
    chmod 755 ./thirdparty/NVEncC/NVEncC.elf && \
    chmod 755 ./thirdparty/tsreadex/tsreadex.elf && \
    chmod 755 ./thirdparty/VCEEncC/VCEEncC.elf

# NVEncC が依存する NVENC ライブラリにシンボリックリンクを付与
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvcuvid.so.1 /usr/lib/x86_64-linux-gnu/libnvcuvid.so
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvidia-encode.so.1 /usr/lib/x86_64-linux-gnu/libnvidia-encode.so

# VCEEncC が依存する AMD AMF ライブラリをダウンロードし、シンボリックリンクを付与
RUN aria2c -x10 https://drivers.amd.com/drivers/linux/amdgpu-pro-21.30-1290604-ubuntu-20.04.tar.xz --referer=www.amd.com
RUN tar xvf amdgpu-pro-21.30-1290604-ubuntu-20.04.tar.xz && rm amdgpu-pro-21.30-1290604-ubuntu-20.04.tar.xz && \
    cd amdgpu-pro-21.30-1290604-ubuntu-20.04 && ar vx amf-amdgpu-pro_21.30-1290604_amd64.deb && tar xvf data.tar.xz && \
    cp -r opt/amdgpu-pro/lib/x86_64-linux-gnu/libamfrt64.so.0.0.0 /usr/lib/x86_64-linux-gnu/libamfrt64.so && \
    cd ../ && rm -rf amdgpu-pro-21.30-1290604-ubuntu-20.04/
RUN ln -s /usr/lib/x86_64-linux-gnu/libamfrt64.so /usr/lib/x86_64-linux-gnu/libamfrt64.so.1

# 依存パッケージのインストール
## 仮想環境 (.venv) をプロジェクト直下に作成する
ENV PIPENV_VENV_IN_PROJECT true
RUN pip install pipenv
RUN pipenv sync

# データベースを必要な場合にアップグレードし、起動
ENTRYPOINT pipenv run aerich upgrade && exec pipenv run serve
