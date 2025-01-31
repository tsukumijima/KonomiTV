
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Drop existing tables
        DROP TABLE IF EXISTS "recorded_programs";
        DROP TABLE IF EXISTS "recorded_videos";
        DROP TABLE IF EXISTS "series";

        -- Recreate tables with new columns and indexes
        CREATE TABLE IF NOT EXISTS "recorded_programs" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "recording_start_margin" REAL NOT NULL,
            "recording_end_margin" REAL NOT NULL,
            "is_partially_recorded" INT NOT NULL,
            "channel_id" VARCHAR(255) REFERENCES "channels" ("id") ON DELETE CASCADE,
            "network_id" INT,
            "service_id" INT,
            "event_id" INT,
            "series_id" INT REFERENCES "series" ("id") ON DELETE CASCADE,
            "series_broadcast_period_id" INT REFERENCES "series_broadcast_periods" ("id") ON DELETE CASCADE,
            "title" TEXT NOT NULL,
            "series_title" TEXT,
            "episode_number" VARCHAR(255),
            "subtitle" TEXT,
            "description" TEXT NOT NULL,
            "detail" JSON NOT NULL,
            "start_time" TIMESTAMP NOT NULL,
            "end_time" TIMESTAMP NOT NULL,
            "duration" REAL NOT NULL,
            "is_free" INT NOT NULL,
            "genres" JSON NOT NULL,
            "primary_audio_type" TEXT NOT NULL,
            "primary_audio_language" TEXT NOT NULL,
            "secondary_audio_type" TEXT,
            "secondary_audio_language" TEXT,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS "recorded_videos" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "recorded_program_id" INT NOT NULL REFERENCES "recorded_programs" ("id") ON DELETE CASCADE,
            "status" VARCHAR(255) NOT NULL,
            "file_path" TEXT NOT NULL,
            "file_hash" TEXT NOT NULL,
            "file_size" INT NOT NULL,
            "file_created_at" TIMESTAMP NOT NULL,
            "file_modified_at" TIMESTAMP NOT NULL,
            "recording_start_time" TIMESTAMP,
            "recording_end_time" TIMESTAMP,
            "duration" REAL NOT NULL,
            "container_format" VARCHAR(255) NOT NULL,
            "video_codec" VARCHAR(255) NOT NULL,
            "video_codec_profile" VARCHAR(255) NOT NULL,
            "video_scan_type" VARCHAR(255) NOT NULL,
            "video_frame_rate" REAL NOT NULL,
            "video_resolution_width" INT NOT NULL,
            "video_resolution_height" INT NOT NULL,
            "primary_audio_codec" VARCHAR(255) NOT NULL,
            "primary_audio_channel" VARCHAR(255) NOT NULL,
            "primary_audio_sampling_rate" INT NOT NULL,
            "secondary_audio_codec" VARCHAR(255),
            "secondary_audio_channel" VARCHAR(255),
            "secondary_audio_sampling_rate" INT,
            "key_frames" JSON NOT NULL,
            "cm_sections" JSON NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS "series" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "title" TEXT NOT NULL,
            "description" TEXT NOT NULL,
            "genres" JSON NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Create indexes for better query performance
        CREATE INDEX "recorded_programs_time_range" ON "recorded_programs" ("start_time", "end_time");
        CREATE INDEX "recorded_programs_channel_time" ON "recorded_programs" ("channel_id", "start_time");
        CREATE INDEX "recorded_videos_file_path" ON "recorded_videos" ("file_path");
        CREATE INDEX "recorded_videos_file_hash" ON "recorded_videos" ("file_hash");
        CREATE INDEX "series_title" ON "series" ("title");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "recorded_programs";
        DROP TABLE IF EXISTS "recorded_videos";
        DROP TABLE IF EXISTS "series";
        DROP INDEX IF EXISTS "recorded_programs_time_range";
        DROP INDEX IF EXISTS "recorded_programs_channel_time";
        DROP INDEX IF EXISTS "recorded_videos_file_path";
        DROP INDEX IF EXISTS "recorded_videos_file_hash";
        DROP INDEX IF EXISTS "series_title";
    """
