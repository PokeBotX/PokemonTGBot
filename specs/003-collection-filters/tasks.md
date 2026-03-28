# Tasks: Collection Browsing and Filters

**Input**: Design documents from `/specs/003-collection-filters/`  
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for collection aggregation, duplicate filtering, two-type selection limits, type-filter `AND` semantics, page persistence, empty states, and callback safety.

**Organization**: Tasks are grouped by user story so each slice can be implemented and validated independently after the foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US4`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare feature docs and test scaffolding for collection work

- [ ] T001 Create feature support docs for `/specs/003-collection-filters/` in [data-model.md](/home/deck/Desktop/pokemonbot/specs/003-collection-filters/data-model.md) and [quickstart.md](/home/deck/Desktop/pokemonbot/specs/003-collection-filters/quickstart.md)
- [ ] T002 [P] Create dedicated collection test modules in [tests/unit/test_collection.py](/home/deck/Desktop/pokemonbot/tests/unit/test_collection.py) and [tests/integration/test_collection_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_collection_flow.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core collection DTOs, database queries, and shared helpers that all stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Add collection DTOs and filter-state models to [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for aggregated entries, filter state, and paginated result sets
- [ ] T004 [P] Add shared collection constants and helper functions in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py) for page size, normalized type parsing, rarity markers, and default filter state
- [ ] T005 [P] Implement aggregated collection read queries in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) using `user_pokemon` joined with `pokemon_catalog`
- [ ] T006 [P] Implement collection filtering support in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for rarities, normalized types, duplicates-only, and total counts
- [ ] T007 Add structured logging points for collection page renders, filter toggles, resets, and detail-card navigation in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T008 Write foundational unit tests in [tests/unit/test_collection.py](/home/deck/Desktop/pokemonbot/tests/unit/test_collection.py) for type normalization, two-type limit behavior, duplicates semantics, and collection line formatting

**Checkpoint**: Database API, collection models, and shared collection rules are ready for story work

---

## Phase 3: User Story 1 - Open the collection and browse owned pokemon (Priority: P1) 🎯 MVP

**Goal**: User can open the collection, see aggregated owned pokemon, and move between pages without losing the current browsing context

**Independent Test**: Open the collection from the main menu or `/collection` and verify first-page rendering, page counts, empty state, and previous/next navigation

### Tests for User Story 1

- [ ] T009 [P] [US1] Add integration coverage in [tests/integration/test_collection_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_collection_flow.py) for opening the collection from menu and direct command
- [ ] T010 [P] [US1] Add unit coverage in [tests/unit/test_collection.py](/home/deck/Desktop/pokemonbot/tests/unit/test_collection.py) for page slicing, result summaries, and empty-state rendering

### Implementation for User Story 1

- [ ] T011 [US1] Replace the placeholder handler with a real collection screen implementation in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T012 [US1] Register collection routes and callback handling updates in [bot/handlers/navigation.py](/home/deck/Desktop/pokemonbot/bot/handlers/navigation.py) and [bot/navigation/router.py](/home/deck/Desktop/pokemonbot/bot/navigation/router.py)
- [ ] T013 [US1] Update collection command entry and menu wiring in [bot/handlers/commands.py](/home/deck/Desktop/pokemonbot/bot/handlers/commands.py) and [bot/ui/menu.py](/home/deck/Desktop/pokemonbot/bot/ui/menu.py)
- [ ] T014 [US1] Implement collection text rendering, page navigation buttons, and main-menu back action in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)

**Checkpoint**: Collection screen is reachable and usable as a Telegram UI slice

---

## Phase 4: User Story 2 - Filter collection by rarity and type (Priority: P1)

**Goal**: User can open a dedicated filter screen, toggle rarities and up to two types, and immediately see filtered collection results

**Independent Test**: Seed owned pokemon with several rarities/types, open filters, toggle them, and verify filtered results plus active-filter state

### Tests for User Story 2

- [ ] T015 [P] [US2] Add unit tests in [tests/unit/test_collection.py](/home/deck/Desktop/pokemonbot/tests/unit/test_collection.py) for rarity filter combinations, type filter `AND` matching, and max-two-type enforcement
- [ ] T016 [P] [US2] Add integration tests in [tests/integration/test_collection_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_collection_flow.py) for opening filter screen, toggling filters, and returning to the filtered collection

### Implementation for User Story 2

- [ ] T017 [US2] Implement dedicated collection filter screen rendering in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T018 [US2] Implement rarity toggle callbacks and active-filter state handling in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T019 [US2] Implement type toggle callbacks with a hard limit of two selected types in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T020 [US2] Connect filter-state-aware collection queries in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)

**Checkpoint**: User can filter the collection by rarity and type from a dedicated Telegram screen

---

## Phase 5: User Story 3 - Show only duplicate pokemon and reset filters (Priority: P1)

**Goal**: User can restrict the collection to duplicate species only and reset all filters with one action

**Independent Test**: Enable duplicates-only, verify only species with quantity greater than one remain, then press reset and verify the full collection returns

### Tests for User Story 3

- [ ] T021 [P] [US3] Add unit tests in [tests/unit/test_collection.py](/home/deck/Desktop/pokemonbot/tests/unit/test_collection.py) for duplicates-only filtering and reset-to-default filter state
- [ ] T022 [P] [US3] Add integration tests in [tests/integration/test_collection_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_collection_flow.py) for duplicates toggle, no-results case, and reset action

### Implementation for User Story 3

- [ ] T023 [US3] Implement duplicates-only filter toggle in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T024 [US3] Implement reset-filters action and default-state restoration in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T025 [US3] Finalize empty-state messages for no matches, no duplicates, and empty collection in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)

**Checkpoint**: Duplicate discovery and one-click reset work independently of other improvements

---

## Phase 6: User Story 4 - Open pokemon cards from the collection while preserving filter context (Priority: P2)

**Goal**: User can press entry buttons below the collection and open pokemon cards without losing current collection filters and page state

**Independent Test**: Apply filters, navigate to a page, open a pokemon card from an entry button, then return to the collection flow with the same browsing context intact

### Tests for User Story 4

- [ ] T026 [P] [US4] Add unit tests in [tests/unit/test_collection.py](/home/deck/Desktop/pokemonbot/tests/unit/test_collection.py) for button-to-entry mapping and preserved collection state payloads
- [ ] T027 [P] [US4] Add integration tests in [tests/integration/test_collection_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_collection_flow.py) for opening detail cards from collection buttons and keeping collection navigation valid afterward

### Implementation for User Story 4

- [ ] T028 [US4] Implement per-entry inline buttons below collection results in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)
- [ ] T029 [US4] Implement collection detail-card callback flow in [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py), reusing existing pokemon card rendering where practical
- [ ] T030 [US4] Preserve current collection page and filter state across detail-card navigation in [bot/navigation/session.py](/home/deck/Desktop/pokemonbot/bot/navigation/session.py) and [bot/handlers/sections/collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py)

**Checkpoint**: Collection list and detail-card entrypoint work together as one Telegram flow

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tighten callback safety, docs, and final verification across the feature

- [ ] T031 [P] Add duplicate-click and stale-session integration coverage for collection callbacks in [tests/integration/test_collection_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_collection_flow.py)
- [ ] T032 [P] Update user-facing docs for collection browsing and filters in [README.md](/home/deck/Desktop/pokemonbot/README.md) and [README_SETUP.txt](/home/deck/Desktop/pokemonbot/README_SETUP.txt)
- [ ] T033 Run targeted verification with `uv run pytest tests/unit/test_collection.py tests/integration/test_collection_flow.py tests/integration/test_handlers.py -v` and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-6**: Depend on Phase 2; US1 should land first because it provides the base collection screen, US2 and US3 build directly on that screen, and US4 depends on the collection entry buttons from US1
- **Phase 7**: Depends on completion of all desired stories

### User Story Dependencies

- **US1**: Starts after foundational DTOs, collection queries, and shared helpers exist
- **US2**: Depends on US1 collection screen and foundational filtering support
- **US3**: Depends on US2 filter screen and foundational filtering support
- **US4**: Depends on US1 collection rendering and the stable filter/page state model from US2/US3

### Parallel Opportunities

- T004, T005, and T006 can run in parallel after the collection DTO shape is settled
- T009 and T010 can run in parallel for US1
- T015 and T016 can run in parallel for US2
- T021 and T022 can run in parallel for US3
- T026 and T027 can run in parallel for US4
- T031 and T032 can run in parallel during polish

## Implementation Strategy

### MVP First

1. Complete Phases 1-2
2. Deliver US1 collection browsing with pagination
3. Deliver US2 rarity/type filtering
4. Deliver US3 duplicates-only and reset
5. Deliver US4 detail-card entrypoint
6. Validate callback safety and filter persistence before polishing

### Incremental Delivery

1. Foundation: DTOs, aggregated queries, shared helpers, and test scaffolding
2. Browsing slice: collection screen, page controls, and command/menu entry
3. Filtering slice: dedicated filter screen plus rarity/type toggles
4. Duplicate/reset slice: duplicates-only logic and one-click reset
5. Detail slice: entry buttons and card-navigation preservation

## Notes

- Each story should remain independently testable after Phase 2
- Prefer extending existing session/navigation patterns instead of building a separate collection framework
- Keep Telegram collection text compact and readable, especially with 12 entries per page
- Type filtering must operate on normalized individual types rather than raw stored strings like `fire/flying`
