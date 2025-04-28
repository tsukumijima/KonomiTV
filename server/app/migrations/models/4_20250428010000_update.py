
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Temporarily disable foreign key constraints (may be disabled by default in SQLite, but just in case)
        PRAGMA foreign_keys=off;

        -- Create a temporary table with the new schema (cm_sections allows NULL)
        CREATE TABLE "recorded_videos_new" (
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
            "cm_sections" JSON, -- Removed NOT NULL constraint
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Copy data from existing table to temporary table
        INSERT INTO "recorded_videos_new" (
            "id", "recorded_program_id", "status", "file_path", "file_hash", "file_size",
            "file_created_at", "file_modified_at", "recording_start_time", "recording_end_time",
            "duration", "container_format", "video_codec", "video_codec_profile", "video_scan_type",
            "video_frame_rate", "video_resolution_width", "video_resolution_height",
            "primary_audio_codec", "primary_audio_channel", "primary_audio_sampling_rate",
            "secondary_audio_codec", "secondary_audio_channel", "secondary_audio_sampling_rate",
            "key_frames", "cm_sections", "created_at", "updated_at"
        )
        SELECT
            "id", "recorded_program_id", "status", "file_path", "file_hash", "file_size",
            "file_created_at", "file_modified_at", "recording_start_time", "recording_end_time",
            "duration", "container_format", "video_codec", "video_codec_profile", "video_scan_type",
            "video_frame_rate", "video_resolution_width", "video_resolution_height",
            "primary_audio_codec", "primary_audio_channel", "primary_audio_sampling_rate",
            "secondary_audio_codec", "secondary_audio_channel", "secondary_audio_sampling_rate",
            "key_frames", "cm_sections", "created_at", "updated_at"
        FROM "recorded_videos";

        -- Drop existing table
        DROP TABLE "recorded_videos";

        -- Rename temporary table to original table name
        ALTER TABLE "recorded_videos_new" RENAME TO "recorded_videos";

        -- Recreate indexes (copy from original migration file)
        CREATE INDEX "recorded_videos_file_path" ON "recorded_videos" ("file_path");
        CREATE INDEX "recorded_videos_file_hash" ON "recorded_videos" ("file_hash");

        -- Re-enable foreign key constraints
        PRAGMA foreign_keys=on;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Temporarily disable foreign key constraints
        PRAGMA foreign_keys=off;

        -- Create temporary table with NOT NULL constraint
        CREATE TABLE "recorded_videos_old" (
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
            "cm_sections" JSON NOT NULL, -- Added NOT NULL constraint back
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Copy data
        -- For cm_sections, set default value ('[]') when NULL
        INSERT INTO "recorded_videos_old" (
            "id", "recorded_program_id", "status", "file_path", "file_hash", "file_size",
            "file_created_at", "file_modified_at", "recording_start_time", "recording_end_time",
            "duration", "container_format", "video_codec", "video_codec_profile", "video_scan_type",
            "video_frame_rate", "video_resolution_width", "video_resolution_height",
            "primary_audio_codec", "primary_audio_channel", "primary_audio_sampling_rate",
            "secondary_audio_codec", "secondary_audio_channel", "secondary_audio_sampling_rate",
            "key_frames", "cm_sections", "created_at", "updated_at"
        )
        SELECT
            "id", "recorded_program_id", "status", "file_path", "file_hash", "file_size",
            "file_created_at", "file_modified_at", "recording_start_time", "recording_end_time",
            "duration", "container_format", "video_codec", "video_codec_profile", "video_scan_type",
            "video_frame_rate", "video_resolution_width", "video_resolution_height",
            "primary_audio_codec", "primary_audio_channel", "primary_audio_sampling_rate",
            "secondary_audio_codec", "secondary_audio_channel", "secondary_audio_sampling_rate",
            "key_frames", COALESCE("cm_sections", '[]'), -- Set default value '[]' when NULL
            "created_at", "updated_at"
        FROM "recorded_videos";

        -- Drop existing table
        DROP TABLE "recorded_videos";

        -- Rename temporary table to original table name
        ALTER TABLE "recorded_videos_old" RENAME TO "recorded_videos";

        -- Recreate indexes
        CREATE INDEX "recorded_videos_file_path" ON "recorded_videos" ("file_path");
        CREATE INDEX "recorded_videos_file_hash" ON "recorded_videos" ("file_hash");

        -- Re-enable foreign key constraints
        PRAGMA foreign_keys=on;
    """
