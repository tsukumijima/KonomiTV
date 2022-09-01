
# --------------------------------------------------------------------------------------------------------------
# サードパーティーライブラリのダウンロードを行うステージ
# Docker のマルチステージビルドを使い、最終的な Docker イメージのサイズを抑え、ビルドキャッシュを効かせる
# --------------------------------------------------------------------------------------------------------------

# 念のため最終イメージに合わせて Ubuntu 22.04 LTS にしておく
## 中間イメージなので、サイズは（ビルドするマシンのディスク容量以外は）気にしなくて良い
FROM ubuntu:22.04 AS thirdparty-downloader

# apt-get に対話的に設定確認されないための設定
ENV DEBIAN_FRONTEND=noninteractive

# ダウンロード・展開に必要なパッケージのインストール
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends aria2 ca-certificates xz-utils

# サードパーティーライブラリをダウンロード
WORKDIR /
RUN aria2c -x10 https://github.com/tsukumijima/Storehouse/releases/download/KonomiTV-Thirdparty-Libraries-Prerelease/thirdparty-linux.tar.xz
RUN tar xvf thirdparty-linux.tar.xz

# --------------------------------------------------------------------------------------------------------------
# client をビルドするステージ
# client の dist 自体は Git に含まれているが、万が一ビルドし忘れたりや開発ブランチでの利便性を考慮してビルドしておく
# --------------------------------------------------------------------------------------------------------------

FROM node:16 AS client-builder

# 依存パッケージリストをコピー
COPY ./client/package.json ./client/yarn.lock /code/client/
WORKDIR /code/client
RUN yarn

# アプリケーションをコピー
COPY ./client /code/client

# クライアントをビルド
# /code/client/dist に成果物が作成される
RUN yarn build

# --------------------------------------------------------------------------------------------------------------
# メインのステージ
# ここで作成された実行時イメージが docker-compose up -d で起動される
# --------------------------------------------------------------------------------------------------------------

# Ubuntu 22.04 LTS (with CUDA) をベースイメージとして利用
# CUDA 付きなのは NVEncC を動かせるようにするため
FROM nvidia/cuda:11.7.0-runtime-ubuntu22.04

# タイムゾーンを東京に設定
ENV TZ=Asia/Tokyo

# apt-get に対話的に設定を確認されないための設定
ENV DEBIAN_FRONTEND=noninteractive

# Intel QSV と AMD VCE 関連のライブラリのインストール（実行時イメージなので RUN の最後に掃除する）
## Intel Graphics の apt リポジトリはまだ jammy (Ubuntu 22.04 LTS) に対応していないので、当面 focal (Ubuntu 20.04 LTS) 向けのを使う
## amdgpu 周りのインストール方法は amdgpu-install パッケージに同梱されているファイル群を参考にした
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gpg && \
    curl -fsSL https://repositories.intel.com/graphics/intel-graphics.key | gpg --dearmor -o /usr/share/keyrings/intel-graphics-keyring.gpg && \
    curl -fsSL https://repo.radeon.com/rocm/rocm.gpg.key | gpg --dearmor -o /usr/share/keyrings/rocm-keyring.gpg && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/graphics/ubuntu focal main' > /etc/apt/sources.list.d/intel-graphics.list && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/rocm-keyring.gpg] https://repo.radeon.com/amdgpu/22.20.1/ubuntu jammy main' > /etc/apt/sources.list.d/amdgpu.list && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/rocm-keyring.gpg] https://repo.radeon.com/amdgpu/22.20.1/ubuntu jammy proprietary' > /etc/apt/sources.list.d/amdgpu-proprietary.list && \
    echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/rocm-keyring.gpg] https://repo.radeon.com/rocm/apt/5.2 ubuntu main' > /etc/apt/sources.list.d/rocm.list && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        libfontconfig1 libfreetype6 libfribidi0 \
        intel-media-va-driver-non-free intel-opencl-icd libigfxcmrt7 libmfx1 libmfx-gen1.2 libva-drm2 libva-x11-2 ocl-icd-opencl-dev \
        amf-amdgpu-pro libamdenc-amdgpu-pro libdrm2-amdgpu vulkan-amdgpu-pro rocm-opencl-runtime opencl-legacy-amdgpu-pro-icd && \
    apt-get -y autoremove && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# ダウンロードしておいたサードパーティライブラリをコピー
COPY --from=thirdparty-downloader /thirdparty /code/server/thirdparty

# パッケージリスト (Pipfile / Pipfile.lock) だけをコピー
COPY ./server/Pipfile* /code/server/
WORKDIR /code/server

# 依存パッケージのインストール
## 仮想環境 (.venv) をプロジェクト直下に作成する
ENV PIPENV_VENV_IN_PROJECT true
RUN ./thirdparty/Python/bin/python -m pipenv sync --python="/code/server/thirdparty/Python/bin/python"

# 残りのアプリケーションをコピー
COPY ./server /code/server

# client の成果物をコピー (dist だけで良い)
COPY --from=client-builder /code/client/dist /code/client/dist

# データベースを必要な場合にアップグレードし、起動
ENTRYPOINT ./thirdparty/Python/bin/python -m pipenv run aerich upgrade && exec ./.venv/bin/python KonomiTV.py
