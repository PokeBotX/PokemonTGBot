# Tasks: Chat Pokemon Encounters

**Input**: Design documents from `/specs/004-chat-encounters/`  
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for encounter cooldown gating, 10-message trigger logic, `/find` triggering, one-attempt-per-user enforcement, inventory consumption, concurrent capture safety, successful reward issuance, and 5-minute timeout cleanup.

**Organization**: Tasks are grouped by user story so each slice can be implemented and validated independently after the foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US4`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare feature docs and test scaffolding for chat encounter work

- [ ] T001 Create feature support docs for `/specs/004-chat-encounters/` in [data-model.md](/home/deck/Desktop/pokemonbot/specs/004-chat-encounters/data-model.md) and [quickstart.md](/home/deck/Desktop/pokemonbot/specs/004-chat-encounters/quickstart.md)
- [ ] T002 [P] Create dedicated encounter test modules in [tests/unit/test_chat_encounters.py](/home/deck/Desktop/pokemonbot/tests/unit/test_chat_encounters.py) and [tests/integration/test_chat_encounters_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_chat_encounters_flow.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema, encounter state models, and database APIs that all stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with persistent per-chat encounter state storage for cooldown timestamps, message counters, active encounter metadata, and timeout data
- [ ] T004 Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with encounter-attempt storage that records one attempt per user per active encounter
- [ ] T005 [P] Add encounter DTOs and shared constants to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for spawn cooldown, message thresholds, timeout duration, and ball capture chances
- [ ] T006 [P] Add database methods to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for chat-state initialization, spawn eligibility checks, encounter creation, attempt tracking, timeout cleanup, and successful reward issuance
- [ ] T007 [P] Add encounter helper functions in a new module [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py) for encounter text, callback ids, and ball resolution rules
- [ ] T008 Add structured logging points for encounter spawn checks, spawn creation, capture attempts, timeout expiry, and reward assignment in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py)
- [ ] T009 Write foundational unit tests in [tests/unit/test_chat_encounters.py](/home/deck/Desktop/pokemonbot/tests/unit/test_chat_encounters.py) for cooldown math, capture probabilities, one-attempt-per-user rules, and timeout eligibility

**Checkpoint**: Encounter schema, persistence API, and shared encounter rules are ready for story work

---

## Phase 3: User Story 1 - Spawn a wild pokemon encounter in a group chat (Priority: P1) 🎯 MVP

**Goal**: A pokemon can appear in a group chat after cooldown and trigger conditions are met, but never in private chats

**Independent Test**: Simulate group-chat traffic and verify that after cooldown expiry plus 10 messages or `/find`, the bot posts one encounter message with image and ball buttons; private chats never trigger this flow

### Tests for User Story 1

- [ ] T010 [P] [US1] Add integration coverage in [tests/integration/test_chat_encounters_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_chat_encounters_flow.py) for group-chat spawn from message threshold and private-chat non-support
- [ ] T011 [P] [US1] Add unit coverage in [tests/unit/test_chat_encounters.py](/home/deck/Desktop/pokemonbot/tests/unit/test_chat_encounters.py) for spawn gating by cooldown and message count

### Implementation for User Story 1

- [ ] T012 [US1] Implement encounter message rendering and encounter keyboard builder in [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py)
- [ ] T013 [US1] Add a group-message trigger handler in [bot/handlers/chat_activity.py](/home/deck/Desktop/pokemonbot/bot/handlers/chat_activity.py) that counts messages and requests encounter spawn checks
- [ ] T014 [US1] Register the group-message handler in [main.py](/home/deck/Desktop/pokemonbot/main.py) and [main_local.py](/home/deck/Desktop/pokemonbot/main_local.py) without affecting private-chat command flows
- [ ] T015 [US1] Ensure encounter image selection reuses pokemon image metadata with fallback image handling in [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py)

**Checkpoint**: Wild pokemon can appear in eligible chats and do not appear in private dialogs

---

## Phase 4: User Story 2 - Let any chat member try to catch the encountered pokemon (Priority: P1)

**Goal**: Encounter buttons can be pressed by any participant in the chat, while still enforcing one attempt per user per encounter

**Independent Test**: Have multiple simulated users click the same encounter buttons and verify that each user gets at most one attempt while other users remain allowed to try

### Tests for User Story 2

- [ ] T016 [P] [US2] Add unit tests in [tests/unit/test_chat_encounters.py](/home/deck/Desktop/pokemonbot/tests/unit/test_chat_encounters.py) for one-attempt-per-user enforcement and unrestricted participant access
- [ ] T017 [P] [US2] Add integration tests in [tests/integration/test_chat_encounters_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_chat_encounters_flow.py) for multi-user click behavior on one encounter

### Implementation for User Story 2

- [ ] T018 [US2] Implement encounter-specific callback routing in [bot/handlers/chat_encounter_navigation.py](/home/deck/Desktop/pokemonbot/bot/handlers/chat_encounter_navigation.py) that validates chat/message context but deliberately skips normal single-user button ownership checks
- [ ] T019 [US2] Register encounter callback routes and handlers in [main.py](/home/deck/Desktop/pokemonbot/main.py), [main_local.py](/home/deck/Desktop/pokemonbot/main_local.py), and [bot/navigation/router.py](/home/deck/Desktop/pokemonbot/bot/navigation/router.py) or a dedicated encounter router
- [ ] T020 [US2] Implement one-attempt-per-user persistence checks in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and enforce them from [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py)

**Checkpoint**: Encounter clicks are open to all chat members, but each member only gets one try per encounter

---

## Phase 5: User Story 3 - Resolve encounter capture using ball tiers and rarity-based spawn odds (Priority: P1)

**Goal**: Encounter pokemon spawn with gacha rarity odds, attempts resolve with configured ball chances, and successful catches award the pokemon

**Independent Test**: Force an encounter, perform attempts with regular/ultra/master balls, and verify correct success chances, inventory consumption, and collection reward behavior

### Tests for User Story 3

- [ ] T021 [P] [US3] Add unit tests in [tests/unit/test_chat_encounters.py](/home/deck/Desktop/pokemonbot/tests/unit/test_chat_encounters.py) for encounter rarity selection, regular/ultra/master capture chances, and masterball guarantee
- [ ] T022 [P] [US3] Add integration tests in [tests/integration/test_chat_encounters_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_chat_encounters_flow.py) for successful capture, failed callback notification, and inventory consumption on ultra/master attempts

### Implementation for User Story 3

- [ ] T023 [US3] Implement encounter pokemon selection in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) using the same rarity distribution as the gacha/shop flow
- [ ] T024 [US3] Implement ball-specific attempt resolution in [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py) for regular pokeball `60%`, ultraball `80%`, and masterball `100%`
- [ ] T025 [US3] Implement ultraball/masterball inventory deduction in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) with consumption on every attempt, including failures
- [ ] T026 [US3] Implement successful reward issuance and encounter close-out in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) plus encounter message editing in [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py)

**Checkpoint**: Full encounter catch loop works with real ball rules and reward delivery

---

## Phase 6: User Story 4 - Respect chat cooldown and hidden spawn progression (Priority: P2)

**Goal**: Cooldown, message thresholds, and 5-minute encounter expiration work consistently and invisibly for users

**Independent Test**: Simulate repeated chat activity around cooldown boundaries and verify hidden cooldown gating, `/search` behavior, and 5-minute timeout cleanup

### Tests for User Story 4

- [ ] T027 [P] [US4] Add unit tests in [tests/unit/test_chat_encounters.py](/home/deck/Desktop/pokemonbot/tests/unit/test_chat_encounters.py) for cooldown reset, message-threshold reset, and timeout expiration rules
- [ ] T028 [P] [US4] Add integration tests in [tests/integration/test_chat_encounters_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_chat_encounters_flow.py) for `/search`, timeout cleanup, and cooldown-hidden behavior

### Implementation for User Story 4

- [ ] T029 [US4] Implement `/find` group-chat command handling in [bot/handlers/commands.py](/home/deck/Desktop/pokemonbot/bot/handlers/commands.py) and register it in [main.py](/home/deck/Desktop/pokemonbot/main.py) and [main_local.py](/home/deck/Desktop/pokemonbot/main_local.py)
- [ ] T030 [US4] Implement 5-minute timeout cleanup and encounter-expired message editing in [bot/handlers/sections/chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py) and [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T031 [US4] Ensure repeated messages and `/search` calls cannot create overlapping active encounters in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)

**Checkpoint**: Encounter frequency stays controlled, hidden cooldown works, and stale encounters disappear correctly

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tighten concurrency safety, docs, and final verification across the feature

- [ ] T032 [P] Add concurrent-click and double-capture integration coverage in [tests/integration/test_chat_encounters_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_chat_encounters_flow.py)
- [ ] T033 [P] Update setup and troubleshooting docs for encounter features in [README.md](/home/deck/Desktop/pokemonbot/README.md), [README_SETUP.txt](/home/deck/Desktop/pokemonbot/README_SETUP.txt), and [TROUBLESHOOTING.md](/home/deck/Desktop/pokemonbot/TROUBLESHOOTING.md)
- [ ] T034 Run targeted verification with `uv run pytest tests/unit/test_chat_encounters.py tests/integration/test_chat_encounters_flow.py tests/integration/test_handlers.py -v` and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-6**: Depend on Phase 2; US1 should land first because encounter spawning is the entrypoint for the rest, US2 depends on an active encounter message, US3 depends on both encounter spawning and click handling, and US4 hardens cooldown and timeout behavior around the complete flow
- **Phase 7**: Depends on completion of all desired stories

### User Story Dependencies

- **US1**: Starts after foundational schema, encounter state models, and spawn-check APIs exist
- **US2**: Depends on US1 encounter creation and message rendering
- **US3**: Depends on US2 callback path and foundational persistence
- **US4**: Depends on US1 spawn state plus US3 encounter lifecycle handling

### Parallel Opportunities

- T005, T006, and T007 can run in parallel after schema shape is settled
- T010 and T011 can run in parallel for US1
- T016 and T017 can run in parallel for US2
- T021 and T022 can run in parallel for US3
- T027 and T028 can run in parallel for US4
- T032 and T033 can run in parallel during polish

## Implementation Strategy

### MVP First

1. Complete Phases 1-2
2. Deliver US1 encounter spawning in eligible chats
3. Deliver US2 open-to-all encounter clicking with one-attempt-per-user protection
4. Deliver US3 capture resolution and reward issuance
5. Deliver US4 cooldown hardening and timeout cleanup
6. Validate concurrency and cleanup before polishing

### Incremental Delivery

1. Foundation: schema, DTOs, state APIs, and encounter helper rules
2. Trigger slice: group messages and `/search`
3. Interaction slice: encounter callbacks open to any user
4. Reward slice: ball resolution, inventory usage, and reward issuance
5. Lifecycle slice: timeout cleanup, no-overlap guarantees, and observability

## Notes

- Keep encounter callback handling separate from normal menu ownership rules
- Prefer explicit database-backed chat state over implicit in-memory counters so cooldown and message progress survive restarts
- Treat encounter closure as a critical transaction: one winner, one reward, no double-catch
- Keep user-facing chat noise low: failed attempts use callback notifications, while success and timeout are reflected by editing the encounter message
