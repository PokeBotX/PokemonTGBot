# Implementation Plan: Pokedex

## Goal

Add a Mini App pokedex that opens from the profile `Всего форм: N` control, shows the full form-aware catalog with owned-state badges, and supports read-only detail plus buy-request entry with market-style prechecks.

## Scope

- Mini App profile entrypoint into pokedex
- Form-aware pokedex list API and UI
- Collection-style filters plus collected/not-collected and form-kind filters
- Search by id and name
- Paged browsing with stable base-first form ordering
- Read-only pokedex detail page
- Buy-request CTA from detail with slot/currency prechecks

## Non-Goals

- Telegram bot pokedex UI
- Collection-instance actions from pokedex detail
- New market economics or request-limit rules
- Species grouping or alternate grouped pokedex modes

## Delivery Slices

### Slice 1 - Pokedex foundation

- Add backend query helpers and response models for form-aware pokedex browsing
- Add Mini App route opened from profile
- Render cards with owned/not-owned badges and dimmed missing entries

### Slice 2 - Filters, search, and pagination

- Reuse collection-style filtering patterns
- Add collected/not-collected and form-kind filters
- Add name/id search and preserve list context across navigation

### Slice 3 - Detail and buy-request prechecks

- Add read-only pokedex detail payload and page
- Show related-form hints
- Wire buy-request CTA with immediate request-slot and currency prechecks

## Risks

- Confusing sort semantics if form display ids and internal ids leak into ordering
- Context loss if detail navigation does not round-trip list filters/search cleanly
- UI duplication if pokedex detail diverges too far from existing market/catalog detail surfaces

## Verification

- Focused backend tests for pokedex aggregation, search, filters, sorting, and ownership badges
- Frontend lint/build
- Manual Mini App walkthrough:
  - profile -> pokedex
  - filters/search/pagination
  - owned/unowned states
  - detail page
  - buy-request precheck success/failure
