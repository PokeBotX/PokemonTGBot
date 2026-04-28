# Tasks: Admin Bot

**Input**: Design documents from `/specs/010-admin-bot/`  
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for superadmin access control, private-chat enforcement, confirmation gating, grants, pokemon creation, image uploads, and audit recording.

**Organization**: Tasks are grouped by user story so we can ship a safe admin foundation first, then layer privileged operations on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US5`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare docs and test scaffolding for the admin-bot work

- [x] T001 Create dedicated admin-bot test modules in [tests/unit/test_admin_access.py](/home/deck/Desktop/pokemonbot/tests/unit/test_admin_access.py), [tests/unit/test_admin_actions.py](/home/deck/Desktop/pokemonbot/tests/unit/test_admin_actions.py), [tests/unit/test_admin_images.py](/home/deck/Desktop/pokemonbot/tests/unit/test_admin_images.py), and [tests/integration/test_admin_bot_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_admin_bot_flow.py)
- [x] T002 Add auxiliary docs if needed (`data-model.md`, `quickstart.md`) under [specs/010-admin-bot](/home/deck/Desktop/pokemonbot/specs/010-admin-bot)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Entry points, access control, pending confirmations, and audit foundations shared by all admin operations

**⚠️ CRITICAL**: No user story work should begin until this phase is complete

- [x] T003 [P] Add dedicated admin entrypoints such as [main_admin.py](/home/deck/Desktop/pokemonbot/main_admin.py) and [main_admin_local.py](/home/deck/Desktop/pokemonbot/main_admin_local.py)
- [x] T004 [P] Add env parsing for `ADMIN_BOT_TOKEN` and `ADMIN_BOT_ALLOWED_IDS`
- [x] T005 [P] Create admin-only handler/module structure under [bot/admin](/home/deck/Desktop/pokemonbot/bot/admin)
- [x] T006 [P] Add a private-chat-only access guard and superadmin allowlist enforcement
- [x] T007 [P] Add a reusable pending-action confirmation framework for privileged mutations
- [x] T008 [P] Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with an audit table for admin actions
- [x] T009 [P] Add DB/service helpers for writing admin audit records
- [x] T010 Add structured logs for admin access checks, pending-action creation, confirmation, cancellation, mutation success, and mutation failure

**Checkpoint**: The admin bot can start safely, reject unauthorized users, and stage confirmable actions with audit support

---

## Phase 3: User Story 1 - Restrict admin bot access to superadmins (Priority: P1)

**Goal**: Only env-listed superadmins can use the admin bot, and only in private chats

**Independent Test**: Allowed user in private chat gets the admin menu; disallowed user or non-private chat gets rejected

### Tests for User Story 1

- [x] T011 [P] [US1] Add unit tests for allowlist parsing, private-chat enforcement, and unauthorized-user rejection
- [x] T012 [P] [US1] Add integration tests for first-contact admin menu access and blocked access scenarios

### Implementation for User Story 1

- [x] T013 [US1] Implement admin access guard middleware/helpers
- [x] T014 [US1] Implement the root admin menu and private-chat-only welcome flow
- [x] T015 [US1] Return explicit user-facing errors for unauthorized access and wrong chat type

**Checkpoint**: The admin bot is safely reachable only by valid superadmins

---

## Phase 4: User Story 2 - Execute currency and pokemon grants safely (Priority: P1)

**Goal**: Superadmins can grant currency and pokemon through confirmable Telegram flows

**Independent Test**: Start a grant flow by `@username`, confirm it, and verify DB changes plus audit entries

### Tests for User Story 2

- [x] T016 [P] [US2] Add unit tests for target-user lookup, pokemon lookup, validation failures, and confirmation gating
- [x] T017 [P] [US2] Add integration tests for successful currency grant and pokemon grant flows

### Implementation for User Story 2

- [x] T018 [US2] Implement button-driven currency grant flow with `@username`, currency choice, amount input/state, and confirmation
- [x] T019 [US2] Implement button-driven pokemon grant flow with `@username`, `pokemon_id`, and confirmation
- [x] T020 [US2] Add privileged DB/service methods for currency and pokemon grants
- [x] T021 [US2] Audit both successful and failed grant operations

**Checkpoint**: Core support/admin grant actions work safely

---

## Phase 5: User Story 3 - Create a new pokemon species from the admin bot (Priority: P1)

**Goal**: Superadmins can create a full pokemon catalog entry with all required fields and confirmation

**Independent Test**: Fill the full pokemon draft, confirm it, and verify that the species exists in `pokemon_catalog`

### Tests for User Story 3

- [x] T022 [P] [US3] Add unit tests for pokemon draft validation, duplicate-id rejection, and confirmation behavior
- [x] T023 [P] [US3] Add integration tests for successful pokemon creation and cancellation before confirmation

### Implementation for User Story 3

- [x] T024 [US3] Implement button/state flow for collecting the full pokemon payload
- [x] T025 [US3] Add privileged DB/service method for transactional pokemon creation
- [x] T026 [US3] Add confirmation preview and final result message for new pokemon creation
- [x] T027 [US3] Audit successful and failed pokemon creation attempts

**Checkpoint**: The admin bot can manage the pokemon catalog without manual SQL

---

## Phase 6: User Story 4 - Upload and manage pokemon images through Telegram (Priority: P1)

**Goal**: Superadmins can upload images from Telegram, store them in MinIO, and manage pokemon image variants plus source/order/default metadata

**Independent Test**: Upload a photo/document, attach it to a species, confirm, and verify the new image variant plus editable metadata

### Tests for User Story 4

- [x] T028 [P] [US4] Add unit tests for Telegram image intake, MinIO upload metadata handling, variant mapping validation, and source/order/default updates
- [x] T029 [P] [US4] Add integration tests for upload-confirm-attach flow and source/order/default edit flows

### Implementation for User Story 4

- [x] T030 [US4] Implement Telegram photo/document intake in the admin bot
- [x] T031 [US4] Add service helpers for uploading accepted images into MinIO and creating `image_credits`
- [x] T032 [US4] Implement attach-image-to-species flow using `pokemon_image_variants`
- [x] T033 [US4] Implement edit flow for `image_credits.source`
- [x] T034 [US4] Implement edit flow for `display_order` and `is_default` on image variants
- [x] T035 [US4] Add confirmation previews and audit records for all image-management mutations

**Checkpoint**: Admins can manage the pokemon image pipeline end-to-end from Telegram

---

## Phase 7: User Story 5 - Confirm and audit every admin mutation (Priority: P1)

**Goal**: Every mutating action is previewed, confirmed or canceled, and permanently auditable

**Independent Test**: Trigger each operation type, confirm and cancel at least one path, and verify audit trail coverage

### Tests for User Story 5

- [x] T036 [P] [US5] Add unit tests for pending-action expiry/cancel semantics and audit payload formation
- [x] T037 [P] [US5] Add integration tests for confirmation/cancel flows across grants, pokemon creation, and image management

### Implementation for User Story 5

- [x] T038 [US5] Standardize shared confirmation and cancel screens across all admin mutations
- [x] T039 [US5] Ensure pending actions expire or clear safely without executing unintended mutations
- [x] T040 [US5] Persist rich audit records for actor, target, action type, input payload, result status, and timestamps
- [x] T041 [US5] Add user-facing summaries after confirmed operations and after rejected/canceled operations

**Checkpoint**: Admin operations are safe, explicit, and traceable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Tighten UX, operational safety, and deployment clarity

- [x] T042 [P] Review admin menu wording and dangerous-action copy for clarity and safety
- [x] T043 [P] Add rollout notes for env setup (`ADMIN_BOT_TOKEN`, `ADMIN_BOT_ALLOWED_IDS`) and deployment usage
- [x] T044 [P] Verify that privileged DB and MinIO operations share the correct production credentials and do not drift from the public bot
- [x] T045 Run focused verification with `uv run pytest tests/unit/test_admin_access.py tests/unit/test_admin_actions.py tests/unit/test_admin_images.py tests/integration/test_admin_bot_flow.py -v`

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-7**: Depend on Phase 2
- **Phase 8**: Depends on completion of all desired stories

### User Story Dependencies

- **US1**: Starts immediately after foundational work
- **US2**: Depends on US1 because access control and pending actions must already exist
- **US3**: Depends on the same foundation and can progress in parallel with US2 after Phase 2
- **US4**: Depends on the same foundation plus shared MinIO/DB service wiring
- **US5**: Depends on foundational pending-action and audit infrastructure, then tightens all mutation flows

### Parallel Opportunities

- T003, T004, T005, T006, T008, and T009 can run in parallel after structure direction is locked
- T016 and T017 can run in parallel for grant-flow coverage
- T022 and T023 can run in parallel for pokemon creation coverage
- T028 and T029 can run in parallel for image-management coverage

## Implementation Strategy

### MVP First

1. Complete Phases 1-2  
2. Ship private-chat superadmin access plus root admin menu  
3. Ship currency and pokemon grants with confirmation and audit  
4. Ship pokemon creation flow  
5. Ship image upload and image-management flows  
6. Tighten cross-cutting confirmation/audit behavior and docs

### Incremental Delivery

1. Foundation: admin bot startup, allowlist, pending actions, audit table  
2. Grants slice: currency and pokemon issuance  
3. Catalog slice: new pokemon creation  
4. Image slice: upload, attach, source edit, order/default management  
5. Cross-cutting slice: confirmation polish, cancellation safety, audit verification

## Notes

- Keep the first release intentionally conservative: one role, private chat only, explicit confirmation everywhere.
- Prefer service-layer reuse so future admin features inherit audit and confirmation patterns instead of re-implementing them.
- Treat image-management as a first-class part of the admin bot, not as a later add-on, because the public product now relies on image variants.
