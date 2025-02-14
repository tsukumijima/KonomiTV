
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE INDEX "recorded_programs_start_time_id" ON "recorded_programs" ("start_time" DESC, "id" DESC);
        CREATE INDEX "recorded_programs_title" ON "recorded_programs" ("title");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "recorded_programs_start_time_id";
        DROP INDEX IF EXISTS "recorded_programs_title";
    """
