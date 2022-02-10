-- upgrade --
ALTER TABLE "channels" ADD "is_radiochannel" INT NOT NULL DEFAULT 0;
-- downgrade --
ALTER TABLE "channels" DROP COLUMN "is_radiochannel";
