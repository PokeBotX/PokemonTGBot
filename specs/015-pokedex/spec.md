# Feature Specification: Pokedex

**Feature Branch**: `015-pokedex`  
**Created**: 2026-05-12  
**Status**: Draft  
**Input**: User description: "нужно сделать покедекс, в профиле есть кнопка всего форм: N, надо сделать чтобы по этой кнопке открывался покедекс, в нём прям на самих мини карточках должно быть показано есть ли этот вид покемона у тебя или нет"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open a full-form pokedex from the profile (Priority: P1)

As a player, I want the `Всего форм: N` control in the Mini App profile to open a full pokedex, so I can browse the entire known catalog and see which exact forms I own.

**Why this priority**: This is the main entrypoint and the core player-facing reason to build the feature at all.

**Independent Test**: Open the Mini App profile, tap `Всего форм: N`, and verify that a paginated pokedex view opens with visible cards for owned and unowned forms.

**Acceptance Scenarios**:

1. **Given** a player opens the Mini App profile, **When** they tap `Всего форм: N`, **Then** the Mini App opens a pokedex screen rather than staying on the profile screen.
2. **Given** the pokedex is opened, **When** the first page loads, **Then** it shows catalog cards for all known pokemon forms, including base forms and alternate forms.
3. **Given** a form is not owned, **When** its card is rendered, **Then** the card remains visible but visually dimmed and marked as not collected.
4. **Given** a form is owned, **When** its card is rendered, **Then** the card shows an owned badge and is not dimmed like an unowned entry.

---

### User Story 2 - Filter, search, and sort the pokedex without losing form detail (Priority: P1)

As a player, I want the pokedex to support collection-style filtering and search, so I can quickly find a specific species or form and inspect collected versus missing entries.

**Why this priority**: A full-form pokedex becomes noisy without search and filters, especially after forms were introduced.

**Independent Test**: Apply collection-style filters, search by id and by name, and confirm the results remain paginated and sorted by base dex id first, then form order.

**Acceptance Scenarios**:

1. **Given** the pokedex is open, **When** the player uses rarity and type filters already familiar from collection, **Then** the list narrows accordingly without exposing the duplicates filter.
2. **Given** the pokedex is open, **When** the player filters by collected or not collected, **Then** only matching cards remain visible.
3. **Given** the pokedex is open, **When** the player filters by `Shiny`, `Mega`, or `Gigantamax`, **Then** only matching form kinds remain visible.
4. **Given** the player searches by base dex id, form dex id, or name, **When** matching entries exist, **Then** matching cards are returned in a stable paginated order.
5. **Given** a mixed catalog of base and alternate forms, **When** cards are sorted, **Then** base dex ids appear in order first and their related forms follow in their natural form order rather than by internal row id.

---

### User Story 3 - Inspect a pokedex entry and optionally create a buy request (Priority: P1)

As a player, I want to open a read-only pokedex detail page for a catalog entry, so I can inspect its stats and related forms and optionally place a buy request if I want that form.

**Why this priority**: The pokedex is much more useful if each card can expand into an inspectable entry instead of being just a checklist.

**Independent Test**: Open an owned and an unowned pokedex entry, verify the detail page is read-only, confirm it can show related forms, and verify the buy-request CTA performs the same slot and currency prechecks as the market.

**Acceptance Scenarios**:

1. **Given** the player taps a pokedex card, **When** the detail page opens, **Then** it shows pokemon stats and descriptive catalog data but does not expose collection-instance actions like sell, release, favorite toggle, or instance switching.
2. **Given** the opened entry belongs to a species that has other forms in the catalog, **When** the detail page renders, **Then** it clearly states which related forms exist, such as shiny, mega, or gigantamax.
3. **Given** the detail page is open, **When** the player taps the single buy-request action, **Then** the app first checks request-slot availability and current currency before opening the request flow.
4. **Given** the player lacks enough currency or free request capacity, **When** they tap the buy-request action, **Then** the UI shows an immediate validation error instead of opening a broken confirmation flow.

---

### User Story 4 - Understand collected state on each mini card at a glance (Priority: P2)

As a player, I want the mini cards themselves to communicate whether I own that exact form, so I can scan progress quickly without opening every detail page.

**Why this priority**: This is the UX payoff of the feature and keeps the pokedex useful as a collection tracker.

**Independent Test**: Compare owned and unowned cards across the same species family and verify that base, shiny, mega, and gigantamax ownership are tracked independently.

**Acceptance Scenarios**:

1. **Given** the player owns the base form but not the shiny form, **When** both cards are shown, **Then** only the base card appears as collected.
2. **Given** the player owns the shiny form but not the base form, **When** both cards are shown, **Then** only the shiny card appears as collected.
3. **Given** the same species has multiple forms, **When** the list is scanned, **Then** each form has its own `есть / нет` state rather than inheriting ownership from related forms.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Mini App profile control labeled `Всего форм: N` MUST open a dedicated pokedex screen.
- **FR-002**: The pokedex MUST be built from the full `pokemon_catalog`, including base forms and alternate forms such as shiny, mega, and gigantamax.
- **FR-003**: Each pokedex card MUST represent one exact catalog entry, not a grouped species bucket.
- **FR-004**: A pokedex card MUST show the entry id, visible name, and whether that exact form is collected.
- **FR-005**: Unowned pokedex cards MUST remain visible and MUST appear visually dimmed relative to owned entries.
- **FR-006**: Owned-state tracking in the pokedex MUST be exact-form-aware: owning a base form MUST NOT automatically mark shiny, mega, or gigantamax as collected, and vice versa.
- **FR-007**: The pokedex MUST support the same main collection filters for rarity and type, excluding the duplicates filter.
- **FR-008**: The pokedex MUST add filters for `collected`, `not collected`, `shiny`, `mega`, and `gigantamax`.
- **FR-009**: The pokedex MUST support search by visible pokemon name, base dex id, and form-aware display id.
- **FR-010**: The pokedex MUST paginate results using the same overall interaction pattern as the Mini App collection.
- **FR-011**: The pokedex MUST sort entries by base dex id first, then by form order within that base sequence.
- **FR-012**: Tapping a pokedex card MUST open a read-only pokedex detail page for that catalog entry.
- **FR-013**: The pokedex detail page MUST show pokemon stats and catalog-level descriptive data but MUST NOT show collection-instance actions such as favorite toggle, release, sell, or instance switching.
- **FR-014**: The pokedex detail page MUST show whether related forms exist for the same base species when such forms are present in the catalog.
- **FR-015**: The pokedex detail page MUST expose exactly one market action: create buy request.
- **FR-016**: Before opening the buy-request confirmation flow from pokedex detail, the Mini App MUST precheck both request-slot availability and current currency balance.
- **FR-017**: If the buy-request precheck fails, the pokedex detail page MUST show an immediate error and MUST NOT advance into a broken or incomplete flow.
- **FR-018**: Pokedex cards and detail payloads MUST use the user-visible dex/form identifiers and MUST NOT expose internal row-id ordering artifacts such as `10xxx` surrogate ids as sort keys.
- **FR-019**: The Mini App MUST preserve the player’s current pokedex filter, search, and pagination context when they enter and return from pokedex detail, unless they explicitly reset it.
- **FR-020**: The pokedex feature MUST be implemented in Mini App surfaces first; no Telegram bot pokedex flow is required for this slice.

### Key Entities

- **PokedexEntry**: One visible catalog entry for a base or alternate form, including visible id, name, rarity, types, image, and owned-state badge.
- **PokedexQuery**: The current client/server query state for search text, filters, page cursor, and sort order.
- **PokedexDetail**: A read-only catalog detail payload that includes stats, related-form hints, and buy-request precheck metadata.
- **CollectedStateBadge**: A compact owned/not-owned indicator bound to one exact form entry.
- **BuyRequestPrecheck**: The validation result indicating whether the player has enough currency and free request capacity to open the buy-request flow from pokedex detail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A player can open the pokedex from the Mini App profile in one tap from `Всего форм: N`.
- **SC-002**: In manual verification, owned versus unowned states remain correct for mixed-form species where the player owns only some forms.
- **SC-003**: Search by name and by id returns relevant results within the same pagination model already used by collection.
- **SC-004**: Pokedex detail can open for both owned and unowned entries without requiring a concrete `user_pokemon` instance.
- **SC-005**: Buy-request precheck failures from pokedex detail are surfaced immediately and do not advance the player into an invalid confirmation flow.

## Decisions Locked

- The pokedex is a full-form catalog, not a base-species-only view.
- Base, shiny, mega, and gigantamax ownership are tracked independently on cards.
- Unowned entries stay visible but dimmed rather than hidden or replaced with question marks.
- Pokedex detail is read-only and collection-instance-agnostic.
- The only action on pokedex detail is buy request, with prechecks baked in.

## Implementation Assumptions

- Existing collection filters, natural form sorting helpers, and Mini App market precheck flows will be reused where possible instead of reimplemented from scratch.
- Related-form hints on detail can be text-first in the first release and do not require a dedicated horizontal carousel unless implementation is already cheap.
