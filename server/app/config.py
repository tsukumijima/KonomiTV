
import logging.config
import ruamel.yaml
import logging
import sys
from pathlib import Path
from typing import Any

from app.constants import (
    AKEBI_LOG_PATH,
    BASE_DIR,
    KONOMITV_ACCESS_LOG_PATH,
    KONOMITV_SERVER_LOG_PATH,
    LOGGING_CONFIG,
)


# 設定ファイルのパス
CONFIG_YAML = BASE_DIR.parent / 'config.yaml'

# 設定ファイルが配置されていない場合
if Path.exists(CONFIG_YAML) is False:

    # 前回のログをすべて削除
    try:
        if KONOMITV_SERVER_LOG_PATH.exists():
            KONOMITV_SERVER_LOG_PATH.unlink()
        if KONOMITV_ACCESS_LOG_PATH.exists():
            KONOMITV_ACCESS_LOG_PATH.unlink()
        if AKEBI_LOG_PATH.exists():
            AKEBI_LOG_PATH.unlink()
    except PermissionError:
        pass

    # Uvicorn を起動する前に Uvicorn のロガーを使えるようにする
    logging.config.dictConfig(LOGGING_CONFIG)
    __logger = logging.getLogger('uvicorn')

    # 処理を続行できないのでここで終了する
    __logger.error('設定ファイルが配置されていないため、KonomiTV を起動できません。')
    __logger.error('config.example.yaml を config.yaml にコピーし、お使いの環境に合わせて編集してください。')
    sys.exit(1)

# 設定ファイルからサーバー設定を読み込む
with open(CONFIG_YAML, encoding='utf-8') as file:
    CONFIG: dict[str, dict[str, Any]] = dict(ruamel.yaml.YAML().load(file))  # type: ignore

    # EDCB / Mirakurun の URL の末尾のスラッシュをなしに統一
    ## これをやっておかないと Mirakurun の URL の末尾にスラッシュが入ってきた場合に接続に失敗する
    ## EDCB に関しては統一する必要はないが、念のため
    CONFIG['general']['edcb_url'] = CONFIG['general']['edcb_url'].rstrip('/')
    CONFIG['general']['mirakurun_url'] = CONFIG['general']['mirakurun_url'].rstrip('/')

    # Docker 上で実行されているとき、サーバー設定のうち、パス指定の項目に Docker 環境向けの Prefix (/host-rootfs) を付ける
    ## /host-rootfs (docker-compose.yaml で定義) を通してホストマシンのファイルシステムにアクセスできる
    if Path.exists(Path('/.dockerenv')) is True:
        __docker_fs_prefix = '/host-rootfs'
        CONFIG['capture']['upload_folder'] = __docker_fs_prefix + CONFIG['capture']['upload_folder']
        if type(CONFIG['tv']['debug_mode_ts_path']) is str:
            CONFIG['tv']['debug_mode_ts_path'] = __docker_fs_prefix + CONFIG['tv']['debug_mode_ts_path']
