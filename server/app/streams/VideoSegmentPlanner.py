from __future__ import annotations

import bisect
import math
from fractions import Fraction

from biim.mpeg2ts import ts

from app.schemas import KeyFrame, SegmentMapEntry


class VideoSegmentPlanner:
    """
    仮想 HLS セグメント長と segment_map 変換規則をまとめるユーティリティ
    """


    @staticmethod
    def computeSegmentDurationSeconds(video_frame_rate: float) -> float:
        """
        録画のフレームレートから、約 6 秒に最も近い整数フレーム長を秒数へ変換する

        Args:
            video_frame_rate (float): DB に保存されているフレームレート

        Returns:
            float: HLS プレイリストへ記載する通常セグメント長
        """

        # メタデータが壊れている録画でもプレイリスト生成を止めず、従来値の 6 秒で扱う
        if video_frame_rate <= 0:
            return 6.0

        frame_rate = VideoSegmentPlanner.__normalizeFrameRate(video_frame_rate)
        segment_frame_count = round(float(frame_rate) * 6.0)
        return float(Fraction(segment_frame_count, 1) / frame_rate)


    @staticmethod
    def convertKeyFramesToSegmentMap(
        key_frames: list[KeyFrame],
        video_frame_rate: float,
        duration_seconds: float,
    ) -> list[SegmentMapEntry]:
        """
        既存の key_frames から、新しいオンデマンド解決と同じ規則の segment_map を生成する

        Args:
            key_frames (list[KeyFrame]): 旧 KeyFrameAnalyzer が保存したキーフレーム一覧
            video_frame_rate (float): DB に保存されているフレームレート
            duration_seconds (float): 録画ファイルの総再生時間

        Returns:
            list[SegmentMapEntry]: HLS シーケンス番号ごとの入力開始位置キャッシュ
        """

        # 旧 KeyFrameAnalyzer は末尾シーク用の番兵を追加するため、最後の要素は実キーフレームとして扱わない
        ## 実キーフレームが 1 件も残らない録画はキャッシュを作らず、再生時のオンデマンド探索に任せる
        usable_key_frames = key_frames[:-1]
        if len(usable_key_frames) == 0 or duration_seconds <= 0:
            return []

        segment_duration_seconds = VideoSegmentPlanner.computeSegmentDurationSeconds(video_frame_rate)
        segment_duration_ticks = round(segment_duration_seconds * ts.HZ)
        segment_count = max(1, math.ceil(duration_seconds / segment_duration_seconds))
        source_base_dts = usable_key_frames[0]['dts']
        dts_list = [key_frame['dts'] for key_frame in usable_key_frames]

        segment_map: list[SegmentMapEntry] = []
        for sequence_index in range(segment_count):
            # プレイリスト上の時刻に対し、その時刻以前で最も近いキーフレームを採用する
            ## 既存 key_frames からの移行結果と新規オンデマンド解決結果を同じ分割規則で扱う
            playlist_start_seconds = sequence_index * segment_duration_seconds
            target_dts = source_base_dts + round(playlist_start_seconds * ts.HZ)
            key_frame_index = bisect.bisect_right(dts_list, target_dts) - 1
            if key_frame_index < 0:
                key_frame_index = 0
            key_frame = usable_key_frames[key_frame_index]

            # 負の値は要求時刻より後ろのキーフレームなので、セグメント冒頭の映像を欠く
            keyframe_age_ticks = target_dts - key_frame['dts']
            if keyframe_age_ticks < 0:
                continue

            # 旧 key_frames が途中で途切れている録画では、最後のキーフレームが残り全セグメントへ割り当たる
            ## 後続キーフレームが存在する場合は長い GOP 内に目標時刻があるだけなので、キャッシュとして採用する
            if keyframe_age_ticks >= segment_duration_ticks and key_frame_index == len(usable_key_frames) - 1:
                continue

            segment_map.append(SegmentMapEntry(
                sequence_index = sequence_index,
                source_file_position = key_frame['offset'],
                source_start_dts = key_frame['dts'],
            ))

        return segment_map


    @staticmethod
    def __normalizeFrameRate(video_frame_rate: float) -> Fraction:
        """
        DB に保存済みの小数フレームレートを、代表的な放送系の有理数へ戻す

        Args:
            video_frame_rate (float): DB に保存されているフレームレート

        Returns:
            Fraction: セグメント基準長の計算に使うフレームレート
        """

        # MetadataAnalyzer は FFprobe の分数値を float に変換して保存するため、
        ## DB 上では 30000/1001 が 29.97 のように丸められている
        known_rates = [
            (Fraction(60000, 1001), 0.05),
            (Fraction(30000, 1001), 0.05),
            (Fraction(24000, 1001), 0.05),
            (Fraction(15000, 1001), 0.05),
            (Fraction(60, 1), 0.05),
            (Fraction(50, 1), 0.05),
            (Fraction(30, 1), 0.05),
            (Fraction(25, 1), 0.05),
            (Fraction(24, 1), 0.05),
            (Fraction(15, 1), 0.05),
        ]
        for known_rate, tolerance in known_rates:
            if abs(float(known_rate) - video_frame_rate) <= tolerance:
                return known_rate
        return Fraction(video_frame_rate).limit_denominator(100000)
