from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "recorded_videos" ADD COLUMN "segment_map" JSON NOT NULL DEFAULT '[]';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "recorded_videos" DROP COLUMN "segment_map";
    """
