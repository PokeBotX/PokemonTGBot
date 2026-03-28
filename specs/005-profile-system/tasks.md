# Tasks: Profile System

**Input**: Design documents from `/specs/005-profile-system/`  
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for profile summary rendering, account-age and collection-progress metrics, nickname updates, language persistence, referral link rendering, default cover fallback, ownership-gated cover selection, and SQL-backed pokemon-name search behavior.

**Organization**: Tasks are grouped by user story so each slice can be implemented and validated independently after the foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US6`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare docs and focused test scaffolding for profile work

- [ ] T001 Create feature support docs for `/specs/005-profile-system/` in [data-model.md](/home/deck/Desktop/pokemonbot/specs/005-profile-system/data-model.md) and [quickstart.md](/home/deck/Desktop/pokemonbot/specs/005-profile-system/quickstart.md)
- [ ] T002 [P] Create dedicated profile test modules in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) and [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core DTOs, database methods, route ids, and persistence helpers required by all profile stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with any missing profile-setting fields needed for language, chosen cover, referral token/link support, and owned-pokemon cover persistence
- [ ] T004 [P] Add profile DTOs and shared helper types to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for summary metrics, rarity progress, cover candidates, and search results
- [ ] T005 [P] Add database methods to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for profile summary queries, nickname update, language update, referral link read, default-cover resolution, and owned-pokemon cover validation
- [ ] T006 [P] Add route names and callback-id conventions in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) for profile root, settings, referral, placeholders, cover search, and search-result selection
- [ ] T007 Add structured logs for profile render, settings changes, referral open, cover-search requests, cover selection success, and rejected ownership checks in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)
- [ ] T008 Write foundational unit tests in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) for account-age formatting, unique-progress math, rarity-progress math, and owned-cover validation rules

**Checkpoint**: Profile data model, summary queries, and shared profile routes are ready for story work

---

## Phase 3: User Story 1 - View the main profile screen (Priority: P1) 🎯 MVP

**Goal**: The user can open a real profile screen with account summary, collection progress, and profile actions

**Independent Test**: Open profile from menu or `/profile` and verify the header, Telegram ID, account age, overall unique progress, rarity progress, and root keyboard are rendered correctly

### Tests for User Story 1

- [ ] T009 [P] [US1] Add unit coverage in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) for summary text rendering and rarity-progress formatting
- [ ] T010 [P] [US1] Add integration coverage in [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py) for opening profile from the menu callback and `/profile`

### Implementation for User Story 1

- [ ] T011 [US1] Replace the placeholder in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) with a real profile root screen renderer
- [ ] T012 [US1] Implement profile summary query usage in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) and [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T013 [US1] Build the main profile keyboard in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) with `Настройки`, `Рефка`, `Боевая команда`, `VIP`, and `Назад в меню`
- [ ] T014 [US1] Make direct `/profile` open the same real profile screen from [bot/handlers/commands.py](/home/deck/Desktop/pokemonbot/bot/handlers/commands.py)

**Checkpoint**: The profile root is usable and no longer a placeholder

---

## Phase 4: User Story 2 - Open settings and change profile data (Priority: P1)

**Goal**: The user can open settings and persist nickname/language changes

**Independent Test**: Open settings, change nickname, change language, and verify both values are saved and shown again on later profile opens

### Tests for User Story 2

- [ ] T015 [P] [US2] Add unit tests in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) for nickname validation and language persistence behavior
- [ ] T016 [P] [US2] Add integration tests in [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py) for opening settings, changing nickname, and changing language

### Implementation for User Story 2

- [ ] T017 [US2] Implement the settings screen and nested back navigation in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)
- [ ] T018 [US2] Implement nickname change flow in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) with DB persistence in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T019 [US2] Implement language selection flow in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) with DB persistence in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T020 [US2] Add user-facing confirmations for nickname and language saves in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)

**Checkpoint**: Settings work end-to-end and survive repeated profile opens

---

## Phase 5: User Story 3 - View and use the referral screen (Priority: P2)

**Goal**: The user can open a lean referral section that shows only the personal referral link

**Independent Test**: Open the referral section and verify the bot shows the user-specific link and proper back buttons

### Tests for User Story 3

- [ ] T021 [P] [US3] Add unit tests in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) for referral-link formatting
- [ ] T022 [P] [US3] Add integration tests in [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py) for opening and leaving the referral screen

### Implementation for User Story 3

- [ ] T023 [US3] Implement referral-link read/generation logic in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T024 [US3] Implement the `Рефка` screen in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) with only the personal link and navigation back to profile

**Checkpoint**: Referral section is working and intentionally minimal

---

## Phase 6: User Story 4 - Choose a profile cover from owned pokemon (Priority: P1)

**Goal**: The user can set a profile cover only from pokemon they already own, with a default cover fallback

**Independent Test**: Open cover selection, search for an owned pokemon, select it, and verify the cover changes; users without a chosen cover still see `image_profile.png`

### Tests for User Story 4

- [ ] T025 [P] [US4] Add unit tests in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) for default-cover fallback and ownership-gated cover candidates
- [ ] T026 [P] [US4] Add integration tests in [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py) for cover search, successful selection, and rejected non-owned selection

### Implementation for User Story 4

- [ ] T027 [US4] Implement default profile-cover resolution using `image_profile.png` in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) and [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T028 [US4] Implement the cover-selection entry screen from `Настройки -> Обложка` in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)
- [ ] T029 [US4] Implement persistence for selected cover image in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) with strict ownership/image checks
- [ ] T030 [US4] Render the chosen cover on subsequent profile openings in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)

**Checkpoint**: Profile cover behaves correctly with default fallback and owned-pokemon restrictions

---

## Phase 7: User Story 5 - Keep placeholder sections for battle team and VIP (Priority: P3)

**Goal**: Team and VIP buttons are visible and safe, even before their real logic exists

**Independent Test**: Open `Боевая команда` and `VIP` from profile and verify each shows a readable placeholder with back navigation

### Tests for User Story 5

- [ ] T031 [P] [US5] Add integration tests in [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py) for both placeholder sections

### Implementation for User Story 5

- [ ] T032 [US5] Implement battle-team placeholder screen in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)
- [ ] T033 [US5] Implement VIP placeholder screen in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)

**Checkpoint**: Full profile keyboard is stable even where deeper subsystems are not ready yet

---

## Phase 8: User Story 6 - Search pokemon by name without loading the entire catalog (Priority: P2)

**Goal**: The bot supports SQL-backed pokemon-name search, direct-card open on one result, and a compact list when there are multiple matches

**Independent Test**: Search by a partial pokemon name and verify one result opens a card immediately while multiple results produce a short choice list; cover search reuses the same foundation but stays ownership-scoped

### Tests for User Story 6

- [ ] T034 [P] [US6] Add unit tests in [tests/unit/test_profile.py](/home/deck/Desktop/pokemonbot/tests/unit/test_profile.py) for SQL-backed search matching and result-shaping rules
- [ ] T035 [P] [US6] Add integration tests in [tests/integration/test_profile_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_profile_flow.py) for one-result direct card open and multi-result compact list behavior

### Implementation for User Story 6

- [ ] T036 [US6] Implement SQL-backed pokemon-name search methods in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) with filtering and result limits instead of full-catalog loading
- [ ] T037 [US6] Implement reusable pokemon search result rendering in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py) for single-result card open and multi-result compact lists
- [ ] T038 [US6] Reserve `/search` for pokemon-name search in [bot/handlers/commands.py](/home/deck/Desktop/pokemonbot/bot/handlers/commands.py), [main.py](/home/deck/Desktop/pokemonbot/main.py), and [main_local.py](/home/deck/Desktop/pokemonbot/main_local.py)
- [ ] T039 [US6] Reuse the same SQL-backed search foundation for owned-only cover search in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)

**Checkpoint**: Pokemon-name search is efficient and reusable for both `/search` and cover selection

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Tighten profile UX, docs, and final verification across all slices

- [ ] T040 [P] Update docs for profile, cover selection, `/find`, and reserved `/search` behavior in [README.md](/home/deck/Desktop/pokemonbot/README.md) and [README_SETUP.txt](/home/deck/Desktop/pokemonbot/README_SETUP.txt)
- [ ] T041 [P] Review and tighten profile message length and navigation clarity in [bot/handlers/sections/profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py)
- [ ] T042 Run targeted verification with `uv run pytest tests/unit/test_profile.py tests/integration/test_profile_flow.py tests/integration/test_handlers.py -v` and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-8**: Depend on Phase 2; US1 should land first because it establishes the real profile root, US2 depends on profile navigation, US3 depends on root navigation, US4 depends on summary plus settings flow, US5 depends on the real root keyboard, and US6 depends on foundational DB/query helpers and is reusable by US4
- **Phase 9**: Depends on completion of all desired stories

### User Story Dependencies

- **US1**: Starts after foundational summary queries and route structure exist
- **US2**: Depends on US1 profile root and settings navigation
- **US3**: Depends on US1 root navigation
- **US4**: Depends on US1 and US2, plus shared image/ownership helpers
- **US5**: Depends on US1 root keyboard
- **US6**: Depends on foundational DB/query helpers and can be built alongside later profile UX, but should land before finalizing cover-search UX

### Parallel Opportunities

- T004, T005, and T006 can run in parallel after schema shape is settled
- T009 and T010 can run in parallel for US1
- T015 and T016 can run in parallel for US2
- T021 and T022 can run in parallel for US3
- T025 and T026 can run in parallel for US4
- T034 and T035 can run in parallel for US6
- T040 and T041 can run in parallel during polish

## Implementation Strategy

### MVP First

1. Complete Phases 1-2
2. Deliver US1 profile root
3. Deliver US2 settings persistence
4. Deliver US4 cover selection with default fallback
5. Deliver US3 referral screen
6. Deliver US5 placeholders
7. Deliver US6 efficient pokemon-name search
8. Validate and polish

### Incremental Delivery

1. Foundation: summary queries, routes, DTOs, and tests
2. Root profile slice: header, progress, keyboard
3. Settings slice: nickname and language writes
4. Referral and placeholder slice
5. Cover slice: default image plus owned-only selection
6. Search slice: SQL-backed pokemon-name search reused by cover selection
7. Final polish and verification

## Notes

- Keep profile summary queries aggregate-first; avoid Python-side full-catalog processing.
- Treat profile cover ownership as a hard invariant.
- Reuse existing pokemon-card rendering where practical instead of inventing a second card format.
- Keep `/find` reserved for group encounter spawning and `/search` reserved for pokemon-name lookup.
