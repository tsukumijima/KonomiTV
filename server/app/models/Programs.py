
import ariblib.constants
import datetime
import re
import requests
import time
from datetime import timedelta
from tortoise import fields
from tortoise import models
from tortoise import timezone

from app.constants import CONFIG
from app.utils import Logging
from app.utils import ZenkakuToHankaku


class Programs(models.Model):

    # テーブル設計は Notion を参照のこと
    id:str = fields.TextField(pk=True)
    channel_id:str = fields.TextField()
    title:str = fields.TextField()
    description:str = fields.TextField()
    detail:dict = fields.JSONField()
    start_time:datetime.datetime = fields.DatetimeField()
    end_time:datetime.datetime = fields.DatetimeField()
    duration:float = fields.FloatField()
    is_free:bool = fields.BooleanField()
    genre:list = fields.JSONField()
    video_type:str = fields.TextField()
    video_codec:str = fields.TextField()
    video_resolution:str = fields.TextField()
    audio_type:str = fields.TextField()
    audio_sampling_rate:str = fields.TextField()


    @classmethod
    async def update(cls):
        """番組情報を更新する"""

        def MillisecondToDatetime(millisecond: int) -> datetime.datetime:
            """ミリ秒を datetime に変換するラッパー"""
            return datetime.datetime.fromtimestamp(
                millisecond / 1000,  # ミリ秒なので秒に変換
                tz = timezone.get_default_timezone(),  # タイムゾーンを UTC+9（日本時間）に指定する
            )

        # 現在時刻のタイムスタンプ
        timestamp = time.time()

        # Mirakurun の API から番組情報を取得する
        mirakurun_programs_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/programs'
        programs = requests.get(mirakurun_programs_api_url).json()

        # 登録されている全ての番組を取得し、番組 ID (ex:NID32736-SID1024-EID11200) をキーに持つ辞書に変換する
        # EID (イベントID) だけでは一意にならないため、敢えて NID と SID も追加した ID としている
        db_programs = await Programs.all()
        duplicate_programs = {temp.id:temp for temp in db_programs}

        # 番組ごとに実行
        for program_info in programs:

            # 既にある番組情報の更新かどうか
            is_update = False

            # 番組タイトルがない（＝サブチャンネルでメインチャンネルの内容をそのまま放送している）を弾く
            if 'name' not in program_info:
                continue

            # 既に同じ番組 ID の番組が DB に登録されているなら（情報の更新がない場合のみ）スキップ
            # DB は読み取るよりも書き込みの方が負荷と時間がかかるため、不要な書き込みは極力避ける
            duplicate_program_id = f'NID{str(program_info["networkId"])}-SID{str(program_info["serviceId"]).zfill(3)}-EID{str(program_info["eventId"])}'
            if duplicate_program_id in duplicate_programs:

                # 重複している番組のモデルを取得
                duplicate_program = duplicate_programs[duplicate_program_id]

                # 番組終了時刻が現在時刻から1時間以上前ならレコードを削除
                if timezone.now() - duplicate_program.end_time > timedelta(hours=1):
                    Logging.debug(f'Delete Program: {duplicate_program.id}')
                    await duplicate_program.delete()

                # TODO: タイトル・番組概要・番組開始時刻・番組終了時刻がすべて同じならスキップ
                if (duplicate_program.title == ZenkakuToHankaku(program_info['name'])) and \
                   (duplicate_program.description == ZenkakuToHankaku(program_info['description'])) and \
                   (duplicate_program.start_time == MillisecondToDatetime(program_info['startAt'])) and \
                   (duplicate_program.end_time == MillisecondToDatetime(program_info['startAt'] + program_info['duration'])):

                    # 次のループへ
                    continue

                # すでに存在する番組情報を更新する
                else:
                    is_update = True

            # 番組終了時刻が現在時刻より1時間以上前な番組を弾く
            # 既に終わった番組を登録してもしょうがないし、番組を DB に入れれば入れるほど重くなるので不要なものは減らしたい
            if time.time() - ((program_info['startAt'] + program_info['duration']) / 1000) > (60 * 60):
                continue

            # 番組に紐づくチャンネルを取得
            from app.models import Channels  # 循環インポート防止のためここでインポート
            channel = await Channels.filter(network_id=program_info['networkId'], service_id=program_info['serviceId']).first()
            if channel is None:  # 登録されていないチャンネルの番組を弾く（ワンセグやデータ放送など）
                continue

            if is_update is False:
                # 新しい番組のレコードを作成
                program = Programs()
            else:
                # 既に存在する番組のレコードを設定
                program = duplicate_program

            # 取得してきた値を設定
            program.id = f'{channel.id}-EID{str(program_info["eventId"])}'  # チャンネルの ID に EID (イベントID) を追加する
            program.channel_id = channel.channel_id
            program.title = ZenkakuToHankaku(program_info['name'])
            program.description = ZenkakuToHankaku(program_info['description'])
            program.start_time = MillisecondToDatetime(program_info['startAt'])
            program.end_time = MillisecondToDatetime(program_info['startAt'] + program_info['duration'])
            program.duration = float(program_info['duration'] / 1000)  # ミリ秒なので秒に変換
            program.is_free = program_info['isFree']
            program.video_type = ariblib.constants.COMPONENT_TYPE[program_info['video']['streamContent']][program_info['video']['componentType']]
            program.video_codec = program_info['video']['type']
            program.video_resolution = program_info['video']['resolution']
            program.audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audio']['componentType']]
            program.audio_sampling_rate = str(program_info['audio']['samplingRate'] / 1000) + 'kHz'  # kHz に変換

            # 番組詳細
            if 'extended' not in program_info:
                ## extended がない場合
                program.detail = dict()  # 空の辞書を入れる
            else:
                ## 全角→半角へ変換するため、敢えて一度ばらしてから再構築する
                program.detail = dict()  # 辞書を定義
                for head, text in program_info['extended'].items():

                    # 見出しと本文
                    head_han = ZenkakuToHankaku(head)
                    text_han = ZenkakuToHankaku(text)
                    program.detail[head_han] = text_han

                    # 番組概要が空であれば番組詳細の最初の本文を概要として使う
                    # 空でまったく情報がないよりかは良いはず
                    if program.description == '':
                        program.description == text_han

            # ジャンル
            if 'genres' not in program_info:
                ## genres がない場合
                program.genre = list()  # 空のリストを入れる
            else:
                ## 数字だけでは開発中の視認性が低いのでテキストに変換する
                program.genre = list() # リストを定義
                for genre in program_info['genres']:

                    # major … 大分類
                    # middle … 中分類
                    genre_dict = {
                        'major': ariblib.constants.CONTENT_TYPE[genre['lv1']][0],
                        'middle': ariblib.constants.CONTENT_TYPE[genre['lv1']][1][genre['lv2']],
                    }

                    # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                    # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                    if genre_dict['major'] == '拡張':
                        if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                            user_nibble = (genre['un1'] * 0x10) + genre['un2']
                            genre_dict['middle'] = ariblib.constants.USER_TYPE[user_nibble]
                        # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                        else:
                            continue

                    program.genre.append(genre_dict)

            if is_update is False:
                Logging.debug(f'Add Program: {program.id}')
            else:
                Logging.debug(f'Update Program: {program.id}')

            # レコードを保存する
            await program.save()

        # Mirakurun の番組 ID (ex:327360102411200) をキーに持つ辞書に変換する
        mirakurun_programs = {temp['id']:temp for temp in programs}

        # DB に登録されているが Mirakurun の API レスポンスに存在しない番組を洗い出し、削除する
        # Mirakurun の API レスポンスに存在しないという事は何らかの理由で削除された番組なので、残しておくと幽霊化する
        for db_program in db_programs:

            # NID・SID・EID を抽出
            network_id, service_id, event_id = re.match(r'^NID([0-9]+)-SID([0-9]+)-EID([0-9]+)$', db_program.id).groups()

            # Mirakurun 形式の番組 ID を算出
            mirakurun_program_id = int(str(network_id).zfill(5) + str(service_id).zfill(5) + str(event_id).zfill(5))

            # Mirakurun の API レスポンスに存在しないなら番組を削除する
            if mirakurun_program_id not in mirakurun_programs:
                Logging.debug(f'Delete Program (ghost): {db_program.id}')
                await db_program.delete()

        Logging.info(f'Program update complete. ({round(time.time() - timestamp, 3)} sec)')
