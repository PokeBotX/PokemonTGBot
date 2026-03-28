# Profile Data Model

## Core Read Models

- `ProfileSummary`
  - `telegram_id`
  - `nickname`
  - `language`
  - `created_at`
  - `total_unique_owned`
  - `total_catalog`
  - `total_unique_percent`
  - `rarity_progress`
  - `profile_pic_credit_id`

- `ProfileRarityProgress`
  - `rarity`
  - `owned_unique`
  - `total_catalog`
  - `percent`

- `ProfileReferral`
  - `referral_code`
  - `referral_link`

- `ProfileCoverCandidate`
  - `pokemon_id`
  - `sample_user_pokemon_id`
  - `name`
  - `rarity`
  - `pokemon_type`
  - `image_credit_id`

- `PokemonSearchEntry`
  - `pokemon_id`
  - `name`
  - `rarity`
  - `pokemon_type`
  - base stats
  - `image_credit_id`

## Persistence

- `users`
  - stores telegram id, nickname, created date
- `user_settings`
  - stores `language`
  - stores `profile_pic_credit_id`
- `user_pokemon`
  - source of owned cover eligibility
- `pokemon_catalog`
  - source of rarity totals, search data, image ownership checks

## Important Invariants

- Обложку можно ставить только из покемона, который реально есть у пользователя.
- Для обложки используется только запись с ненулевым `image_credit_id`.
- `/search` работает через SQL с лимитом результатов и не грузит весь каталог в память.
- Ник, язык и обложка должны сохраняться между повторными открытиями профиля.
