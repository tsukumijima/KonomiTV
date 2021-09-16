-- upgrade --
ALTER TABLE "programs" ADD "network_id" INT NOT NULL DEFAULT 0;
ALTER TABLE "programs" ADD "service_id" INT NOT NULL DEFAULT 0;
ALTER TABLE "programs" ADD "event_id" INT NOT NULL DEFAULT 0;
-- downgrade --
ALTER TABLE "programs" DROP COLUMN "network_id";
ALTER TABLE "programs" DROP COLUMN "service_id";
ALTER TABLE "programs" DROP COLUMN "event_id";
