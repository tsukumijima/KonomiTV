from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "clip_videos" ADD COLUMN "segments" TEXT NOT NULL DEFAULT '[]';
        UPDATE "clip_videos"
        SET "segments" = json_array(json_object('start_time', "start_time", 'end_time', "end_time"));
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "clip_videos" DROP COLUMN "segments";
    """
