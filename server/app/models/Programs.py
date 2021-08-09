
import ariblib.constants
import datetime
import jaconv
import requests
from tortoise import fields
from tortoise import models
from tortoise.contrib.pydantic import pydantic_model_creator

from app.constants import CONFIG


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

        # Mirakurun の API から番組情報を取得する
        mirakurun_programs_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/programs'
        programs = requests.get(mirakurun_programs_api_url).json()

        # 番組ごとに実行
        for program_info in programs:

            # 番組タイトルがない（＝サブチャンネルでメインチャンネルの内容をそのまま放送している）を弾く
            if 'name' not in program_info:
                continue

            # 既に同じ番組が DB に登録されているならスキップ
            # DB は読み取るよりも書き込みの方が負荷と時間がかかるため、不要な書き込みは極力避ける
            if Programs.filter(
                id = f'NID{str(program_info["networkId"])}-SID{str(program_info["serviceId"])}-EID{str(program_info["eventId"])}'
            ).get_or_none() is not None:
                continue

            # 番組に紐づくチャンネルを取得
            from app.models import Channels  # 循環インポート防止のためここでインポート
            channel = await Channels.filter(network_id=program_info['networkId'], service_id=program_info['serviceId']).first()
            if channel is None:  # 登録されていないチャンネルの番組を弾く（ワンセグやデータ放送など）
                continue

            # 新しい番組のレコードを作成
            program = Programs()

            # 取得してきた値を設定
            program.id = f'{channel.id}-EID{str(program_info["eventId"])}'  # チャンネルの ID に EID (イベントID) を追加する
            program.channel_id = channel.channel_id
            program.title = jaconv.zen2han(program_info['name'], kana=False, digit=True, ascii=True)
            program.description = jaconv.zen2han(program_info['description'], kana=False, digit=True, ascii=True)
            program.start_time = datetime.datetime.fromtimestamp(
                program_info['startAt'] / 1000,  # ミリ秒なので秒に変換
                datetime.timezone(datetime.timedelta(hours=9)),  # タイムゾーンを UTC+9（日本時間）に指定する
            )
            program.end_time = datetime.datetime.fromtimestamp(
                (program_info['startAt'] + program_info['duration']) / 1000,  # ミリ秒なので秒に変換
                tz = datetime.timezone(datetime.timedelta(hours=9)),  # タイムゾーンを UTC+9（日本時間）に指定する
            )
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
                    head_han = jaconv.zen2han(head, kana=False, digit=True, ascii=True)
                    text_han = jaconv.zen2han(text, kana=False, digit=True, ascii=True)
                    program.detail[head_han] = text_han

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
                    program.genre.append({
                        'major': ariblib.constants.CONTENT_TYPE[genre['lv1']][0],
                        'middle': ariblib.constants.CONTENT_TYPE[genre['lv1']][1][genre['lv2']],
                    })

            # レコードを保存する
            await program.save()


# Pydantic のモデルに変換したもの
# FastAPI 側のバリデーションなどで扱いやすくなる
ProgramsPydantic = pydantic_model_creator(Programs, name='Programs')
