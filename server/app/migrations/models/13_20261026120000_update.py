from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    # BinaryField に一意制約を宣言できないため、ハッシュの索引は SQL で明示する
    return """
        CREATE TABLE IF NOT EXISTS "captures" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "file_hash" BLOB NOT NULL,
            "file_size" BIGINT NOT NULL,
            "captured_at" TIMESTAMP NOT NULL,
            "broadcast_at" TIMESTAMP,
            "image_width" INT NOT NULL,
            "image_height" INT NOT NULL,
            "metadata_status" VARCHAR(16) NOT NULL,
            "playback_position" REAL,
            "caption_text" TEXT,
            "is_caption_composited" INT NOT NULL DEFAULT 0,
            "is_comment_composited" INT NOT NULL DEFAULT 0,
            "capture_program_id" INT REFERENCES "capture_programs" ("id") ON DELETE SET NULL,
            "detached_since" TIMESTAMP,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_captures_file_hash" ON "captures" ("file_hash");
        CREATE INDEX IF NOT EXISTS "captures_captured_at_id" ON "captures" ("captured_at", "id");
        CREATE INDEX IF NOT EXISTS "captures_broadcast_at_id" ON "captures" ("broadcast_at", "id");
        CREATE INDEX IF NOT EXISTS "captures_program_position" ON "captures" ("capture_program_id", "playback_position", "id");

        CREATE TABLE IF NOT EXISTS "capture_files" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "capture_id" INT REFERENCES "captures" ("id") ON DELETE CASCADE,
            "file_path" VARCHAR(4096) NOT NULL UNIQUE,
            "file_name" VARCHAR(1024) NOT NULL,
            "file_size" BIGINT NOT NULL,
            "file_created_at" TIMESTAMP NOT NULL,
            "file_modified_at" TIMESTAMP NOT NULL,
            "status" VARCHAR(16) NOT NULL,
            "missing_since" TIMESTAMP,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS "capture_files_capture_id" ON "capture_files" ("capture_id");
        CREATE INDEX IF NOT EXISTS "capture_files_status_missing_since" ON "capture_files" ("status", "missing_since");
        CREATE INDEX IF NOT EXISTS "capture_files_name_size_modified_at" ON "capture_files" ("file_name", "file_size", "file_modified_at");

        CREATE TABLE IF NOT EXISTS "capture_programs" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "network_id" INT NOT NULL,
            "service_id" INT NOT NULL,
            "event_id" INT NOT NULL,
            "start_time" TIMESTAMP NOT NULL,
            "end_time" TIMESTAMP,
            "duration" REAL,
            "title" TEXT NOT NULL,
            "description" TEXT NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "uid_capture_programs_program_key" UNIQUE ("network_id", "service_id", "event_id", "start_time")
        );
        CREATE INDEX IF NOT EXISTS "capture_programs_start_time_id" ON "capture_programs" ("start_time", "id");

        CREATE TABLE IF NOT EXISTS "capture_favorites" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "capture_id" INT NOT NULL REFERENCES "captures" ("id") ON DELETE CASCADE,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "uid_capture_favorites_user_id_capture_id" UNIQUE ("user_id", "capture_id")
        );
        CREATE INDEX IF NOT EXISTS "capture_favorites_capture_id" ON "capture_favorites" ("capture_id");

        CREATE TABLE IF NOT EXISTS "capture_tags" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "name" VARCHAR(255) NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "uid_capture_tags_user_id_name" UNIQUE ("user_id", "name")
        );
        CREATE TABLE IF NOT EXISTS "capture_tag_items" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "tag_id" INT NOT NULL REFERENCES "capture_tags" ("id") ON DELETE CASCADE,
            "capture_id" INT NOT NULL REFERENCES "captures" ("id") ON DELETE CASCADE,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT "uid_capture_tag_items_tag_id_capture_id" UNIQUE ("tag_id", "capture_id")
        );
        CREATE INDEX IF NOT EXISTS "capture_tag_items_capture_id" ON "capture_tag_items" ("capture_id");

        CREATE INDEX IF NOT EXISTS "recorded_programs_program_key" ON "recorded_programs" ("network_id", "service_id", "event_id", "start_time");
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "recorded_programs_program_key";
        DROP TABLE IF EXISTS "capture_tag_items";
        DROP TABLE IF EXISTS "capture_tags";
        DROP TABLE IF EXISTS "capture_favorites";
        DROP TABLE IF EXISTS "capture_programs";
        DROP TABLE IF EXISTS "capture_files";
        DROP TABLE IF EXISTS "captures";
    """
