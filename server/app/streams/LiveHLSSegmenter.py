
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

import asyncio
import gc
import math
import time
from collections import deque
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from typing import cast

from app.config import Config
from app.utils import Logging

from biim.mpeg2ts import ts
from biim.mpeg2ts.pat import PATSection
from biim.mpeg2ts.pmt import PMTSection
from biim.mpeg2ts.pes import PES
from biim.mpeg2ts.h264 import H264PES
from biim.mpeg2ts.h265 import H265PES
from biim.mpeg2ts.parser import SectionParser, PESParser

from biim.hls.m3u8 import M3U8

from biim.mp4.box import ftyp, moov, mvhd, mvex, trex, moof, mdat, emsg
from biim.mp4.avc import avcTrack
from biim.mp4.hevc import hevcTrack
from biim.mp4.mp4a import mp4aTrack


class LiveHLSSegmenter:

    # ターゲットとする LL-HLS 部分セグメント (m4s) の再生時間 (秒)
    PART_DURATION = 0.5

    # m3u8 プレイリストに含めるセグメントの最大数
    LIST_SIZE = 10


    def __init__(self, gop_length_second: float) -> None:
        """
        ライブストリーミング用 LL-HLS Segmenter を初期化する

        Args:
            gop_length_second (float): エンコード後のストリームの GOP 長
        """

        # デバッグ時のみ CORS ヘッダーを有効化
        if Config().general.debug is True:
            self.cors_headers = {
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Allow-Origin': '*',
            }
        else:
            self.cors_headers = {}

        # EXT-X-TARGETDURATION に小数を与えると再生されないので、小数点以下は切り上げ
        gop_length_second_int: int = math.ceil(gop_length_second)

        # M3U8 プレイリストのインスタンスを初期化
        ## 映像+主音声と映像+副音声のプレイリストは別々に管理する
        self._primary_audio_m3u8 = M3U8(
            target_duration = gop_length_second_int,
            part_target = self.PART_DURATION,
            window_size = self.LIST_SIZE,
            hasInit = True,
        )
        self._secondary_audio_m3u8 = M3U8(
            target_duration = gop_length_second_int,
            part_target = self.PART_DURATION,
            window_size = self.LIST_SIZE,
            hasInit = True,
        )

        # init: 最初の初期セグメントを格納するための Future オブジェクト
        self._primary_audio_init: asyncio.Future[bytes] = asyncio.Future()
        self._secondary_audio_init: asyncio.Future[bytes] = asyncio.Future()

        # MPEG2-TS の各セクションのパーサーを初期化
        self._pat_parser: SectionParser[PATSection] = SectionParser(PATSection)
        self._pmt_parser: SectionParser[PMTSection] = SectionParser(PMTSection)
        self._h264_pes_parser: PESParser[H264PES] = PESParser(H264PES)
        self._h265_pes_parser: PESParser[H265PES] = PESParser(H265PES)
        self._aac_pes_parser_PA: PESParser[PES] = PESParser(PES)
        self._aac_pes_parser_SA: PESParser[PES] = PESParser(PES)
        self._id3_pes_parser: PESParser[PES] = PESParser(PES)

        # PCR (Program Clock Reference)
        self._PCR_PID: int | None = None
        self._LATEST_PCR_VALUE: int | None = None
        self._LATEST_PCR_TIMESTAMP_90KHZ: int | None = 0
        self._LATEST_PCR_DATETIME: datetime | None = None
        self._LATEST_VIDEO_TIMESTAMP_90KHZ: int | None = None
        self._LATEST_VIDEO_MONOTONIC_TIME: float | None = None
        self._LATEST_VIDEO_SLEEP_DIFFERENCE: float = 0

        # エンコーダーから送られてきた MPEG2-TS 内の各トラックの PID
        self._PMT_PID: int | None = None
        self._H264_PID: int | None = None
        self._H265_PID: int | None = None
        self._AAC_PID_PA: int | None = None  # 主音声
        self._AAC_PID_SA: int | None = None  # 副音声
        self._ID3_PID: int | None = None

        # AAC 音声トラックの設定データ
        self._aac_config_PA: tuple[bytes, int, int] | None = None  # 主音声
        self._aac_config_SA: tuple[bytes, int, int] | None = None  # 副音声

        # H.264 / H.265 映像トラック関連の一時変数
        self._curr_h264_data: tuple[bool, deque[bytes], int, int, datetime] | None = None
        self._next_h264_data: tuple[bool, deque[bytes], int, int, datetime] | None = None
        self._curr_h265_data: tuple[bool, deque[bytes], int, int, datetime] | None = None
        self._next_h265_data: tuple[bool, deque[bytes], int, int, datetime] | None = None
        self._vps_data: bytes | None = None
        self._sps_data: bytes | None = None
        self._pps_data: bytes | None = None

        # フラグメント化された各トラックのデータを一時的に格納する Deque
        self._h264_fragments: deque[bytes] = deque()
        self._h265_fragments: deque[bytes] = deque()
        self._aac_fragments_PA: deque[bytes] = deque()
        self._aac_fragments_SA: deque[bytes] = deque()
        self._emsg_fragments: deque[bytes] = deque()

        # 初期セグメント (init) の作成が完了したかどうか
        self._initialization_segment_dispatched = False

        # 部分セグメントの開始 PTS (Packet Time Stamp) (のはず…)
        self._partial_begin_timestamp: int | None = None


    async def getPlaylist(self, msn: int | None, part: int | None, secondary_audio: bool = False) -> Response:
        """
        LL-HLS のプレイリスト (m3u8) を FastAPI のレスポンスとして返す
        ref: https://developer.apple.com/documentation/http_live_streaming/enabling_low-latency_http_live_streaming_hls

        Args:
            msn (int | None): LL-HLS プレイリストの msn (Media Sequence Number) インデックス
            part (int | None): LL-HLS プレイリストの part (部分セグメント) インデックス
            secondary_audio (bool, optional): 副音声用セグメントを取得するかどうか. Defaults to False.

        Returns:
            Response: プレイリストデータ (m3u8) の FastAPI レスポンス
        """

        # 副音声用セグメントが指定されたら _secondary_audio_m3u8 を、そうでなければ主音声用の _primary_audio_m3u8 を使う
        m3u8 = self._secondary_audio_m3u8 if secondary_audio is True else self._primary_audio_m3u8

        # _HLS_msn も _HLS_part も指定されていなければ、普通にプレイリストを返す
        if msn is None and part is None:

            # 通常モードで m3u8 プレイリストを生成
            future = m3u8.plain()
            if future is None:
                Logging.error('[LiveHLSSegmenter][getPlaylist] m3u8.plain() returned None')
                return Response(status_code=422, media_type='application/vnd.apple.mpegurl', headers=self.cors_headers)

            # m3u8 プレイリストが生成されるまで待ってから返す
            ## m3u8 プレイリストは m3u8.continuousSegment() または m3u8.completeSegment() が呼ばれた段階で生成される
            playlist: str = await future
            return Response(content=playlist, media_type='application/vnd.apple.mpegurl', headers=self.cors_headers)

        # 少なくとも _HLS_msn が指定されているので、次のセグメントが生成されるまで待ってからプレイリストを返す
        else:

            # _HLS_part だけ指定されていることはありえない
            if msn is None:
                Logging.error('[LiveHLSSegmenter][getPlaylist] msn is None')
                return Response(status_code=422, media_type='application/vnd.apple.mpegurl', headers=self.cors_headers)

            # _HLS_part が指定されていなければ、0 に設定
            if part is None:
                part = 0

            # ブロッキングモードで m3u8 プレイリストを生成
            future = m3u8.blocking(msn, part)
            if future is None:
                Logging.error('[LiveHLSSegmenter][getPlaylist] m3u8.blocking() returned None')
                return Response(status_code=422, media_type='application/vnd.apple.mpegurl', headers=self.cors_headers)

            # m3u8 プレイリストが生成されるまで待ってから返す
            ## m3u8 プレイリストは指定された msn と part に紐づくセグメント/部分セグメントの生成が完了した段階で生成される
            ## 正直どう動いているのかあまり理解できていない…
            playlist: str = await future
            return Response(content=playlist, media_type='application/vnd.apple.mpegurl', headers=self.cors_headers)


    async def getSegment(self, msn: int | None, secondary_audio: bool = False) -> Response | StreamingResponse:
        """
        LL-HLS の完全なセグメント (m4s) を FastAPI のレスポンスとして順次返す
        ref: https://developer.apple.com/documentation/http_live_streaming/enabling_low-latency_http_live_streaming_hls

        Args:
            msn (int | None): LL-HLS セグメントの msn (Media Sequence Number) インデックス
            secondary_audio (bool, optional): 副音声用セグメントを取得するかどうか. Defaults to False.

        Returns:
            Response | StreamingResponse: セグメントデータ (m4s) の FastAPI レスポンス (StreamingResponse)
        """

        # 副音声用セグメントが指定されたら _secondary_audio_m3u8 を、そうでなければ主音声用の _primary_audio_m3u8 を使う
        m3u8 = self._secondary_audio_m3u8 if secondary_audio is True else self._primary_audio_m3u8

        # msn が指定されていなければ、0 に設定
        if msn is None:
            msn = 0

        # 完全なセグメントを Queue の形で取得する
        queue = await m3u8.segment(msn)
        if queue is None:
            Logging.error('[LiveHLSSegmenter][getSegment] m3u8.segment() returned None')
            return Response(status_code=422, media_type='video/mp4', headers=self.cors_headers)

        # Queue からセグメントデータを取得して StreamingResponse で返す
        async def generator():
            while True:
                stream = await queue.get()
                if stream == None:
                    break
                yield bytes(stream)

        return StreamingResponse(generator(), media_type='video/mp4', headers=self.cors_headers)


    async def getPartialSegment(self, msn: int | None, part: int | None, secondary_audio: bool = False) -> Response | StreamingResponse:
        """
        LL-HLS の部分セグメント (m4s) を FastAPI のレスポンスとして順次返す
        ref: https://developer.apple.com/documentation/http_live_streaming/enabling_low-latency_http_live_streaming_hls

        Args:
            msn (int | None): LL-HLS セグメントの msn (Media Sequence Number) インデックス
            part (int | None): LL-HLS セグメントの part (部分セグメント) インデックス
            secondary_audio (bool, optional): 副音声用セグメントを取得するかどうか. Defaults to False.

        Returns:
            Response | StreamingResponse: 部分セグメントデータ (m4s) の FastAPI レスポンス (StreamingResponse)
        """

        # 副音声用セグメントが指定されたら _secondary_audio_m3u8 を、そうでなければ主音声用の _primary_audio_m3u8 を使う
        m3u8 = self._secondary_audio_m3u8 if secondary_audio is True else self._primary_audio_m3u8

        # msn が指定されていなければ、0 に設定
        if msn is None:
            msn = 0

        # part が指定されていなければ、0 に設定
        if part is None:
            part = 0

        # 部分セグメントを Queue の形で取得する
        queue = await m3u8.partial(msn, part)
        if queue is None:
            Logging.error('[LiveHLSSegmenter][getPartialSegment] m3u8.partial() returned None')
            return Response(status_code=422, media_type='video/mp4', headers=self.cors_headers)

        # Queue からセグメントデータを取得して StreamingResponse で返す
        async def generator():
            while True:
                stream = await queue.get()
                if stream == None:
                    break
                yield bytes(stream)

        return StreamingResponse(generator(), media_type='video/mp4', headers=self.cors_headers)


    async def getInitializationSegment(self, secondary_audio: bool = False) -> Response:
        """
        LL-HLS の初期セグメント (init) を FastAPI のレスポンスとして返す
        ref: https://developer.apple.com/documentation/http_live_streaming/enabling_low-latency_http_live_streaming_hls

        Args:
            secondary_audio (bool, optional): 副音声用セグメントを取得するかどうか. Defaults to False.

        Returns:
            Response: 初期セグメントデータ (m4s) の FastAPI レスポンス
        """

        # 副音声用セグメントが指定されたら _secondary_audio_init を、そうでなければ主音声用の _primary_audio_init を使う
        init = self._secondary_audio_init if secondary_audio is True else self._primary_audio_init

        # 初期セグメントの生成が完了するまで待機
        init_segment: bytes = await asyncio.shield(init)

        # 初期セグメントデータを返す
        return Response(init_segment, media_type='video/mp4', headers=self.cors_headers)


    def pushTSPacketData(self, packet: bytes) -> None:
        """
        LiveEncodingTask からエンコードした MPEG2-TS パケットを受け取り、LL-HLS セグメントの生成処理を行う
        LiveEncodingTask でエンコーダーからの 188 bytes ごとの出力を受け取るたびに呼び出される
        packet は必ず 188 bytes である必要がある

        Args:
            packet (bytes): 188 bytes の MPEG2-TS パケット
        """

        SAMPLING_FREQUENCY = {
            0x00: 96000,
            0x01: 88200,
            0x02: 64000,
            0x03: 48000,
            0x04: 44100,
            0x05: 32000,
            0x06: 24000,
            0x07: 22050,
            0x08: 16000,
            0x09: 12000,
            0x0a: 11025,
            0x0b: 8000,
            0x0c: 7350,
        }

        # TS パケットの PID を取得
        PID: int = ts.pid(packet)

        # H.264 映像トラック
        if PID == self._H264_PID:
            self._h264_pes_parser.push(packet)
            for H264 in self._h264_pes_parser:
                if self._LATEST_PCR_VALUE is None: continue
                if self._LATEST_PCR_DATETIME is None: continue
                dts = cast(int, H264.dts() if H264.has_dts() else H264.pts())
                pts = cast(int, H264.pts())
                cts = (pts - dts + ts.PCR_CYCLE) % ts.PCR_CYCLE
                timestamp = ((dts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) + self._LATEST_PCR_TIMESTAMP_90KHZ
                program_date_time: datetime = self._LATEST_PCR_DATETIME + timedelta(seconds=(((dts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) / ts.HZ))
                keyframe_in_samples = False
                samples = deque()

                for ebsp in H264:
                    nal_unit_type = ebsp[0] & 0x1f

                    if nal_unit_type == 0x07: # SPS
                        self._sps_data = ebsp
                    elif nal_unit_type == 0x08: # PPS
                        self._pps_data = ebsp
                    elif nal_unit_type == 0x09 or nal_unit_type == 0x06: # AUD or SEI
                        pass
                    elif nal_unit_type == 0x05:
                        keyframe_in_samples = True
                        samples.append(ebsp)
                    else:
                        samples.append(ebsp)
                self._next_h264_data = (keyframe_in_samples, samples, timestamp, cts, program_date_time) if samples else None

                has_IDR = False
                begin_timestamp: int | None = None
                begin_program_date_time: datetime | None = None
                if self._curr_h264_data:
                    has_key_frame, samples, dts, cts, pdt = self._curr_h264_data
                    has_IDR = has_key_frame
                    begin_timestamp = dts
                    begin_program_date_time = pdt
                    duration = timestamp - dts
                    content = bytearray()
                    while samples:
                        ebsp = samples.popleft()
                        content += len(ebsp).to_bytes(4, byteorder='big') + ebsp

                    self._h264_fragments.append(
                        b''.join([
                            moof(0,
                                [
                                    (1, duration, dts, 0, [(len(content), duration, has_key_frame, cts)])
                                ]
                            ),
                            mdat(content)
                        ])
                    )
                self._next_h264_data, self._curr_h264_data = self._curr_h264_data, self._next_h264_data

                if self._sps_data and self._pps_data and self._aac_config_PA and self._aac_config_SA and not self._initialization_segment_dispatched:
                    self._primary_audio_init.set_result(b''.join([
                        ftyp(),
                        moov(
                            mvhd(ts.HZ),
                            mvex([
                                trex(1),
                                trex(2),
                            ]),
                            [
                                avcTrack(1, ts.HZ, self._sps_data, self._pps_data),
                                mp4aTrack(2, ts.HZ, *self._aac_config_PA),  # type: ignore
                            ]
                        )
                    ]))
                    self._secondary_audio_init.set_result(b''.join([
                        ftyp(),
                        moov(
                            mvhd(ts.HZ),
                            mvex([
                                trex(1),
                                trex(2),
                            ]),
                            [
                                avcTrack(1, ts.HZ, self._sps_data, self._pps_data),
                                mp4aTrack(2, ts.HZ, *self._aac_config_SA),  # type: ignore
                            ]
                        )
                    ]))
                    self._initialization_segment_dispatched = True

                if begin_timestamp is None: continue

                if has_IDR:
                    if self._partial_begin_timestamp is not None:
                        PART_DIFF = begin_timestamp - self._partial_begin_timestamp
                        if self.PART_DURATION * ts.HZ < PART_DIFF:
                            self._partial_begin_timestamp = int(begin_timestamp - max(0, PART_DIFF - self.PART_DURATION * ts.HZ))
                            self._primary_audio_m3u8.continuousPartial(self._partial_begin_timestamp, False)
                            self._secondary_audio_m3u8.continuousPartial(self._partial_begin_timestamp, False)
                    self._partial_begin_timestamp = begin_timestamp
                    self._primary_audio_m3u8.continuousSegment(self._partial_begin_timestamp, True, begin_program_date_time)
                    self._secondary_audio_m3u8.continuousSegment(self._partial_begin_timestamp, True, begin_program_date_time)
                elif self._partial_begin_timestamp is not None:
                    PART_DIFF = begin_timestamp - self._partial_begin_timestamp
                    if self.PART_DURATION * ts.HZ <= PART_DIFF:
                        self._partial_begin_timestamp = int(begin_timestamp - max(0, PART_DIFF - self.PART_DURATION * ts.HZ))
                        self._primary_audio_m3u8.continuousPartial(self._partial_begin_timestamp)
                        self._secondary_audio_m3u8.continuousPartial(self._partial_begin_timestamp)

                while self._emsg_fragments:
                    data = self._emsg_fragments.popleft()
                    self._primary_audio_m3u8.push(data)
                    self._secondary_audio_m3u8.push(data)
                while self._h264_fragments:
                    data = self._h264_fragments.popleft()
                    self._primary_audio_m3u8.push(data)
                    self._secondary_audio_m3u8.push(data)
                while self._aac_fragments_PA:
                    self._primary_audio_m3u8.push(self._aac_fragments_PA.popleft())
                while self._aac_fragments_SA:
                    self._secondary_audio_m3u8.push(self._aac_fragments_SA.popleft())

                if self._LATEST_VIDEO_TIMESTAMP_90KHZ is not None and self._LATEST_VIDEO_MONOTONIC_TIME is not None:
                    TIMESTAMP_DIFF = (begin_timestamp - self._LATEST_VIDEO_TIMESTAMP_90KHZ) / ts.HZ  # type: ignore
                    TIME_DIFF = time.monotonic() - self._LATEST_VIDEO_MONOTONIC_TIME  # type: ignore
                    # if args.input is not sys.stdin.buffer:
                    #     SLEEP_BEGIN = time.monotonic()
                    #     time.sleep(max(0, TIMESTAMP_DIFF - (TIME_DIFF + self._LATEST_VIDEO_SLEEP_DIFFERENCE)))
                    #     SLEEP_END = time.monotonic()
                    #     self._LATEST_VIDEO_SLEEP_DIFFERENCE = (SLEEP_END - SLEEP_BEGIN) - max(0, TIMESTAMP_DIFF - (TIME_DIFF + self._LATEST_VIDEO_SLEEP_DIFFERENCE))
                self._LATEST_VIDEO_TIMESTAMP_90KHZ = begin_timestamp
                self._LATEST_VIDEO_MONOTONIC_TIME = time.monotonic()

        # H.265 映像トラック
        elif PID == self._H265_PID:
            self._h265_pes_parser.push(packet)
            for H265 in self._h265_pes_parser:
                if self._LATEST_PCR_VALUE is None: continue
                if self._LATEST_PCR_DATETIME is None: continue
                dts = cast(int, H265.dts() if H265.has_dts() else H265.pts())
                pts = cast(int, H265.pts())
                cts = (pts - dts + ts.PCR_CYCLE) % ts.PCR_CYCLE
                timestamp = ((dts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) + self._LATEST_PCR_TIMESTAMP_90KHZ
                program_date_time: datetime = self._LATEST_PCR_DATETIME + timedelta(seconds=(((dts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) / ts.HZ))
                keyframe_in_samples = False
                samples: deque[bytes] = deque()

                for ebsp in H265:
                    nal_unit_type = (ebsp[0] >> 1) & 0x3f

                    if nal_unit_type == 0x20: # VPS
                        self._vps_data = ebsp
                    elif nal_unit_type == 0x21: # SPS
                        self._sps_data = ebsp
                    elif nal_unit_type == 0x22: # PPS
                        self._pps_data = ebsp
                    elif nal_unit_type == 0x23 or nal_unit_type == 0x27: # AUD or SEI
                        pass
                    elif nal_unit_type == 19 or nal_unit_type == 20 or nal_unit_type == 21: # IDR_W_RADL, IDR_W_LP, CRA_NUT
                        keyframe_in_samples = True
                        samples.append(ebsp)
                    else:
                        samples.append(ebsp)
                self._next_h265_data = (keyframe_in_samples, samples, timestamp, cts, program_date_time) if samples else None

                has_IDR = False
                begin_timestamp: int | None = None
                begin_program_date_time: datetime | None = None
                if self._curr_h265_data:
                    has_key_frame, samples, dts, cts, pdt = self._curr_h265_data
                    has_IDR = has_key_frame
                    begin_timestamp = dts
                    begin_program_date_time = pdt
                    duration = timestamp - dts
                    content = bytearray()
                    while samples:
                        ebsp = samples.popleft()
                        content += len(ebsp).to_bytes(4, byteorder='big') + ebsp

                    self._h265_fragments.append(
                        b''.join([
                            moof(0,
                                [
                                    (1, duration, dts, 0, [(len(content), duration, has_key_frame, cts)])
                                ]
                            ),
                            mdat(content)
                        ])
                    )
                self._next_h265_data, self._curr_h265_data = self._curr_h265_data, self._next_h265_data

                if self._vps_data and self._sps_data and self._pps_data and self._aac_config_PA and self._aac_config_SA and not self._initialization_segment_dispatched:
                    self._primary_audio_init.set_result(b''.join([
                        ftyp(),
                        moov(
                            mvhd(ts.HZ),
                            mvex([
                                trex(1),
                                trex(2),
                            ]),
                            [
                                hevcTrack(1, ts.HZ, self._vps_data, self._sps_data, self._pps_data),
                                mp4aTrack(2, ts.HZ, *self._aac_config_PA),  # type: ignore
                            ]
                        )
                    ]))
                    self._secondary_audio_init.set_result(b''.join([
                        ftyp(),
                        moov(
                            mvhd(ts.HZ),
                            mvex([
                                trex(1),
                                trex(2),
                            ]),
                            [
                                hevcTrack(1, ts.HZ, self._vps_data, self._sps_data, self._pps_data),
                                mp4aTrack(2, ts.HZ, *self._aac_config_SA),  # type: ignore
                            ]
                        )
                    ]))
                    self._initialization_segment_dispatched = True

                if begin_timestamp is None: continue

                if has_IDR:
                    if self._partial_begin_timestamp is not None:
                        PART_DIFF = begin_timestamp - self._partial_begin_timestamp
                        if self.PART_DURATION * ts.HZ < PART_DIFF:
                            self._partial_begin_timestamp = int(begin_timestamp - max(0, PART_DIFF - self.PART_DURATION * ts.HZ))
                            self._primary_audio_m3u8.continuousPartial(self._partial_begin_timestamp, False)
                            self._secondary_audio_m3u8.continuousPartial(self._partial_begin_timestamp, False)
                    self._partial_begin_timestamp = begin_timestamp
                    self._primary_audio_m3u8.continuousSegment(self._partial_begin_timestamp, True, begin_program_date_time)
                    self._secondary_audio_m3u8.continuousSegment(self._partial_begin_timestamp, True, begin_program_date_time)
                elif self._partial_begin_timestamp is not None:
                    PART_DIFF = begin_timestamp - self._partial_begin_timestamp
                    if self.PART_DURATION * ts.HZ <= PART_DIFF:
                        self._partial_begin_timestamp = int(begin_timestamp - max(0, PART_DIFF - self.PART_DURATION * ts.HZ))
                        self._primary_audio_m3u8.continuousPartial(self._partial_begin_timestamp)
                        self._secondary_audio_m3u8.continuousPartial(self._partial_begin_timestamp)

                while self._emsg_fragments:
                    data = self._emsg_fragments.popleft()
                    self._primary_audio_m3u8.push(data)
                    self._secondary_audio_m3u8.push(data)
                while self._h265_fragments:
                    data = self._h265_fragments.popleft()
                    self._primary_audio_m3u8.push(data)
                    self._secondary_audio_m3u8.push(data)
                while self._aac_fragments_PA:
                    self._primary_audio_m3u8.push(self._aac_fragments_PA.popleft())
                while self._aac_fragments_SA:
                    self._secondary_audio_m3u8.push(self._aac_fragments_SA.popleft())

                if self._LATEST_VIDEO_TIMESTAMP_90KHZ is not None and self._LATEST_VIDEO_MONOTONIC_TIME is not None:
                    TIMESTAMP_DIFF = (begin_timestamp - self._LATEST_VIDEO_TIMESTAMP_90KHZ) / ts.HZ  # type: ignore
                    TIME_DIFF = time.monotonic() - self._LATEST_VIDEO_MONOTONIC_TIME  # type: ignore
                    # if args.input is not sys.stdin.buffer:
                    #     SLEEP_BEGIN = time.monotonic()
                    #     time.sleep(max(0, TIMESTAMP_DIFF - (TIME_DIFF + self._LATEST_VIDEO_SLEEP_DIFFERENCE)))
                    #     SLEEP_END = time.monotonic()
                    #     self._LATEST_VIDEO_SLEEP_DIFFERENCE = (SLEEP_END - SLEEP_BEGIN) - max(0, TIMESTAMP_DIFF - (TIME_DIFF + self._LATEST_VIDEO_SLEEP_DIFFERENCE))
                self._LATEST_VIDEO_TIMESTAMP_90KHZ = begin_timestamp
                self._LATEST_VIDEO_MONOTONIC_TIME = time.monotonic()

        # AAC 音声トラック (主音声)
        elif PID == self._AAC_PID_PA:
            self._aac_pes_parser_PA.push(packet)
            for AAC_PES in self._aac_pes_parser_PA:
                if self._LATEST_PCR_VALUE is None: continue
                pts = cast(int, AAC_PES.pts())
                timestamp = ((pts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) + self._LATEST_PCR_TIMESTAMP_90KHZ
                begin, ADTS_AAC = 0, AAC_PES.PES_packet_data()
                length = len(ADTS_AAC)
                while begin < length:
                    protection = (ADTS_AAC[begin + 1] & 0b00000001) == 0
                    profile = ((ADTS_AAC[begin + 2] & 0b11000000) >> 6)
                    samplingFrequencyIndex = ((ADTS_AAC[begin + 2] & 0b00111100) >> 2)
                    channelConfiguration = ((ADTS_AAC[begin + 2] & 0b00000001) << 2) | ((ADTS_AAC[begin + 3] & 0b11000000) >> 6)
                    frameLength = ((ADTS_AAC[begin + 3] & 0x03) << 11) | (ADTS_AAC[begin + 4] << 3) | ((ADTS_AAC[begin + 5] & 0xE0) >> 5)
                    if not self._aac_config_PA:
                        self._aac_config_PA = (bytes([
                            ((profile + 1) << 3) | ((samplingFrequencyIndex & 0x0E) >> 1),
                            ((samplingFrequencyIndex & 0x01) << 7) | (channelConfiguration << 3)
                        ]), channelConfiguration, SAMPLING_FREQUENCY[samplingFrequencyIndex])
                    duration = 1024 * ts.HZ // SAMPLING_FREQUENCY[samplingFrequencyIndex]
                    self._aac_fragments_PA.append(
                        b''.join([
                            moof(0,
                                [
                                    (2, duration, timestamp, 0, [(frameLength - (9 if protection else 7), duration, False, 0)])
                                ]
                            ),
                            mdat(bytes(ADTS_AAC[begin + (9 if protection else 7): begin + frameLength]))
                        ])
                    )
                    timestamp += duration
                    begin += frameLength

        # AAC 音声トラック (副音声)
        elif PID == self._AAC_PID_SA:
            self._aac_pes_parser_SA.push(packet)
            for AAC_PES in self._aac_pes_parser_SA:
                if self._LATEST_PCR_VALUE is None: continue
                pts = cast(int, AAC_PES.pts())
                timestamp = ((pts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) + self._LATEST_PCR_TIMESTAMP_90KHZ
                begin, ADTS_AAC = 0, AAC_PES.PES_packet_data()
                length = len(ADTS_AAC)
                while begin < length:
                    protection = (ADTS_AAC[begin + 1] & 0b00000001) == 0
                    profile = ((ADTS_AAC[begin + 2] & 0b11000000) >> 6)
                    samplingFrequencyIndex = ((ADTS_AAC[begin + 2] & 0b00111100) >> 2)
                    channelConfiguration = ((ADTS_AAC[begin + 2] & 0b00000001) << 2) | ((ADTS_AAC[begin + 3] & 0b11000000) >> 6)
                    frameLength = ((ADTS_AAC[begin + 3] & 0x03) << 11) | (ADTS_AAC[begin + 4] << 3) | ((ADTS_AAC[begin + 5] & 0xE0) >> 5)
                    if not self._aac_config_SA:
                        self._aac_config_SA = (bytes([
                            ((profile + 1) << 3) | ((samplingFrequencyIndex & 0x0E) >> 1),
                            ((samplingFrequencyIndex & 0x01) << 7) | (channelConfiguration << 3)
                        ]), channelConfiguration, SAMPLING_FREQUENCY[samplingFrequencyIndex])
                    duration = 1024 * ts.HZ // SAMPLING_FREQUENCY[samplingFrequencyIndex]
                    self._aac_fragments_SA.append(
                        b''.join([
                            moof(0,
                                [
                                    (2, duration, timestamp, 0, [(frameLength - (9 if protection else 7), duration, False, 0)])
                                ]
                            ),
                            mdat(bytes(ADTS_AAC[begin + (9 if protection else 7): begin + frameLength]))
                        ])
                    )
                    timestamp += duration
                    begin += frameLength

        # PAT (Program Association Table)
        elif PID == 0x00:
            self._pat_parser.push(packet)
            for PAT in self._pat_parser:
                if PAT.CRC32() != 0: continue

                for program_number, program_map_PID in PAT:
                    if program_number == 0: continue

                    if not self._PMT_PID:
                        self._PMT_PID = program_map_PID

        # PMT (Program Map Table)
        elif PID == self._PMT_PID:
            self._pmt_parser.push(packet)
            for PMT in self._pmt_parser:
                if PMT.CRC32() != 0: continue

                self._PCR_PID = PMT.PCR_PID
                for stream_type, elementary_PID, _ in PMT:
                    if stream_type == 0x1b and self._H264_PID is None:
                        self._H264_PID = elementary_PID
                        Logging.debug_simple('[LiveHLSSegmenter] H.264 Track: ' + hex(self._H264_PID))
                    elif stream_type == 0x24 and self._H265_PID is None:
                        self._H265_PID = elementary_PID
                        Logging.debug_simple('[LiveHLSSegmenter] H.265 Track: ' + hex(self._H265_PID))
                    elif stream_type == 0x0F:
                        if self._AAC_PID_PA is None:
                            self._AAC_PID_PA = elementary_PID
                            Logging.debug_simple('[LiveHLSSegmenter] AAC Track (Primary): ' + hex(self._AAC_PID_PA))
                        elif self._AAC_PID_SA is None:
                            self._AAC_PID_SA = elementary_PID
                            Logging.debug_simple('[LiveHLSSegmenter] AAC Track (Secondary): ' + hex(self._AAC_PID_SA))
                    elif stream_type == 0x15 and self._ID3_PID is None:
                        self._ID3_PID = elementary_PID
                        Logging.debug_simple('[LiveHLSSegmenter] ID3 (ARIB Caption) Track: ' + hex(self._ID3_PID))

        # Timed Metadata (ID3) トラック
        ## Timed Metadata に変換された ARIB 字幕データが入る
        elif PID == self._ID3_PID:
            self._id3_pes_parser.push(packet)
            for ID3_PES in self._id3_pes_parser:
                if self._LATEST_PCR_VALUE is None: continue
                pts = cast(int, ID3_PES.pts())
                timestamp = ((pts - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) + self._LATEST_PCR_TIMESTAMP_90KHZ
                ID3 = ID3_PES.PES_packet_data()
                self._emsg_fragments.append(emsg(ts.HZ, timestamp, None, 'https://aomedia.org/emsg/ID3', ID3))

        else:
            pass

        # PCR (Program Clock Reference)
        if PID == self._PCR_PID and ts.has_pcr(packet):
            PCR_VALUE = (cast(int, ts.pcr(packet)) - ts.HZ + ts.PCR_CYCLE) % ts.PCR_CYCLE
            PCR_DIFF = ((PCR_VALUE - self._LATEST_PCR_VALUE + ts.PCR_CYCLE) % ts.PCR_CYCLE) if self._LATEST_PCR_VALUE is not None else 0
            self._LATEST_PCR_TIMESTAMP_90KHZ = cast(int, self._LATEST_PCR_TIMESTAMP_90KHZ) + PCR_DIFF
            if self._LATEST_PCR_DATETIME is None: self._LATEST_PCR_DATETIME = datetime.now(timezone.utc) - timedelta(seconds=(1))
            self._LATEST_PCR_DATETIME += timedelta(seconds=(PCR_DIFF / ts.HZ))
            self._LATEST_PCR_VALUE = PCR_VALUE


    def destroy(self) -> None:
        """
        インスタンス変数をすべて破棄し、メモリを解放する
        実際は Python の GC がよしなになんとかしてくれそうだけど、念のため…
        """

        del self._primary_audio_m3u8
        del self._secondary_audio_m3u8

        del self._primary_audio_init
        del self._secondary_audio_init

        del self._pat_parser
        del self._pmt_parser
        del self._h264_pes_parser
        del self._h265_pes_parser
        del self._aac_pes_parser_PA
        del self._aac_pes_parser_SA
        del self._id3_pes_parser

        del self._PCR_PID
        del self._LATEST_PCR_VALUE
        del self._LATEST_PCR_TIMESTAMP_90KHZ
        del self._LATEST_PCR_DATETIME
        del self._LATEST_VIDEO_TIMESTAMP_90KHZ
        del self._LATEST_VIDEO_MONOTONIC_TIME
        del self._LATEST_VIDEO_SLEEP_DIFFERENCE

        del self._PMT_PID
        del self._H264_PID
        del self._H265_PID
        del self._AAC_PID_PA
        del self._AAC_PID_SA
        del self._ID3_PID

        del self._aac_config_PA
        del self._aac_config_SA

        del self._curr_h264_data
        del self._next_h264_data
        del self._curr_h265_data
        del self._next_h265_data
        del self._vps_data
        del self._sps_data
        del self._pps_data

        del self._h264_fragments
        del self._h265_fragments
        del self._aac_fragments_PA
        del self._aac_fragments_SA
        del self._emsg_fragments

        del self._initialization_segment_dispatched
        del self._partial_begin_timestamp

        # 強制的にガベージコレクションを実行する
        gc.collect()
