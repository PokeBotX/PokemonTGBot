CREATE TABLE IF NOT EXISTS "users" (
  "id" bigserial PRIMARY KEY,
  "tg_user_id" bigint UNIQUE NOT NULL,
  "tg_username" varchar(64),
  "nickname" varchar(64),
  "vip_level" int NOT NULL DEFAULT 0,
  "created_at" timestamptz NOT NULL DEFAULT (now()),
  "start_guide_seen_at" timestamptz
);

ALTER TABLE "users"
  ADD COLUMN IF NOT EXISTS "tg_username" varchar(64),
  ADD COLUMN IF NOT EXISTS "start_guide_seen_at" timestamptz;

CREATE TABLE IF NOT EXISTS "user_settings" (
  "user_id" bigint PRIMARY KEY,
  "language" varchar(8) NOT NULL DEFAULT 'ru',
  "profile_pic_credit_id" bigint,
  "updated_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS "currencies" (
  "id" smallserial PRIMARY KEY,
  "code" varchar(16) UNIQUE NOT NULL,
  "name" varchar(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS "user_balances" (
  "user_id" bigint NOT NULL,
  "currency_id" smallint NOT NULL,
  "amount" bigint NOT NULL DEFAULT 0,
  PRIMARY KEY ("user_id", "currency_id")
);

CREATE TABLE IF NOT EXISTS "items" (
  "id" smallserial PRIMARY KEY,
  "code" varchar(32) UNIQUE NOT NULL,
  "name" varchar(64) NOT NULL,
  "item_type" varchar(32) NOT NULL,
  "image_credit_id" bigint
);

CREATE TABLE IF NOT EXISTS "user_items" (
  "user_id" bigint NOT NULL,
  "item_id" smallint NOT NULL,
  "quantity" int NOT NULL DEFAULT 0,
  PRIMARY KEY ("user_id", "item_id")
);

CREATE TABLE IF NOT EXISTS "user_shop_state" (
  "user_id" bigint PRIMARY KEY,
  "bonus_last_claim_at" timestamptz NOT NULL DEFAULT (NOW() - INTERVAL '6 hours'),
  "epic_pity_counter" int NOT NULL DEFAULT 0,
  "legendary_pity_counter" int NOT NULL DEFAULT 0,
  "updated_at" timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "chat_encounter_state" (
  "chat_id" bigint PRIMARY KEY,
  "last_spawn_at" timestamptz NOT NULL DEFAULT TO_TIMESTAMP(0),
  "messages_since_cooldown" int NOT NULL DEFAULT 0,
  "active_encounter_id" bigint UNIQUE,
  "updated_at" timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "image_credits" (
  "id" bigserial PRIMARY KEY,
  "storage_bucket" varchar(128) NOT NULL,
  "object_key" text NOT NULL,
  "content_type" varchar(64),
  "etag" varchar(128),
  "source" text,
  "author" text,
  "created_at" timestamptz NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS "pokemon_catalog" (
  "id" int PRIMARY KEY,
  "name" varchar(64) NOT NULL,
  "dex_form_code" varchar(16),
  "type" varchar(32),
  "rarity" varchar(32),
  "base_hp" int NOT NULL DEFAULT 0,
  "base_attack" int NOT NULL DEFAULT 0,
  "base_defense" int NOT NULL DEFAULT 0,
  "base_stamina" int NOT NULL DEFAULT 0,
  "image_credit_id" bigint
);

ALTER TABLE "pokemon_catalog"
  ADD COLUMN IF NOT EXISTS "dex_form_code" varchar(16);

UPDATE "pokemon_catalog"
SET "dex_form_code" = "id"::text
WHERE "dex_form_code" IS NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pokemon_catalog_name_key'
  ) THEN
    ALTER TABLE "pokemon_catalog"
      DROP CONSTRAINT "pokemon_catalog_name_key";
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "pokemon_image_variants" (
  "pokemon_id" int NOT NULL,
  "image_credit_id" bigint NOT NULL,
  "display_order" int NOT NULL DEFAULT 1,
  "is_default" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY ("pokemon_id", "image_credit_id")
);

CREATE TABLE IF NOT EXISTS "user_pokemon_image_preferences" (
  "user_id" bigint NOT NULL,
  "pokemon_id" int NOT NULL,
  "image_credit_id" bigint NOT NULL,
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY ("user_id", "pokemon_id")
);

CREATE TABLE IF NOT EXISTS "admin_action_audit" (
  "id" bigserial PRIMARY KEY,
  "actor_user_id" bigint,
  "actor_telegram_id" bigint NOT NULL,
  "actor_username" varchar(64),
  "action_type" varchar(64) NOT NULL,
  "target_user_id" bigint,
  "target_telegram_id" bigint,
  "target_username" varchar(64),
  "status" varchar(16) NOT NULL,
  "input_payload" jsonb,
  "result_payload" jsonb,
  "error_message" text,
  "created_at" timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "user_pokemon" (
  "id" bigserial PRIMARY KEY,
  "owner_user_id" bigint NOT NULL,
  "pokemon_id" int NOT NULL,
  "obtained_at" timestamptz NOT NULL DEFAULT (now()),
  "is_locked" boolean NOT NULL DEFAULT false,
  "released_at" timestamptz
);

ALTER TABLE "user_pokemon"
  ADD COLUMN IF NOT EXISTS "released_at" timestamptz;

CREATE TABLE IF NOT EXISTS "user_pvp_team_slots" (
  "user_id" bigint NOT NULL,
  "slot_index" smallint NOT NULL,
  "user_pokemon_id" bigint NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY ("user_id", "slot_index"),
  UNIQUE ("user_id", "user_pokemon_id"),
  CHECK ("slot_index" BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS "user_pvp_daily_rewards" (
  "user_id" bigint NOT NULL,
  "reward_date" date NOT NULL,
  "rewarded_battle_count" int NOT NULL DEFAULT 0,
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY ("user_id", "reward_date")
);

CREATE TABLE IF NOT EXISTS "pvp_challenges" (
  "id" bigserial PRIMARY KEY,
  "chat_id" bigint NOT NULL,
  "message_thread_id" bigint,
  "message_id" bigint,
  "initiator_user_id" bigint NOT NULL,
  "target_user_id" bigint NOT NULL,
  "status" varchar(24) NOT NULL DEFAULT 'pending',
  "pending_expires_at" timestamptz NOT NULL,
  "selection_expires_at" timestamptz,
  "initiator_selected_user_pokemon_id" bigint,
  "target_selected_user_pokemon_id" bigint,
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "accepted_at" timestamptz,
  "canceled_at" timestamptz,
  "completed_at" timestamptz,
  "cancel_reason" varchar(32)
);

CREATE TABLE IF NOT EXISTS "market_listings" (
  "id" bigserial PRIMARY KEY,
  "seller_user_id" bigint NOT NULL,
  "pokemon_instance_id" bigint NOT NULL,
  "currency_id" smallint NOT NULL,
  "price" bigint NOT NULL,
  "status" varchar(16) NOT NULL DEFAULT 'active'
);

ALTER TABLE "market_listings"
  ADD COLUMN IF NOT EXISTS "listed_at" timestamptz NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS "completed_at" timestamptz,
  ADD COLUMN IF NOT EXISTS "removed_at" timestamptz,
  ADD COLUMN IF NOT EXISTS "removal_reason" varchar(32),
  ADD COLUMN IF NOT EXISTS "initial_commission_paid" bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS "daily_commission_amount" bigint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS "next_commission_at" timestamptz,
  ADD COLUMN IF NOT EXISTS "expires_at" timestamptz,
  ADD COLUMN IF NOT EXISTS "last_commission_at" timestamptz;

CREATE TABLE IF NOT EXISTS "market_buy_requests" (
  "id" bigserial PRIMARY KEY,
  "requester_user_id" bigint NOT NULL,
  "pokemon_id" int NOT NULL,
  "currency_id" smallint NOT NULL,
  "price" bigint NOT NULL,
  "reserved_amount" bigint NOT NULL DEFAULT 0,
  "status" varchar(16) NOT NULL DEFAULT 'active',
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  "fulfilled_at" timestamptz,
  "canceled_at" timestamptz,
  "fulfilled_by_user_id" bigint,
  "fulfilled_user_pokemon_id" bigint,
  "cancel_reason" varchar(32)
);

CREATE TABLE IF NOT EXISTS "trade_sessions" (
  "id" bigserial PRIMARY KEY,
  "chat_id" bigint NOT NULL,
  "message_thread_id" bigint,
  "request_message_id" bigint,
  "active_message_id" bigint,
  "initiator_user_id" bigint NOT NULL,
  "target_user_id" bigint NOT NULL,
  "status" varchar(16) NOT NULL DEFAULT 'pending',
  "pending_expires_at" timestamptz NOT NULL,
  "trade_expires_at" timestamptz,
  "initiator_ready" boolean NOT NULL DEFAULT false,
  "target_ready" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "updated_at" timestamptz NOT NULL DEFAULT NOW(),
  "accepted_at" timestamptz,
  "canceled_at" timestamptz,
  "completed_at" timestamptz,
  "cancel_reason" varchar(32)
);

CREATE TABLE IF NOT EXISTS "trade_user_links" (
  "user_id" bigint PRIMARY KEY,
  "trade_id" bigint NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "trade_offer_items" (
  "trade_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "user_pokemon_id" bigint NOT NULL UNIQUE,
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY ("trade_id", "user_pokemon_id")
);

CREATE TABLE IF NOT EXISTS "chat_encounters" (
  "id" bigserial PRIMARY KEY,
  "chat_id" bigint NOT NULL,
  "message_thread_id" bigint,
  "encounter_message_id" bigint,
  "pokemon_id" int NOT NULL,
  "status" varchar(16) NOT NULL DEFAULT 'active',
  "spawned_at" timestamptz NOT NULL DEFAULT NOW(),
  "expires_at" timestamptz NOT NULL,
  "resolved_at" timestamptz,
  "caught_by_user_id" bigint,
  "caught_user_pokemon_id" bigint,
  "caught_with_item_code" varchar(32)
);

ALTER TABLE "chat_encounters"
  ADD COLUMN IF NOT EXISTS "caught_user_pokemon_id" bigint;

CREATE TABLE IF NOT EXISTS "chat_encounter_attempts" (
  "encounter_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "ball_code" varchar(32) NOT NULL,
  "success" boolean NOT NULL DEFAULT false,
  "attempted_at" timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY ("encounter_id", "user_id")
);

CREATE UNIQUE INDEX IF NOT EXISTS image_credits_storage_bucket_object_key_idx
  ON "image_credits" ("storage_bucket", "object_key");

CREATE INDEX IF NOT EXISTS chat_encounters_chat_id_status_idx
  ON "chat_encounters" ("chat_id", "status");

CREATE INDEX IF NOT EXISTS chat_encounters_expires_at_status_idx
  ON "chat_encounters" ("expires_at", "status");

CREATE INDEX IF NOT EXISTS user_pokemon_owner_user_id_pokemon_id_idx
  ON "user_pokemon" ("owner_user_id", "pokemon_id");

CREATE UNIQUE INDEX IF NOT EXISTS pokemon_catalog_dex_form_code_idx
  ON "pokemon_catalog" ("dex_form_code")
  WHERE "dex_form_code" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS pokemon_image_variants_default_idx
  ON "pokemon_image_variants" ("pokemon_id")
  WHERE is_default = true;

CREATE UNIQUE INDEX IF NOT EXISTS pokemon_image_variants_order_idx
  ON "pokemon_image_variants" ("pokemon_id", "display_order");

CREATE INDEX IF NOT EXISTS user_pokemon_image_preferences_user_pokemon_idx
  ON "user_pokemon_image_preferences" ("user_id", "pokemon_id", "updated_at" DESC);

CREATE INDEX IF NOT EXISTS admin_action_audit_actor_created_idx
  ON "admin_action_audit" ("actor_telegram_id", "created_at" DESC);

CREATE INDEX IF NOT EXISTS admin_action_audit_action_status_idx
  ON "admin_action_audit" ("action_type", "status", "created_at" DESC);

CREATE INDEX IF NOT EXISTS market_listings_active_browse_idx
  ON "market_listings" ("status", "listed_at" DESC, "price" ASC);

CREATE INDEX IF NOT EXISTS market_listings_seller_status_idx
  ON "market_listings" ("seller_user_id", "status");

CREATE INDEX IF NOT EXISTS market_listings_next_commission_idx
  ON "market_listings" ("status", "next_commission_at");

CREATE INDEX IF NOT EXISTS market_listings_expires_at_idx
  ON "market_listings" ("status", "expires_at");

CREATE UNIQUE INDEX IF NOT EXISTS market_listings_active_instance_idx
  ON "market_listings" ("pokemon_instance_id")
  WHERE status = 'active';

CREATE INDEX IF NOT EXISTS market_buy_requests_requester_status_idx
  ON "market_buy_requests" ("requester_user_id", "status");

CREATE INDEX IF NOT EXISTS market_buy_requests_active_browse_idx
  ON "market_buy_requests" ("status", "created_at" DESC, "price" DESC);

CREATE INDEX IF NOT EXISTS market_buy_requests_pokemon_status_idx
  ON "market_buy_requests" ("pokemon_id", "status");

CREATE UNIQUE INDEX IF NOT EXISTS market_buy_requests_active_requester_pokemon_idx
  ON "market_buy_requests" ("requester_user_id", "pokemon_id")
  WHERE status = 'active';

CREATE INDEX IF NOT EXISTS trade_sessions_status_pending_expires_idx
  ON "trade_sessions" ("status", "pending_expires_at");

CREATE INDEX IF NOT EXISTS trade_sessions_status_trade_expires_idx
  ON "trade_sessions" ("status", "trade_expires_at");

CREATE INDEX IF NOT EXISTS trade_sessions_chat_id_status_idx
  ON "trade_sessions" ("chat_id", "status", "created_at" DESC);

CREATE INDEX IF NOT EXISTS trade_offer_items_trade_id_user_id_idx
  ON "trade_offer_items" ("trade_id", "user_id", "created_at");

CREATE INDEX IF NOT EXISTS users_lower_tg_username_idx
  ON "users" (lower("tg_username"));

COMMENT ON TABLE "user_settings" IS 'Настройки пользователя и аватар';

COMMENT ON TABLE "pokemon_catalog" IS 'Каталог покемонов (справочник). Статические данные покемонов.';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'users_vip_level_non_negative'
  ) THEN
    ALTER TABLE "users"
      ADD CONSTRAINT "users_vip_level_non_negative"
      CHECK ("vip_level" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_balances_amount_non_negative'
  ) THEN
    ALTER TABLE "user_balances"
      ADD CONSTRAINT "user_balances_amount_non_negative"
      CHECK ("amount" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_items_quantity_non_negative'
  ) THEN
    ALTER TABLE "user_items"
      ADD CONSTRAINT "user_items_quantity_non_negative"
      CHECK ("quantity" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_shop_state_epic_pity_counter_non_negative'
  ) THEN
    ALTER TABLE "user_shop_state"
      ADD CONSTRAINT "user_shop_state_epic_pity_counter_non_negative"
      CHECK ("epic_pity_counter" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_shop_state_legendary_pity_counter_non_negative'
  ) THEN
    ALTER TABLE "user_shop_state"
      ADD CONSTRAINT "user_shop_state_legendary_pity_counter_non_negative"
      CHECK ("legendary_pity_counter" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chat_encounter_state_messages_since_cooldown_non_negative'
  ) THEN
    ALTER TABLE "chat_encounter_state"
      ADD CONSTRAINT "chat_encounter_state_messages_since_cooldown_non_negative"
      CHECK ("messages_since_cooldown" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'pokemon_catalog_base_hp_non_negative'
  ) THEN
    ALTER TABLE "pokemon_catalog"
      ADD CONSTRAINT "pokemon_catalog_base_hp_non_negative"
      CHECK ("base_hp" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'pokemon_catalog_base_attack_non_negative'
  ) THEN
    ALTER TABLE "pokemon_catalog"
      ADD CONSTRAINT "pokemon_catalog_base_attack_non_negative"
      CHECK ("base_attack" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'pokemon_catalog_base_defense_non_negative'
  ) THEN
    ALTER TABLE "pokemon_catalog"
      ADD CONSTRAINT "pokemon_catalog_base_defense_non_negative"
      CHECK ("base_defense" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'pokemon_catalog_base_stamina_non_negative'
  ) THEN
    ALTER TABLE "pokemon_catalog"
      ADD CONSTRAINT "pokemon_catalog_base_stamina_non_negative"
      CHECK ("base_stamina" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'market_listings_price_positive'
  ) THEN
    ALTER TABLE "market_listings"
      ADD CONSTRAINT "market_listings_price_positive"
      CHECK ("price" > 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'market_listings_initial_commission_paid_non_negative'
  ) THEN
    ALTER TABLE "market_listings"
      ADD CONSTRAINT "market_listings_initial_commission_paid_non_negative"
      CHECK ("initial_commission_paid" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'market_listings_daily_commission_amount_non_negative'
  ) THEN
    ALTER TABLE "market_listings"
      ADD CONSTRAINT "market_listings_daily_commission_amount_non_negative"
      CHECK ("daily_commission_amount" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'market_buy_requests_price_positive'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD CONSTRAINT "market_buy_requests_price_positive"
      CHECK ("price" > 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'market_buy_requests_reserved_amount_non_negative'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD CONSTRAINT "market_buy_requests_reserved_amount_non_negative"
      CHECK ("reserved_amount" >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trade_sessions_status_valid'
  ) THEN
    ALTER TABLE "trade_sessions"
      ADD CONSTRAINT "trade_sessions_status_valid"
      CHECK ("status" IN ('pending', 'active', 'rejected', 'canceled', 'expired', 'completed'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trade_sessions_not_self_trade'
  ) THEN
    ALTER TABLE "trade_sessions"
      ADD CONSTRAINT "trade_sessions_not_self_trade"
      CHECK ("initiator_user_id" <> "target_user_id");
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'trade_offer_items_user_unique_per_trade'
  ) THEN
    ALTER TABLE "trade_offer_items"
      ADD CONSTRAINT "trade_offer_items_user_unique_per_trade"
      UNIQUE ("trade_id", "user_id", "user_pokemon_id");
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_listings_pokemon_instance_id_key'
  ) THEN
    ALTER TABLE "market_listings"
      DROP CONSTRAINT "market_listings_pokemon_instance_id_key";
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'market_listings' AND column_name = 'start_date'
  ) THEN
    ALTER TABLE "market_listings" DROP COLUMN "start_date";
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'market_listings' AND column_name = 'end_date'
  ) THEN
    ALTER TABLE "market_listings" DROP COLUMN "end_date";
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'market_listings' AND column_name = 'purchaser_user_id'
  ) THEN
    ALTER TABLE "market_listings" DROP COLUMN "purchaser_user_id";
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'users'
      AND column_name = 'created_at'
      AND data_type = 'timestamp without time zone'
  ) THEN
    ALTER TABLE "users"
      ALTER COLUMN "created_at" TYPE timestamptz
      USING "created_at" AT TIME ZONE 'UTC';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'user_settings'
      AND column_name = 'updated_at'
      AND data_type = 'timestamp without time zone'
  ) THEN
    ALTER TABLE "user_settings"
      ALTER COLUMN "updated_at" TYPE timestamptz
      USING "updated_at" AT TIME ZONE 'UTC';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'image_credits'
      AND column_name = 'created_at'
      AND data_type = 'timestamp without time zone'
  ) THEN
    ALTER TABLE "image_credits"
      ALTER COLUMN "created_at" TYPE timestamptz
      USING "created_at" AT TIME ZONE 'UTC';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'user_pokemon'
      AND column_name = 'obtained_at'
      AND data_type = 'timestamp without time zone'
  ) THEN
    ALTER TABLE "user_pokemon"
      ALTER COLUMN "obtained_at" TYPE timestamptz
      USING "obtained_at" AT TIME ZONE 'UTC';
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_settings_user_id_fkey'
  ) THEN
    ALTER TABLE "user_settings"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_sessions_initiator_user_id_fkey'
  ) THEN
    ALTER TABLE "trade_sessions"
      ADD FOREIGN KEY ("initiator_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_sessions_target_user_id_fkey'
  ) THEN
    ALTER TABLE "trade_sessions"
      ADD FOREIGN KEY ("target_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_user_links_user_id_fkey'
  ) THEN
    ALTER TABLE "trade_user_links"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_user_links_trade_id_fkey'
  ) THEN
    ALTER TABLE "trade_user_links"
      ADD FOREIGN KEY ("trade_id")
      REFERENCES "trade_sessions" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_offer_items_trade_id_fkey'
  ) THEN
    ALTER TABLE "trade_offer_items"
      ADD FOREIGN KEY ("trade_id")
      REFERENCES "trade_sessions" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_offer_items_user_id_fkey'
  ) THEN
    ALTER TABLE "trade_offer_items"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'trade_offer_items_user_pokemon_id_fkey'
  ) THEN
    ALTER TABLE "trade_offer_items"
      ADD FOREIGN KEY ("user_pokemon_id")
      REFERENCES "user_pokemon" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_buy_requests_requester_user_id_fkey'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD FOREIGN KEY ("requester_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_buy_requests_pokemon_id_fkey'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD FOREIGN KEY ("pokemon_id")
      REFERENCES "pokemon_catalog" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_buy_requests_currency_id_fkey'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD FOREIGN KEY ("currency_id")
      REFERENCES "currencies" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_buy_requests_fulfilled_by_user_id_fkey'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD FOREIGN KEY ("fulfilled_by_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_buy_requests_fulfilled_user_pokemon_id_fkey'
  ) THEN
    ALTER TABLE "market_buy_requests"
      ADD FOREIGN KEY ("fulfilled_user_pokemon_id")
      REFERENCES "user_pokemon" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chat_encounters_caught_user_pokemon_id_fkey'
  ) THEN
    ALTER TABLE "chat_encounters"
      ADD FOREIGN KEY ("caught_user_pokemon_id")
      REFERENCES "user_pokemon" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chat_encounter_state_active_encounter_id_fkey'
  ) THEN
    ALTER TABLE "chat_encounter_state"
      ADD FOREIGN KEY ("active_encounter_id")
      REFERENCES "chat_encounters" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_shop_state_user_id_fkey'
  ) THEN
    ALTER TABLE "user_shop_state"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chat_encounters_pokemon_id_fkey'
  ) THEN
    ALTER TABLE "chat_encounters"
      ADD FOREIGN KEY ("pokemon_id")
      REFERENCES "pokemon_catalog" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chat_encounters_caught_by_user_id_fkey'
  ) THEN
    ALTER TABLE "chat_encounters"
      ADD FOREIGN KEY ("caught_by_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chat_encounter_attempts_encounter_id_fkey'
  ) THEN
    ALTER TABLE "chat_encounter_attempts"
      ADD FOREIGN KEY ("encounter_id")
      REFERENCES "chat_encounters" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chat_encounter_attempts_user_id_fkey'
  ) THEN
    ALTER TABLE "chat_encounter_attempts"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_settings_profile_pic_credit_id_fkey'
  ) THEN
    ALTER TABLE "user_settings"
      ADD FOREIGN KEY ("profile_pic_credit_id")
      REFERENCES "image_credits" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_balances_user_id_fkey'
  ) THEN
    ALTER TABLE "user_balances"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_balances_currency_id_fkey'
  ) THEN
    ALTER TABLE "user_balances"
      ADD FOREIGN KEY ("currency_id")
      REFERENCES "currencies" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'items_image_credit_id_fkey'
  ) THEN
    ALTER TABLE "items"
      ADD FOREIGN KEY ("image_credit_id")
      REFERENCES "image_credits" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_items_user_id_fkey'
  ) THEN
    ALTER TABLE "user_items"
      ADD FOREIGN KEY ("user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_items_item_id_fkey'
  ) THEN
    ALTER TABLE "user_items"
      ADD FOREIGN KEY ("item_id")
      REFERENCES "items" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pokemon_catalog_image_credit_id_fkey'
  ) THEN
    ALTER TABLE "pokemon_catalog"
      ADD FOREIGN KEY ("image_credit_id")
      REFERENCES "image_credits" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_pokemon_owner_user_id_fkey'
  ) THEN
    ALTER TABLE "user_pokemon"
      ADD FOREIGN KEY ("owner_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_pokemon_pokemon_id_fkey'
  ) THEN
    ALTER TABLE "user_pokemon"
      ADD FOREIGN KEY ("pokemon_id")
      REFERENCES "pokemon_catalog" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_listings_seller_user_id_fkey'
  ) THEN
    ALTER TABLE "market_listings"
      ADD FOREIGN KEY ("seller_user_id")
      REFERENCES "users" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_listings_pokemon_instance_id_fkey'
  ) THEN
    ALTER TABLE "market_listings"
      ADD FOREIGN KEY ("pokemon_instance_id")
      REFERENCES "user_pokemon" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_listings_currency_id_fkey'
  ) THEN
    ALTER TABLE "market_listings"
      ADD FOREIGN KEY ("currency_id")
      REFERENCES "currencies" ("id")
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

INSERT INTO currencies (code, name)
VALUES
  ('pokedollar', 'PokéDollar'),
  ('pokecoin', 'PokéCoin')
ON CONFLICT (code) DO NOTHING;

INSERT INTO items (code, name, item_type)
VALUES
  ('ultraball', 'Ultraball', 'ball'),
  ('masterball', 'Masterball', 'ball')
ON CONFLICT (code) DO NOTHING;
