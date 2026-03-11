CREATE TABLE IF NOT EXISTS "users" (
  "id" bigserial PRIMARY KEY,
  "tg_user_id" bigint UNIQUE NOT NULL,
  "nickname" varchar(64),
  "vip_level" int NOT NULL DEFAULT 0,
  "created_at" timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS "user_settings" (
  "user_id" bigint PRIMARY KEY,
  "language" varchar(8) NOT NULL DEFAULT 'ru',
  "profile_pic_credit_id" bigint,
  "updated_at" timestamp NOT NULL DEFAULT (now())
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
  "bonus_last_claim_at" timestamptz NOT NULL DEFAULT NOW(),
  "epic_pity_counter" int NOT NULL DEFAULT 0,
  "legendary_pity_counter" int NOT NULL DEFAULT 0,
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
  "created_at" timestamp NOT NULL DEFAULT (now())
);

CREATE TABLE IF NOT EXISTS "pokemon_catalog" (
  "id" int PRIMARY KEY,
  "name" varchar(64) UNIQUE NOT NULL,
  "type" varchar(32),
  "rarity" varchar(32),
  "base_hp" int NOT NULL DEFAULT 0,
  "base_attack" int NOT NULL DEFAULT 0,
  "base_defense" int NOT NULL DEFAULT 0,
  "base_stamina" int NOT NULL DEFAULT 0,
  "image_credit_id" bigint
);

CREATE TABLE IF NOT EXISTS "user_pokemon" (
  "id" bigserial PRIMARY KEY,
  "owner_user_id" bigint NOT NULL,
  "pokemon_id" int NOT NULL,
  "obtained_at" timestamp NOT NULL DEFAULT (now()),
  "is_locked" boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS "market_listings" (
  "id" bigserial PRIMARY KEY,
  "seller_user_id" bigint NOT NULL,
  "pokemon_instance_id" bigint UNIQUE NOT NULL,
  "currency_id" smallint NOT NULL,
  "price" bigint NOT NULL,
  "status" varchar(16) NOT NULL DEFAULT 'active',
  "start_date" timestamp NOT NULL DEFAULT (now()),
  "end_date" timestamp,
  "purchaser_user_id" bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS image_credits_storage_bucket_object_key_idx
  ON "image_credits" ("storage_bucket", "object_key");

COMMENT ON TABLE "user_settings" IS 'Настройки пользователя и аватар';

COMMENT ON TABLE "pokemon_catalog" IS 'Каталог покемонов (справочник). Статические данные покемонов.';

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

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'market_listings_purchaser_user_id_fkey'
  ) THEN
    ALTER TABLE "market_listings"
      ADD FOREIGN KEY ("purchaser_user_id")
      REFERENCES "users" ("id")
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
