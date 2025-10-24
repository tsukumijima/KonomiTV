from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "clip_videos" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "title" TEXT NOT NULL,
    "file_path" TEXT NOT NULL,
    "file_hash" TEXT NOT NULL,
    "file_size" INT NOT NULL,
    "start_time" REAL NOT NULL,
    "end_time" REAL NOT NULL,
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
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recorded_video_id" INT NOT NULL REFERENCES "recorded_videos" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "clip_videos";"""
