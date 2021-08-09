-- upgrade --
CREATE TABLE IF NOT EXISTS "programs" (
    "id" TEXT NOT NULL  PRIMARY KEY,
    "channel_id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "detail" JSON NOT NULL,
    "start_time" TIMESTAMP NOT NULL,
    "end_time" TIMESTAMP NOT NULL,
    "duration" REAL NOT NULL,
    "is_free" INT NOT NULL,
    "genre" JSON NOT NULL,
    "video_type" TEXT NOT NULL,
    "video_codec" TEXT NOT NULL,
    "video_resolution" TEXT NOT NULL,
    "audio_type" TEXT NOT NULL,
    "audio_sampling_rate" TEXT NOT NULL
);
-- downgrade --
DROP TABLE IF EXISTS "programs";
