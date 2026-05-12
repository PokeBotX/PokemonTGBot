# Tasks: Pokedex

**Input**: Design documents from [spec.md](/home/deck/Desktop/pokemonbot/specs/015-pokedex/spec.md)  
**Prerequisites**: Existing collection filters, pokemon forms support, market request prechecks

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (disjoint files, no blocking dependency)
- **[Story]**: Which user story this task primarily supports (`US1`, `US2`, etc.)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare focused test and doc surfaces for the new Mini App feature.

- [ ] T001 Create focused backend/frontend test coverage entrypoints for pokedex list, detail, and buy-request precheck behavior under [tests/unit](/home/deck/Desktop/pokemonbot/tests/unit) and [tests/integration](/home/deck/Desktop/pokemonbot/tests/integration)
- [ ] T002 Add auxiliary docs if needed (`data-model.md`, `quickstart.md`) under [specs/015-pokedex](/home/deck/Desktop/pokemonbot/specs/015-pokedex)

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add reusable backend query and serialization helpers before any UI work.

**⚠️ CRITICAL**: No story work should start until this phase is complete.

- [ ] T003 [P] Add DB/domain read models for form-aware pokedex entries, owned-state badges, and read-only detail payloads in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T004 [P] Add shared natural sort helper usage for base-first plus form-order pokedex listing
- [ ] T005 [P] Add shared filter/search normalization helpers for collected-state and form-kind filters
- [ ] T006 [P] Add response builders in [main.py](/home/deck/Desktop/pokemonbot/main.py) for pokedex list payloads and read-only detail payloads
- [ ] T007 [P] Add shared buy-request precheck helper reuse so pokedex detail does not fork market validation logic

## Phase 3: User Story 1 - Open a full-form pokedex from the profile (Priority: P1)

**Goal**: Let the player open a Mini App pokedex from `Всего форм: N` and browse visible owned/unowned cards.

**Independent Test**: Tap `Всего форм: N` in profile and verify a paginated full-form pokedex opens with correct owned-state badges and dimmed unowned entries.

### Tests for User Story 1

- [ ] T008 [P] [US1] Add tests for opening pokedex from profile and loading the first page of form-aware catalog entries
- [ ] T009 [P] [US1] Add tests that owned base and owned alternate forms are tracked independently on cards

### Implementation for User Story 1

- [ ] T010 [US1] Add backend pokedex list query in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T011 [US1] Add Mini App endpoint(s) for pokedex browse payloads in [main.py](/home/deck/Desktop/pokemonbot/main.py)
- [ ] T012 [US1] Add Mini App pokedex route/page and mini-card rendering in [frontend/src/app](/home/deck/Desktop/pokemonbot/frontend/src/app) and [frontend/src/components](/home/deck/Desktop/pokemonbot/frontend/src/components)
- [ ] T013 [US1] Wire the profile `Всего форм: N` control to open pokedex from [frontend/src/components/profile-card.tsx](/home/deck/Desktop/pokemonbot/frontend/src/components/profile-card.tsx)

## Phase 4: User Story 2 - Filter, search, and sort the pokedex without losing form detail (Priority: P1)

**Goal**: Preserve collection-grade browsing controls while keeping the list full-form-aware.

**Independent Test**: Search by id/name and use type, rarity, collected, and form-kind filters while verifying stable base-first form ordering and paginated results.

### Tests for User Story 2

- [ ] T014 [P] [US2] Add tests for pokedex filter combinations including collected/not-collected and shiny/mega/gigantamax
- [ ] T015 [P] [US2] Add tests for search by base dex id, form display id, and name
- [ ] T016 [P] [US2] Add tests for stable ordering by base dex id followed by form order

### Implementation for User Story 2

- [ ] T017 [US2] Extend pokedex DB query logic with collection-style rarity/type filters excluding duplicates
- [ ] T018 [US2] Extend Mini App pokedex UI with collected/not-collected and form-kind filter controls
- [ ] T019 [US2] Add search input and paginated query-state preservation for pokedex list navigation
- [ ] T020 [US2] Preserve filter/search/page context when navigating from pokedex list to detail and back

## Phase 5: User Story 3 - Inspect a pokedex entry and optionally create a buy request (Priority: P1)

**Goal**: Provide a read-only detail page with stats, related-form hints, and a buy-request CTA with immediate prechecks.

**Independent Test**: Open owned and unowned pokedex details, verify no instance actions exist, and confirm buy-request prechecks block invalid actions before any request-confirm step.

### Tests for User Story 3

- [ ] T021 [P] [US3] Add tests for read-only pokedex detail payloads for owned and unowned entries
- [ ] T022 [P] [US3] Add tests for related-form hints on entries that have sibling forms
- [ ] T023 [P] [US3] Add tests for buy-request precheck failure when request slots are full or balance is insufficient

### Implementation for User Story 3

- [ ] T024 [US3] Add pokedex detail backend query in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T025 [US3] Add Mini App pokedex detail endpoint in [main.py](/home/deck/Desktop/pokemonbot/main.py)
- [ ] T026 [US3] Add read-only pokedex detail page in [frontend/src/app](/home/deck/Desktop/pokemonbot/frontend/src/app) with stats and related-form hints
- [ ] T027 [US3] Add a single buy-request CTA plus precheck/error flow on pokedex detail

## Phase 6: User Story 4 - Understand collected state on each mini card at a glance (Priority: P2)

**Goal**: Make collected-state scanning obvious on the cards themselves.

**Independent Test**: Compare owned and unowned cards for the same species family and verify card styling/badges clearly communicate exact-form ownership.

### Tests for User Story 4

- [ ] T028 [P] [US4] Add frontend rendering tests or focused assertions for owned badge and dimmed missing-state card styles
- [ ] T029 [P] [US4] Add tests that base and shiny cards can show different collected states simultaneously

### Implementation for User Story 4

- [ ] T030 [US4] Refine pokedex mini-card component styling for owned badge, missing-state dimming, and readable id/name layout
- [ ] T031 [US4] Ensure owned-state badges remain consistent across filters, search results, and pagination boundaries

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final UX, regression coverage, and rollout notes.

- [ ] T032 [P] Review pokedex copy, labels, and badge wording for consistency with collection/profile/market surfaces
- [ ] T033 [P] Verify no regressions in profile summary, collection filters, market buy-request flow, or pokemon detail routes after pokedex routes land
- [ ] T034 [P] Run focused verification for backend tests, Mini App lint/build, and touched integration suites

## Dependencies & Execution Order

- Phase 1 -> Phase 2 -> User Stories -> Phase 7
- User Story 1 depends on Phase 2
- User Story 2 depends on User Story 1 foundation routes/models
- User Story 3 depends on Phase 2 and should reuse market precheck helpers, but can be built after User Story 1
- User Story 4 depends on User Story 1 card rendering

## Implementation Strategy

### MVP First

1. Finish Setup + Foundational
2. Deliver User Story 1 so profile can open pokedex and browse entries
3. Deliver User Story 2 so the list remains usable at scale
4. Deliver User Story 3 so the screen is actionable via buy request

### Incremental Rollout

1. Backend list/detail payloads behind Mini App routes
2. Profile entrypoint and initial browse UI
3. Filters/search/pagination stabilization
4. Detail plus buy-request prechecks
5. Final card polish and regression pass

## Notes

- Keep this feature Mini App-only for the first release.
- Reuse existing collection and market conventions wherever possible instead of inventing separate pokedex-only models.
- Avoid exposing internal `pokemon_catalog.id` ordering semantics when form display ids already exist.
