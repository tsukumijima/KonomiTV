from fastapi import APIRouter

from app.schemas import DiscordStatus


router = APIRouter(
    tags = ['Discord'],
    prefix = '/api',
)

@router.get(
    '/discord/status',
    summary = 'Discord 接続状況取得 API',
    response_description = 'Discord Bot の接続状況。',
    response_model = DiscordStatus,
)
async def DiscordStatusAPI():
    """
    Discord Bot の接続状況を取得する。
    """
    try:
        # discord.pyから接続状態を取得する
        import discord_main
        connected = discord_main.is_bot_running
        return DiscordStatus(connected=connected)
    except ImportError:
        # discord.pyがインポートできない場合は未接続とする
        return DiscordStatus(connected=False)
    except Exception:
        # その他のエラーの場合も未接続とする
        return DiscordStatus(connected=False)
