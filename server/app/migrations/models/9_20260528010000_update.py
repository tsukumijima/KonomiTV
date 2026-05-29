from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "twitter_accounts" ADD COLUMN "cookie_browser_info" JSON;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "twitter_accounts" DROP COLUMN "cookie_browser_info";
    """
