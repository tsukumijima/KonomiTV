-- upgrade --
CREATE INDEX "programs_time_index" ON "programs" (
	"channel_id",
	"start_time",
	"end_time"
);
-- downgrade --
DROP INDEX IF EXISTS "programs_time_index";
