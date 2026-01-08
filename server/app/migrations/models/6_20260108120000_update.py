
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Add thumbnail_info as a nullable JSON column
        ALTER TABLE "recorded_videos" ADD COLUMN "thumbnail_info" JSON;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Remove thumbnail_info column
        ALTER TABLE "recorded_videos" DROP COLUMN "thumbnail_info";
    """
