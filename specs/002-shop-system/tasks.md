# Tasks: Shop, Daily Bonus, and Gacha

**Input**: Design documents from `/specs/002-shop-system/`
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for balance spending, one-hour bonus gating, pity progression, guaranteed rarity thresholds, and duplicate-click safety.

**Organization**: Tasks are grouped by user story so each slice can be implemented and validated independently after the foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US6`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare feature docs and test scaffolding for shop work

- [ ] T001 Create feature support docs for `/specs/002-shop-system/` in [data-model.md](/home/deck/Desktop/pokemonbot/specs/002-shop-system/data-model.md) and [quickstart.md](/home/deck/Desktop/pokemonbot/specs/002-shop-system/quickstart.md)
- [ ] T002 [P] Create dedicated shop test modules in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) and [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core persistence, database APIs, and shared shop helpers that all stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with persistent shop state storage for per-user bonus timing and pity counters
- [ ] T004 Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with item seed data for `ultraball` and `masterball` compatible with the existing `items` and `user_items` tables
- [ ] T005 [P] Add shop-state read/write methods to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for loading shop state, initializing defaults, and updating pity counters
- [ ] T006 [P] Add economy transaction methods to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for bonus claim, item purchase, single spin, and sequential `x5` spin processing with balance safety
- [ ] T007 [P] Add shared shop constants and helpers in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py) for prices, rarity probabilities, bonus rate, and pity thresholds
- [ ] T008 Add structured logging points for shop operations in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)
- [ ] T009 Write foundational unit tests in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) for bonus accumulation math, pity counter transitions, and `x5` sequential spin evaluation

**Checkpoint**: Database schema, persistence API, and shared shop rules are ready for story work

---

## Phase 3: User Story 1 - Open the shop screen and see available actions (Priority: P1) 🎯 MVP

**Goal**: User can enter the shop from the main menu and see balance, pity counters, grouped actions, VIP placeholder, and back navigation

**Independent Test**: Open the shop from the existing menu and verify the rendered message contains grouped actions, balance, pity counters, VIP placeholder, and back button

### Tests for User Story 1

- [ ] T010 [P] [US1] Add integration coverage in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py) for opening the shop from the menu and rendering grouped actions
- [ ] T011 [P] [US1] Add unit coverage in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) for shop text formatting and action visibility by balance

### Implementation for User Story 1

- [ ] T012 [US1] Implement shop message rendering and keyboard builder in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)
- [ ] T013 [US1] Register shop section handling and routing updates in [bot/handlers/navigation.py](/home/deck/Desktop/pokemonbot/bot/handlers/navigation.py) and [bot/navigation/router.py](/home/deck/Desktop/pokemonbot/bot/navigation/router.py)
- [ ] T014 [US1] Update menu metadata and button wiring for the shop entrypoint in [bot/ui/menu.py](/home/deck/Desktop/pokemonbot/bot/ui/menu.py) and [bot/ui/messages.py](/home/deck/Desktop/pokemonbot/bot/ui/messages.py)
- [ ] T015 [US1] Implement the VIP placeholder callback and "Назад в меню" flow in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py) and [bot/handlers/sections/back.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/back.py)

**Checkpoint**: Shop screen is reachable and usable as a Telegram UI slice

---

## Phase 4: User Story 2 - Claim accumulated daily bonus (Priority: P1)

**Goal**: User can claim accumulated `pokedollar` bonus, see how much was received, and see remaining time when claim is not yet available

**Independent Test**: Seed a user with shop state, open the shop, claim a bonus, and verify balance change plus correct cooldown messaging

### Tests for User Story 2

- [ ] T016 [P] [US2] Add unit tests in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) for hourly bonus accumulation, one-hour minimum claim interval, and 750-cap behavior
- [ ] T017 [P] [US2] Add integration tests in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py) for successful claim and early-claim cooldown response

### Implementation for User Story 2

- [ ] T018 [US2] Implement bonus claim callback flow in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)
- [ ] T019 [US2] Implement transactional bonus claim persistence in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T020 [US2] Update shop rendering so bonus status and remaining cooldown are visible in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)

**Checkpoint**: Daily bonus loop is fully functional and independently testable

---

## Phase 5: User Story 3 - Buy shop items and gacha spins (Priority: P1)

**Goal**: User can spend `pokedollar` on `ultraball`, `masterball`, one spin, and `x5` spins; unavailable actions stay hidden

**Independent Test**: Vary user balance and verify visible actions, then perform purchases and confirm balances and inventory updates

### Tests for User Story 3

- [ ] T021 [P] [US3] Add unit tests in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) for action visibility thresholds and item purchase pricing
- [ ] T022 [P] [US3] Add integration tests in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py) for item purchases and spin purchase availability

### Implementation for User Story 3

- [ ] T023 [US3] Implement single-item purchase callbacks for `ultraball` and `masterball` in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)
- [ ] T024 [US3] Implement balance-safe item purchase database operations in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T025 [US3] Implement balance-aware visibility rules for `Крутка x1`, `Крутка x5`, `Ultraball`, and `Masterball` in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)

**Checkpoint**: Shop purchases and action visibility rules work independently of reward delivery details

---

## Phase 6: User Story 4 - Receive a pokemon from gacha with rarity and pity rules (Priority: P1)

**Goal**: User can perform single or `x5` spins, receive pokemon based on rarity rules, and progress pity counters correctly

**Independent Test**: Execute spins against seeded catalog data and verify reward issuance, pity guarantees, fallback image behavior, and `x5` summary/detail flows

### Tests for User Story 4

- [ ] T026 [P] [US4] Add unit tests in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) for rarity selection, `Epic` pity at 15, `Legendary` pity at 40, and non-reset of `Epic` pity on legendary drops
- [ ] T027 [P] [US4] Add integration tests in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py) for single spin result delivery, `x5` summary generation, and separate detail messages

### Implementation for User Story 4

- [ ] T028 [US4] Implement gacha reward selection and pity application helpers in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)
- [ ] T029 [US4] Implement transactional single-spin and sequential `x5` spin execution in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T030 [US4] Implement single-spin result messages with fallback `image.png` handling in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)
- [ ] T031 [US4] Implement `x5` summary message and per-result detail callbacks as separate messages in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)

**Checkpoint**: End-to-end gacha loop works with persistent pity progression and result messaging

---

## Phase 7: User Story 5 - Track pity progress across sessions (Priority: P2)

**Goal**: Pity counters and shop state survive bot restarts and later shop visits

**Independent Test**: Seed pity state, reload the shop in a later interaction, and verify counters are preserved and displayed correctly

### Tests for User Story 5

- [ ] T032 [P] [US5] Add unit tests in [tests/unit/test_shop.py](/home/deck/Desktop/pokemonbot/tests/unit/test_shop.py) for default shop-state initialization and restored pity progress
- [ ] T033 [P] [US5] Add integration tests in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py) for reopening the shop after persisted progress

### Implementation for User Story 5

- [ ] T034 [US5] Implement default shop-state initialization on first access in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T035 [US5] Render persisted pity counters and cooldown state on every shop refresh in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)

**Checkpoint**: Shop progress persists correctly between sessions

---

## Phase 8: User Story 6 - Future premium button placeholder (Priority: P3)

**Goal**: VIP remains visible in the UI but does not affect economy or state

**Independent Test**: Press VIP and verify the bot returns a placeholder message only

### Tests for User Story 6

- [ ] T036 [P] [US6] Add integration coverage in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py) for VIP placeholder behavior

### Implementation for User Story 6

- [ ] T037 [US6] Finalize VIP placeholder copy and no-op handling in [bot/handlers/sections/shop.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py)

**Checkpoint**: Non-functional premium placeholder is stable and isolated

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Tighten safety, docs, and validation across the feature

- [ ] T038 [P] Add duplicate-click and idempotency integration coverage for shop callbacks in [tests/integration/test_shop_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_shop_flow.py)
- [ ] T039 [P] Update setup and troubleshooting docs for PostgreSQL-backed shop flows in [README_SETUP.txt](/home/deck/Desktop/pokemonbot/README_SETUP.txt), [README.md](/home/deck/Desktop/pokemonbot/README.md), and [TROUBLESHOOTING.md](/home/deck/Desktop/pokemonbot/TROUBLESHOOTING.md)
- [ ] T040 Run targeted verification with `uv run pytest tests/unit/test_shop.py tests/integration/test_shop_flow.py -v` and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-8**: Depend on Phase 2; higher-priority stories should land first, but US5 and US6 can begin after the shared persistence and shop handlers exist
- **Phase 9**: Depends on completion of all desired stories

### User Story Dependencies

- **US1**: Starts after foundational schema, DB APIs, and shared shop constants exist
- **US2**: Depends on US1 rendering entrypoint plus foundational persistence
- **US3**: Depends on US1 rendering entrypoint plus foundational persistence
- **US4**: Depends on US3 purchase flow and foundational persistence
- **US5**: Depends on foundational persistence and at least partial US4 reward flow
- **US6**: Depends on US1 shop screen

### Parallel Opportunities

- T005, T006, and T007 can run in parallel after schema design is settled
- T010 and T011 can run in parallel for US1
- T016 and T017 can run in parallel for US2
- T021 and T022 can run in parallel for US3
- T026 and T027 can run in parallel for US4
- T032 and T033 can run in parallel for US5
- T038 and T039 can run in parallel during polish

## Implementation Strategy

### MVP First

1. Complete Phases 1-2
2. Deliver US1 shop screen
3. Deliver US2 daily bonus
4. Deliver US3 purchases
5. Deliver US4 gacha loop
6. Validate the full economy flow before moving to persistence polish

### Incremental Delivery

1. Foundation: schema, DB methods, constants, logging, and shop tests
2. UI slice: shop screen and placeholder actions
3. Economy slice: daily bonus and item spending
4. Reward slice: single spin, `x5`, pity, and result messaging
5. Persistence slice: restored pity state and remaining polish

## Notes

- Each story should remain independently testable after Phase 2
- Database changes and reward issuance must remain atomic
- Prefer extending existing menu/navigation patterns instead of introducing a parallel shop framework
- Keep Telegram messages compact and explicit about state, cooldowns, and insufficient balance
