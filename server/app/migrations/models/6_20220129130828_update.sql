-- upgrade --
ALTER TABLE "channels" ADD "is_radiochannel" INT NOT NULL;
-- downgrade --
ALTER TABLE "channels" DROP COLUMN "is_radiochannel";
