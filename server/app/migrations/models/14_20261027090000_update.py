from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "recorded_videos" ADD COLUMN "missing_since" TIMESTAMP;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM "recorded_programs" WHERE "id" IN (SELECT "recorded_program_id" FROM "recorded_videos" WHERE "status" = 'Missing');
        ALTER TABLE "recorded_videos" DROP COLUMN "missing_since";
    """
