-- upgrade --
ALTER TABLE "programs" RENAME COLUMN "audio_type" TO "primary_audio_type";
ALTER TABLE "programs" ADD "primary_audio_language" TEXT NOT NULL DEFAULT "";
ALTER TABLE "programs" RENAME COLUMN "audio_sampling_rate" TO "primary_audio_sampling_rate";
ALTER TABLE "programs" ADD "secondary_audio_type" TEXT;
ALTER TABLE "programs" ADD "secondary_audio_language" TEXT;
ALTER TABLE "programs" ADD "secondary_audio_sampling_rate" TEXT;
-- downgrade --
ALTER TABLE "programs" RENAME COLUMN "primary_audio_type" TO "audio_type";
ALTER TABLE "programs" DROP COLUMN "primary_audio_language";
ALTER TABLE "programs" RENAME COLUMN "primary_audio_sampling_rate" TO "audio_sampling_rate";
ALTER TABLE "programs" DROP COLUMN "secondary_audio_type";
ALTER TABLE "programs" DROP COLUMN "secondary_audio_language";
ALTER TABLE "programs" DROP COLUMN "secondary_audio_sampling_rate";
