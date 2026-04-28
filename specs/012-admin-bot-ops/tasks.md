# Tasks: Admin Bot Operations

**Input**: Design documents from `/specs/012-admin-bot-ops/`  
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for audit browse/export, pokemon-species point edits, broadcast preview/confirm, and partial failure reporting.

**Organization**: Tasks are grouped by user story so we can ship audit visibility first, then catalog edits, then controlled broadcast support.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US4`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare docs and tests for the new admin-bot operational slice

- [ ] T001 Create or extend focused admin-bot test coverage in [tests/unit/test_admin_actions.py](/home/deck/Desktop/pokemonbot/tests/unit/test_admin_actions.py) and [tests/integration/test_admin_bot_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_admin_bot_flow.py) for audit browse/export, species edits, and broadcasts
- [ ] T002 Add auxiliary docs if needed (`data-model.md`, `quickstart.md`, `rollout-notes.md`) under [specs/012-admin-bot-ops](/home/deck/Desktop/pokemonbot/specs/012-admin-bot-ops)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared DB/service helpers and routing hooks for the new admin-bot operations

**⚠️ CRITICAL**: No user story work should begin until this phase is complete

- [ ] T003 [P] Add privileged DB helpers for recent audit fetch/export payloads in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T004 [P] Add privileged DB helpers for point-editing `pokemon_catalog` fields in [bot/db/database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [ ] T005 [P] Add privileged DB/service helpers for resolving eligible broadcast target chats and summarizing broadcast outcomes
- [ ] T006 Extend [bot/admin/ui.py](/home/deck/Desktop/pokemonbot/bot/admin/ui.py) and [bot/admin/handlers.py](/home/deck/Desktop/pokemonbot/bot/admin/handlers.py) with new root/menu entry points for `Аудит`, `Редактировать покемона`, and `Рассылка`
- [ ] T007 Ensure all new mutating flows reuse the existing pending-action confirmation and audit framework from feature `010-admin-bot`

**Checkpoint**: The admin bot can route into the new sections and has service-layer primitives to support them safely

---

## Phase 3: User Story 1 - View and export admin audit records (Priority: P1)

**Goal**: Superadmins can inspect recent admin actions and export a bounded audit snapshot without direct DB access

**Independent Test**: Open audit, see recent records, trigger export, and verify readable output

### Tests for User Story 1

- [ ] T008 [P] [US1] Add unit tests for audit fetch bounds, export payload formatting, and empty-state behavior
- [ ] T009 [P] [US1] Add integration tests for audit browse and audit export flows through the admin bot

### Implementation for User Story 1

- [ ] T010 [US1] Implement audit section screen with recent records preview in [bot/admin/handlers.py](/home/deck/Desktop/pokemonbot/bot/admin/handlers.py)
- [ ] T011 [US1] Implement bounded audit export flow and Telegram delivery from the admin bot
- [ ] T012 [US1] Add user-facing empty state and concise audit formatting in [bot/admin/ui.py](/home/deck/Desktop/pokemonbot/bot/admin/ui.py)

**Checkpoint**: Operators can inspect and export recent audit data from the bot

---

## Phase 4: User Story 2 - Edit an existing pokemon species safely (Priority: P1)

**Goal**: Superadmins can point-edit catalog fields for an existing pokemon species through a confirmable Telegram flow

**Independent Test**: Choose `pokemon_id`, select a supported field, enter a new value, confirm, and verify the changed row in `pokemon_catalog`

### Tests for User Story 2

- [ ] T013 [P] [US2] Add unit tests for species lookup, field validation, and point-edit confirmation payloads
- [ ] T014 [P] [US2] Add integration tests for successful species edit, invalid input rejection, and cancel behavior

### Implementation for User Story 2

- [ ] T015 [US2] Implement species-edit start flow by `pokemon_id`
- [ ] T016 [US2] Implement field-selection UI and field-specific input prompts
- [ ] T017 [US2] Implement privileged DB mutation helpers for supported `pokemon_catalog` field edits
- [ ] T018 [US2] Add confirmation preview and result messaging for species edits
- [ ] T019 [US2] Audit successful, canceled, and failed species-edit operations

**Checkpoint**: Catalog rows can be safely corrected without manual SQL

---

## Phase 5: User Story 3 - Broadcast a text message to eligible group chats (Priority: P1)

**Goal**: Superadmins can send a dry-run-confirmed text broadcast to group/supergroup chats where the main bot is currently present

**Independent Test**: Enter broadcast text, inspect preview count, confirm, and receive a success/failure summary

### Tests for User Story 3

- [ ] T020 [P] [US3] Add unit tests for target-chat filtering, preview count calculation, and summary payload formation
- [ ] T021 [P] [US3] Add integration tests for broadcast confirm, broadcast cancel, and partial-send-failure reporting

### Implementation for User Story 3

- [ ] T022 [US3] Implement text-only broadcast compose flow in [bot/admin/handlers.py](/home/deck/Desktop/pokemonbot/bot/admin/handlers.py)
- [ ] T023 [US3] Implement eligible group/supergroup target resolution for chats where the main bot is currently present
- [ ] T024 [US3] Implement dry-run preview with target count before confirmation
- [ ] T025 [US3] Implement confirmed broadcast send loop and operator summary output
- [ ] T026 [US3] Audit broadcast attempts, including partial failures and zero-target cases

**Checkpoint**: The admin bot can deliver controlled operational messages to eligible chats

---

## Phase 6: User Story 4 - Confirm and audit operational admin actions (Priority: P1)

**Goal**: All new admin operations continue to behave like the established safe admin-bot model

**Independent Test**: Trigger audit export, species edit, and broadcast flows; confirm and cancel them; verify consistent previews and audit records

### Tests for User Story 4

- [ ] T027 [P] [US4] Add unit tests for shared preview/cancel semantics on the new operational flows
- [ ] T028 [P] [US4] Add integration tests that confirm every new mutate flow writes the expected audit status transitions

### Implementation for User Story 4

- [ ] T029 [US4] Standardize preview, cancel, success, and failure copy for the new operations in [bot/admin/ui.py](/home/deck/Desktop/pokemonbot/bot/admin/ui.py)
- [ ] T030 [US4] Ensure new pending actions clear safely on cancel/expiry without mutating state
- [ ] T031 [US4] Extend structured logging for audit export, species edits, and broadcasts

**Checkpoint**: New operational actions feel native to the existing admin-bot safety model

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tighten copy, operational limits, and rollout clarity

- [ ] T032 [P] Review dangerous-action wording for species edits and broadcasts
- [ ] T033 [P] Add rollout and operator-usage notes under [specs/012-admin-bot-ops](/home/deck/Desktop/pokemonbot/specs/012-admin-bot-ops)
- [ ] T034 [P] Verify that broadcast targeting excludes private chats and uses only chats where the main bot is still present
- [ ] T035 Run focused verification with `uv run pytest tests/unit/test_admin_actions.py tests/integration/test_admin_bot_flow.py -v`

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-6**: Depend on Phase 2
- **Phase 7**: Depends on completion of all desired stories

### User Story Dependencies

- **US1**: Starts immediately after foundational work
- **US2**: Depends on foundational routing/helpers and the existing admin confirm framework
- **US3**: Depends on foundational routing/helpers and access to bot-presence chat resolution
- **US4**: Depends on all new flows existing so safety behavior can be verified consistently

### Parallel Opportunities

- T003, T004, and T005 can run in parallel once the DB/service shape is fixed
- T008 and T009 can run in parallel for audit coverage
- T013 and T014 can run in parallel for species-edit coverage
- T020 and T021 can run in parallel for broadcast coverage

## Implementation Strategy

### MVP First

1. Complete Phases 1-2  
2. Ship audit browse/export  
3. Ship point-edit species flow  
4. Ship dry-run-confirmed broadcast flow  
5. Tighten shared copy, logs, and rollout notes

### Incremental Delivery

1. Foundation: routing and DB/service helpers  
2. Audit slice: recent records + export  
3. Catalog edit slice: point edits for species fields  
4. Broadcast slice: text-only fanout to eligible chats  
5. Shared safety slice: previews, cancel semantics, and structured logs

## Notes

- Keep this slice conservative: no media broadcast, no instance-level pokemon editing, no arbitrary chat targeting.
- Reuse the already proven admin-bot confirmation and audit framework rather than inventing another operational flow pattern.
