-- upgrade --
CREATE TABLE IF NOT EXISTS "twitter_accounts" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "user_id" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "screen_name" TEXT NOT NULL,
    "icon_url" TEXT NOT NULL,
    "access_token" TEXT NOT NULL,
    "access_token_secret" TEXT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("user_id") REFERENCES users("id")
);
-- downgrade --
DROP TABLE IF EXISTS "twitter_accounts";
