
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import statistics
import struct
from datetime import datetime
from typing import ClassVar

import httpx2 as httpx

from app import logging, schemas
from app.constants import HTTPX_CLIENT, JST
from app.models.Channel import Channel
from app.utils import Interlaced


class TorneClient:
    """
    torne のトル数 (torne の利用者がその番組を録画予約している数) を取得し、番組ごとに保持するクラス
    """

    # チャンネル種別と、トル数 API のレスポンスの放送グループの対応
    ## CATV (ISDB-C)・SKY (スカパー！プレミアムサービス)・BS4K は torne が対応していない放送種別のため、トル数 API のレスポンスに含まれない
    BROADCAST_GROUPS: ClassVar[dict[str, int]] = {'GR': 1, 'BS': 2, 'CS': 5}

    # 地上波の県域放送を受信していない環境で指定する地域識別 (東京)
    ## BS・CS のトル数は、どの地域を指定しても同じ値が返る
    DEFAULT_REGION_ID: ClassVar[int] = 23

    # 1回の取得でリクエストする日数
    ## 当日を含む8日分をリクエストすると、EPG 番組表に載っている1週間先までの番組のトル数を取得できる
    FETCH_DAYS: ClassVar[int] = 8

    # 番組 ID ごとのトル数のキャッシュ
    ## updateToruCounts() が、取得に成功するたびに全体を置き換える
    _toru_counts: ClassVar[dict[str, schemas.ToruCount]] = {}


    @classmethod
    def getToruCounts(cls) -> dict[str, schemas.ToruCount]:
        """
        番組 ID ごとのトル数を取得する (トル数の更新は updateToruCounts() で行う)

        Returns:
            dict[str, schemas.ToruCount]: 番組 ID をキーにしたトル数の辞書 (まだ取得できていない場合は空の辞書)
        """

        return cls._toru_counts


    @classmethod
    async def updateToruCounts(cls) -> None:
        """
        受信できるチャンネルの番組のトル数を torne のトル数 API から取得し、キャッシュを更新する
        更新したトル数は getToruCounts() で取得できる
        """

        # 受信できるチャンネルから、番組 ID の組み立てに使うネットワーク ID と、トル数を取得する地域を求める
        ## トル数 API のレスポンスは番組を放送グループ・サービス ID・イベント ID の組で表すため、
        ## 放送グループとサービス ID の組から、そのチャンネルのネットワーク ID を引けるようにしておく
        network_ids: dict[tuple[int, int], int] = {}
        region_ids: set[int] = set()
        for channel in await Channel.filter(is_watchable=True).all():
            broadcast_group = cls.BROADCAST_GROUPS.get(channel.type)
            if broadcast_group is None:
                continue
            network_ids[(broadcast_group, channel.service_id)] = channel.network_id

            # 地上波のサービス ID の上位6ビットは ARIB TR-B14 の地域識別で、県域放送の 10〜62 がトル数 API の地域の指定に対応する
            ## 広域放送の 1〜6 を指定しても空のレスポンスしか返らないため、同じ環境で受信している県域放送の地域から取得する
            region_id = channel.service_id >> 10
            if channel.type == 'GR' and 10 <= region_id <= 62:
                region_ids.add(region_id)

        # トル数を取得できるチャンネルが1つもない場合は何もしない
        if len(network_ids) == 0:
            return
        if len(region_ids) == 0:
            region_ids.add(cls.DEFAULT_REGION_ID)

        # 当日の 0:00 から FETCH_DAYS 日分のトル数を、地域ごとに取得する
        ## 認証に使う値は、リクエストに設定する直前に取得する
        start_date = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)
        payloads: dict[int, bytes] = {}
        try:
            async with HTTPX_CLIENT() as client:
                for region_id in sorted(region_ids):
                    response = await client.post(
                        url = 'https://syn.so-net.ne.jp/sen',
                        auth = (Interlaced(4), Interlaced(5)),
                        headers = {
                            'User-Agent': 'torne 150 (Android)',
                            'mobileIdAuth': Interlaced(6),
                        },
                        data = {
                            'op': 'opGetToruCount',
                            'userid': Interlaced(7),
                            'deviceid': Interlaced(8),
                            'version': Interlaced(9),
                            'regionid': str(region_id),
                            'startdate': start_date.strftime('%Y-%m-%dT%H:%M:%S%z'),
                            'duration': str(cls.FETCH_DAYS),
                        },
                        timeout = 10.0,
                    )
                    response.raise_for_status()
                    payloads[region_id] = response.content

        # 通信に失敗した場合は、前回取得したトル数をそのまま保持する
        ## トル数は地域ごとにカウントされているようで、岡山・香川のように県域を跨いで放送されている地域では別々に集計されているらしい
        ## このため取得できた地域だけを更新すると、取得できなかった地域の放送局の番組に、当該チャンネルがスピルオーバーで受信可能な
        ## 他県で集計された、通常よりも少ないトル数が設定されてしまいうる
        except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError) as ex:
            logging.warning('[TorneClient] Failed to fetch Toru counts:', exc_info=ex)
            return

        toru_counts: dict[str, schemas.ToruCount] = {}
        for payload in payloads.values():

            # レスポンス (バイナリ) の先頭の8バイトは全体のヘッダーで、2バイト目が放送グループの数を表す
            ## その後ろに、放送グループごとの8バイトのヘッダーが放送グループの数だけ並ぶ
            ## レスポンスの形式が想定と異なる場合は API サーバー側の仕様が変更されたと想定し、ValueError を送出して定期実行のエラーログに残す
            if len(payload) < 8:
                raise ValueError('The Toru count response is shorter than its header.')
            group_count = payload[1]
            offset = 8 * (group_count + 1)
            if offset > len(payload):
                raise ValueError('The Toru count response is shorter than its group headers.')

            # 放送グループ・サービス ID・イベント ID の組ごとのトル数を求める
            region_counts: dict[tuple[int, int, int], int] = {}
            for group_index in range(group_count):

                # 放送グループのヘッダーは、上位4ビットが放送グループ、下位32ビットがその放送グループのレコードの数を表す
                group_header, = struct.unpack_from('>Q', payload, 8 * (group_index + 1))
                broadcast_group = group_header >> 60
                end_offset = offset + (group_header & 0xFFFFFFFF) * 8
                if end_offset > len(payload):
                    raise ValueError('The Toru count response is shorter than its records.')

                # レコードは8バイトで、上位から順にサービス ID (16ビット)・イベント ID (16ビット)・トル数 (32ビット) がビッグエンディアンで並ぶ
                ## 複数日分のレスポンスではイベント ID が 0 のレコードに限り同じ組が複数回現れることがあるため、torne mobile と同じく最初のレコードを採用する
                for program_key, count in struct.iter_unpack('>II', payload[offset:end_offset]):
                    region_counts.setdefault((broadcast_group, program_key >> 16, program_key & 0xFFFF), count)
                offset = end_offset

            # すべての放送グループのレコードを読み終えた位置は、レスポンスの末尾と一致する
            if offset != len(payload):
                raise ValueError('The Toru count response has unexpected trailing data.')

            # 放送グループごとに、トル数の多さを色で示すときの基準値を求める
            ## torne mobile は放送グループごとに「平均 + 2 × 母標準偏差」の整数部分 (上限は最大値 - 1) を求め、トル数がこの値を上回る番組に人気マークを付ける
            ## ここでは色が付き始める最小のトル数として保持するため、求めた値に 1 を加えている
            group_counts: dict[int, list[int]] = {}
            for (broadcast_group, _, _), count in region_counts.items():
                group_counts.setdefault(broadcast_group, []).append(count)
            highlight_bases: dict[int, int] = {}
            for broadcast_group, counts in group_counts.items():
                max_count = max(counts)
                if max_count >= 2:
                    threshold = int(statistics.fmean(counts) + 2 * statistics.pstdev(counts))
                    highlight_bases[broadcast_group] = min(threshold, max_count - 1) + 1

            for (broadcast_group, service_id, event_id), count in region_counts.items():

                # 受信できるチャンネルの番組だけを保持する
                ## イベント ID が 0 のレコードは、対応する番組が番組表に存在しない
                network_id = network_ids.get((broadcast_group, service_id))
                if network_id is None or event_id == 0:
                    continue

                # 複数の地域から取得した場合は、最も多いトル数と、その地域の基準値を採用する
                ## 地域ごとのレスポンスは、その地域の利用者の録画予約を放送局を問わずに集計したものとみられる
                ## このため、ほかの地域の放送局の番組も少ないトル数で含まれるが、放送対象の地域のレスポンスが最も多いトル数を持つ
                program_id = f'NID{network_id}-SID{service_id:03d}-EID{event_id}'
                current_toru_count = toru_counts.get(program_id)
                if current_toru_count is None or count > current_toru_count['count']:
                    toru_counts[program_id] = schemas.ToruCount(
                        count = count,
                        highlight_base = highlight_bases.get(broadcast_group),
                    )

        cls._toru_counts = toru_counts
        logging.info(f'[TorneClient] Toru counts updated. (Regions: {sorted(region_ids)} / Programs: {len(toru_counts)})')
