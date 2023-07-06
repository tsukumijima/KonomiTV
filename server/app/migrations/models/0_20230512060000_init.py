
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "channels";
        CREATE TABLE "channels" (
            "id" VARCHAR(255) NOT NULL PRIMARY KEY,
            "display_channel_id" VARCHAR(255) NOT NULL UNIQUE,
            "network_id" INT NOT NULL,
            "service_id" INT NOT NULL,
            "transport_stream_id" INT,
            "remocon_id" INT NOT NULL,
            "channel_number" VARCHAR(255) NOT NULL,
            "type" VARCHAR(255) NOT NULL,
            "name" TEXT NOT NULL,
            "jikkyo_force" INT,
            "is_subchannel" INT NOT NULL,
            "is_radiochannel" INT NOT NULL,
            "is_watchable" INT NOT NULL
        );
        DROP TABLE IF EXISTS "programs";
        CREATE TABLE "programs" (
            "id" VARCHAR(255) NOT NULL PRIMARY KEY,
            "channel_id" VARCHAR(255) NOT NULL REFERENCES "channels" ("id") ON DELETE CASCADE,
            "network_id" INT NOT NULL,
            "service_id" INT NOT NULL,
            "event_id" INT NOT NULL,
            "title" TEXT NOT NULL,
            "description" TEXT NOT NULL,
            "detail" JSON NOT NULL,
            "start_time" TIMESTAMP NOT NULL,
            "end_time" TIMESTAMP NOT NULL,
            "duration" REAL NOT NULL,
            "is_free" INT NOT NULL,
            "genres" JSON NOT NULL,
            "video_type" TEXT,
            "video_codec" TEXT,
            "video_resolution" TEXT,
            "primary_audio_type" TEXT NOT NULL,
            "primary_audio_language" TEXT NOT NULL,
            "primary_audio_sampling_rate" TEXT NOT NULL,
            "secondary_audio_type" TEXT,
            "secondary_audio_language" TEXT,
            "secondary_audio_sampling_rate" TEXT
        );
        DROP INDEX IF EXISTS "programs_time_index";
        CREATE INDEX "programs_time_index" ON "programs" (
            "channel_id",
            "start_time",
            "end_time"
        );
        CREATE TABLE IF NOT EXISTS "users" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "name" TEXT NOT NULL,
            "password" TEXT NOT NULL,
            "is_admin" INT NOT NULL,
            "client_settings" JSON NOT NULL,
            "niconico_user_id" INT,
            "niconico_user_name" TEXT,
            "niconico_user_premium" INT,
            "niconico_access_token" TEXT,
            "niconico_refresh_token" TEXT,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS "twitter_accounts" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "name" TEXT NOT NULL,
            "screen_name" TEXT NOT NULL,
            "icon_url" TEXT NOT NULL,
            "access_token" TEXT NOT NULL,
            "access_token_secret" TEXT NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        DROP TABLE IF EXISTS "aerich";
        CREATE TABLE IF NOT EXISTS "aerich" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "version" VARCHAR(255) NOT NULL,
            "app" VARCHAR(100) NOT NULL,
            "content" JSON NOT NULL
        );
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "channels";
        DROP TABLE IF EXISTS "programs";
        DROP INDEX IF EXISTS "programs_time_index";
        DROP TABLE IF EXISTS "users";
        DROP TABLE IF EXISTS "twitter_accounts";
        DROP TABLE IF EXISTS "aerich";
    """
