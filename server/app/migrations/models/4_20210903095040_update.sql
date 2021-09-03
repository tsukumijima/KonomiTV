-- upgrade --
ALTER TABLE "channels" ADD "transport_stream_id" INT;
-- downgrade --
ALTER TABLE "channels" DROP COLUMN "transport_stream_id";
