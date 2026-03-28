# Tasks: Market System

**Input**: Design documents from `/specs/006-market-system/`  
**Prerequisites**: plan.md, spec.md

**Tests**: Critical-path tests are required for shared pokemon-card rendering, listing creation, commission debit, auto-removal, request reservation, purchase/fulfillment atomicity, slot limits, and market browse filtering.

**Organization**: Tasks are grouped by user story so each slice can be implemented and validated independently after the foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Story mapping from `spec.md` (`US1`..`US6`)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the market feature docs and focused test scaffolding

- [x] T001 Create feature support docs for `/specs/006-market-system/` in [data-model.md](/home/deck/Desktop/pokemonbot/specs/006-market-system/data-model.md) and [quickstart.md](/home/deck/Desktop/pokemonbot/specs/006-market-system/quickstart.md)
- [x] T002 [P] Create dedicated market test modules in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) and [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared card layer, schema, DTOs, and core transactional helpers required by all market stories

**⚠️ CRITICAL**: No user story work should begin until this phase is complete

- [x] T003 [P] Extend [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) with sale-listing, buy-request, reserved-fund, status, commission, and expiry fields/tables needed by the market
- [x] T004 [P] Introduce a shared non-shop pokemon-card helper module (for example [pokemon_cards.py](/home/deck/Desktop/pokemonbot/bot/ui/pokemon_cards.py)) and move reusable card caption/image logic out of [profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py), [collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py), and [chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py) while keeping shop-specific rendering separate
- [x] T005 [P] Add market DTOs and read models to [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for listing summaries, buy-request summaries, browse filters, my listings, and my requests
- [x] T006 [P] Add core transactional market methods to [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) for listing creation/removal, purchase completion, request creation/cancellation, request fulfillment, and reserved-fund handling
- [x] T007 [P] Add route names, callback-id conventions, and pending-input action ids in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) for root, buy, sell, my listings, my requests, filter toggles, sort toggles, confirmation screens, and cancellation/removal actions
- [x] T008 Add structured logs for listing create/remove, commission debit, listing expiry, purchase success/failure, request create/cancel, request fulfillment, and card-entry branching in [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)
- [x] T009 Write foundational unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for slot limits, reserved-fund math, commission math, and card-action branching rules

**Checkpoint**: Shared card rendering, schema, DTOs, and atomic market methods are ready for user-story work

---

## Phase 3: User Story 2A - Start market flow from a pokemon card (Priority: P1) 🎯 MVP Entry

**Goal**: A shared pokemon card can open the market flow and branch into sell or buy-request behavior based on ownership

**Independent Test**: Open a pokemon card with a `Рынок` button; when the user owns the pokemon it opens the sale flow, otherwise it opens buy-request creation flow

### Tests for User Story 2A

- [x] T010 [P] [US2A] Add unit coverage in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for card action branching and market button rendering
- [x] T011 [P] [US2A] Add integration coverage in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for market entry from collection/profile/search cards

### Implementation for User Story 2A

- [x] T012 [US2A] Add a reusable `Рынок` button to the shared pokemon-card layer in [pokemon_cards.py](/home/deck/Desktop/pokemonbot/bot/ui/pokemon_cards.py)
- [x] T013 [US2A] Wire market-card entry callbacks in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) so owned pokemon branch to sale flow and non-owned pokemon branch to buy-request flow
- [x] T014 [US2A] Reuse the shared card layer from [profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py), [collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py), and [chat_encounters.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/chat_encounters.py)

**Checkpoint**: Market entry is available directly from pokemon cards before deeper market UI is built

---

## Phase 4: User Story 1 - Browse active sale listings and buy pokemon (Priority: P1)

**Goal**: Users can open the market, view active listings from other users, and buy a concrete pokemon instance for `pokecoin`

**Independent Test**: Open `Рынок -> Купить`, browse active listings, and purchase one listing successfully

### Tests for User Story 1

- [x] T015 [P] [US1] Add unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for listing visibility rules and self-buy rejection
- [x] T016 [P] [US1] Add integration tests in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for opening the buy screen and completing a purchase

### Implementation for User Story 1

- [x] T017 [US1] Replace the market placeholder in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) with a real market root screen
- [x] T018 [US1] Implement the `Купить` browse screen in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) using paginated SQL-backed listing queries from [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [x] T019 [US1] Implement purchase confirmation and atomic buy completion in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) and [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)

**Checkpoint**: Users can browse and buy active listings

---

## Phase 5: User Story 2 - Filter market listings while buying (Priority: P1)

**Goal**: Users can filter and sort active listings while buying

**Independent Test**: Toggle rarity, affordability, and sort mode in `Купить` and verify the list changes correctly

### Tests for User Story 2

- [x] T020 [P] [US2] Add unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for filter-state serialization and sort selection
- [x] T021 [P] [US2] Add integration tests in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for rarity filter, `только хватает`, and `сначала дешёвые`

### Implementation for User Story 2

- [x] T022 [US2] Add market buy-filter state and session persistence in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)
- [x] T023 [US2] Add SQL-side rarity filtering, affordability filtering, and sort modes in [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [x] T024 [US2] Render compact filter/sort controls in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)

**Checkpoint**: Buy-side market browsing remains usable as listings grow

---

## Phase 6: User Story 3 - Create and maintain sale listings (Priority: P1)

**Goal**: Users can create sale listings for owned unlocked pokemon, see `Мои лоты`, and remove listings manually

**Independent Test**: Create a listing from card flow, see it in `Мои лоты`, and remove it successfully

### Tests for User Story 3

- [x] T025 [P] [US3] Add unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for sale-slot enforcement, locked-pokemon rejection, and initial commission debit
- [x] T026 [P] [US3] Add integration tests in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for listing creation, listing confirmation, `Мои лоты`, and manual removal

### Implementation for User Story 3

- [x] T027 [US3] Implement sale price pending-input flow and dedicated sale-price command handling in [commands.py](/home/deck/Desktop/pokemonbot/bot/handlers/commands.py) and [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)
- [x] T028 [US3] Implement sale confirmation screen with compact commission/balance summary in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)
- [x] T029 [US3] Persist sale listings and initial commission debit in [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [x] T030 [US3] Implement `Мои лоты` screen and manual listing removal in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)

**Checkpoint**: Selling owned pokemon works end-to-end

---

## Phase 7: User Story 4 - Keep listing commission and auto-remove unpaid listings (Priority: P1)

**Goal**: Daily listing commission and 5-day expiry are enforced automatically

**Independent Test**: Simulate the next billing day and listing expiry; verify commission debit, auto-removal on insufficient funds, and pokemon return

### Tests for User Story 4

- [x] T031 [P] [US4] Add unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for commission amount, first-day debit, auto-removal, and 5-day expiry
- [x] T032 [P] [US4] Add integration tests in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for unpaid-listing removal and expiry behavior

### Implementation for User Story 4

- [x] T033 [US4] Add daily commission and expiry processing methods in [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [x] T034 [US4] Add scheduling or startup-safe periodic processing hooks in [main.py](/home/deck/Desktop/pokemonbot/main.py) and [main_local.py](/home/deck/Desktop/pokemonbot/main_local.py)
- [x] T035 [US4] Show remaining listing lifetime in days in `Мои лоты` rendering inside [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)

**Checkpoint**: Listing lifecycle rules are enforced automatically

---

## Phase 8: User Story 5 - Sell to existing buy requests (Priority: P2)

**Goal**: Users can open `Продать`, see only fulfillable foreign buy requests, and complete a sale into a request

**Independent Test**: Create a buy request from one user, open `Продать` from another eligible user, and fulfill the request

### Tests for User Story 5

- [x] T036 [P] [US5] Add unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for fulfillable-request filtering and self-request rejection
- [x] T037 [P] [US5] Add integration tests in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for `Продать` and successful request fulfillment

### Implementation for User Story 5

- [x] T038 [US5] Implement `Продать` browse screen in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) using fulfillable-request queries from [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [x] T039 [US5] Implement request-fulfillment confirmation and atomic transfer in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) and [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)

**Checkpoint**: Users can sell directly into existing demand

---

## Phase 9: User Story 6 - Create and keep buy requests (Priority: P2)

**Goal**: Users can create, view, and cancel buy requests with immediate fund reservation

**Independent Test**: Create a buy request from a card flow, verify fund reservation, open `Мои заявки`, and cancel the request with fund return

### Tests for User Story 6

- [x] T040 [P] [US6] Add unit tests in [tests/unit/test_market.py](/home/deck/Desktop/pokemonbot/tests/unit/test_market.py) for buy-request slot limit, fund reservation, and fund return on cancel
- [x] T041 [P] [US6] Add integration tests in [tests/integration/test_market_flow.py](/home/deck/Desktop/pokemonbot/tests/integration/test_market_flow.py) for request creation, `Мои заявки`, and manual cancellation

### Implementation for User Story 6

- [x] T042 [US6] Implement buy-request price pending-input flow and dedicated buy-price command handling in [commands.py](/home/deck/Desktop/pokemonbot/bot/handlers/commands.py) and [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)
- [x] T043 [US6] Implement buy-request confirmation and immediate fund reservation in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py) and [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py)
- [x] T044 [US6] Implement `Мои заявки` screen and manual request cancellation in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)

**Checkpoint**: Buy requests are fully manageable and economically safe

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Tighten UX, docs, and final verification across market flows

- [ ] T045 [P] Update docs for market, card-market entry, listing commission, and price-entry commands in [README.md](/home/deck/Desktop/pokemonbot/README.md)
- [x] T046 [P] Review and tighten market message length, button density, and confirmation clarity in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py)
- [x] T047 Run targeted verification with `uv run pytest tests/unit/test_market.py tests/integration/test_market_flow.py tests/integration/test_handlers.py tests/integration/test_navigation.py -v` and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies
- **Phase 2**: Depends on Phase 1 and blocks all story work
- **Phases 3-9**: Depend on Phase 2; card-entry work should land first because the user-facing market UX is anchored on pokemon cards
- **Phase 10**: Depends on completion of all desired stories

### User Story Dependencies

- **US2A**: Starts immediately after foundational work because card-driven entry shapes the rest of the market UX
- **US1**: Depends on foundational database and market root infrastructure
- **US2**: Depends on US1 browse flow
- **US3**: Depends on US2A card entry and foundational market transactions
- **US4**: Depends on US3 listing creation
- **US5**: Depends on US6 request creation plus foundational transactions
- **US6**: Depends on foundational reservation and slot logic; should land before US5 is considered complete

### Parallel Opportunities

- T003, T004, T005, and T007 can run in parallel after schema direction is settled
- T010 and T011 can run in parallel for the card-entry story
- T015 and T016 can run in parallel for buy flow
- T020 and T021 can run in parallel for filters
- T025 and T026 can run in parallel for sale-listing flow
- T031 and T032 can run in parallel for commission lifecycle
- T036 and T037 can run in parallel for request-fulfillment flow
- T040 and T041 can run in parallel for buy-request management

## Implementation Strategy

### MVP First

1. Complete Phases 1-2
2. Deliver shared card layer plus market-card entry
3. Deliver buy-side browse and purchase flow
4. Deliver sell-side listing creation and my listings
5. Deliver commission and expiry automation
6. Deliver buy requests and fulfillable `Продать`
7. Validate and polish

### Incremental Delivery

1. Foundation: schema, shared card renderer, DTOs, atomic DB helpers
2. Card-entry slice: `Рынок` button and sell-vs-request branching
3. Buy slice: browse, filters, purchase
4. Sell slice: create listing, confirm, my listings
5. Lifecycle slice: commission and expiry automation
6. Request slice: create request, my requests, fulfill from `Продать`
7. Final polish and verification

## Notes

- Keep market browse queries SQL-first and paginated.
- Treat reserved request funds and active listing ownership as hard invariants.
- Reuse shared card rendering outside shop to avoid a fifth separate pokemon-card format.
- Keep market price-entry commands short and explicit, with separate command names for selling and buying.
