-- upgrade --
ALTER TABLE "channels" ADD "channel_comment" INT;
-- downgrade --
ALTER TABLE "channels" DROP COLUMN "channel_comment";
