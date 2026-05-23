
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "bluesky_accounts" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "did" TEXT NOT NULL,
            "handle" TEXT NOT NULL,
            "name" TEXT NOT NULL,
            "icon_url" TEXT NOT NULL,
            "session_string" TEXT NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "uid_bluesky_ac_user_id_did" UNIQUE ("user_id", "did")
        );
        CREATE TABLE IF NOT EXISTS "account_links" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "twitter_account_id" INT NOT NULL UNIQUE REFERENCES "twitter_accounts" ("id") ON DELETE CASCADE,
            "bluesky_account_id" INT NOT NULL UNIQUE REFERENCES "bluesky_accounts" ("id") ON DELETE CASCADE,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "account_links";
        DROP TABLE IF EXISTS "bluesky_accounts";
    """
