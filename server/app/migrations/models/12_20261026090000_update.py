from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    # 既存の録画レコードのサムネイル情報の revision を 1 に設定
    return """
        UPDATE "recorded_videos" SET "thumbnail_info" = json_set("thumbnail_info", '$.representative.revision', 1)
        WHERE "thumbnail_info" IS NOT NULL AND json_type("thumbnail_info", '$.representative.revision') IS NULL;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "recorded_videos" SET "thumbnail_info" = json_remove("thumbnail_info", '$.representative.revision')
        WHERE "thumbnail_info" IS NOT NULL;
    """
