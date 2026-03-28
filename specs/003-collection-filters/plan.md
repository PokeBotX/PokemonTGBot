# Implementation Plan: Collection Browsing and Filters

**Branch**: `003-collection-filters` | **Date**: 2026-03-16 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/003-collection-filters/spec.md)  
**Input**: Feature specification from `/specs/003-collection-filters/spec.md`

## Summary

Replace the current placeholder collection section with a real Telegram collection flow backed by PostgreSQL. The feature will aggregate owned pokemon at the species level, render a paginated collection view with 12 entries per page, provide a dedicated filter screen for rarity/type/duplicates, preserve filter state across callback navigation, and expose per-entry buttons that open pokemon card views. Implementation will extend the existing menu/session flow, add collection-specific read queries in the database layer, and keep Telegram messages concise and resilient to duplicate callbacks.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog, redis  
**Storage**: PostgreSQL for owned pokemon and collection queries; Redis-backed menu sessions when enabled, with in-memory fallback  
**Testing**: pytest, pytest-asyncio, pytest-mock  
**Target Platform**: Linux-hosted Telegram bot in polling and webhook modes  
**Project Type**: Telegram bot application with async handlers and PostgreSQL-backed state  
**Performance Goals**: Collection and filter callbacks should feel immediate in Telegram; a page render should complete in a single callback interaction without extra round trips  
**Constraints**: Must preserve Telegram callback/session safety checks, keep collection text readable in Telegram, retain active filters across page changes, avoid duplicate callback side effects, and work against the existing `user_pokemon` plus `pokemon_catalog` schema without introducing unnecessary new tables  
**Scale/Scope**: One new collection browsing flow, one filter-state model carried through navigation/session context, paginated read queries, and integration with future pokemon detail cards

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Telegram-first UX: Pass. The feature is entirely button-driven, keeps the collection as a compact Telegram message, and uses a separate filter screen instead of overloading one view.
- Consistency & ownership: Pass. The feature is read-heavy and uses existing ownership data; no ownership mutations are introduced, but duplicate-click protection and session validity still apply.
- Scope-driven delivery: Pass. Version 1 includes browsing, filters, duplicates-only, reset, pagination, and navigation into a card view; advanced collection analytics and richer card design stay out of scope.
- Test-first critical paths: Pass with implementation requirement. Tests are needed for aggregated counts, duplicate filtering, type filter `AND` semantics, two-type selection cap, filter persistence across pages, and empty states.
- Observability & debuggability: Pass with implementation requirement. Structured logs must capture collection page renders, filter toggles, reset actions, and detail-card navigation.

## Project Structure

### Documentation (this feature)

```text
specs/003-collection-filters/
├── plan.md
└── spec.md
```

### Source Code (repository root)

```text
bot/
├── db/
│   ├── database.py
│   └── __init__.py
├── handlers/
│   ├── commands.py
│   ├── navigation.py
│   └── sections/
│       ├── collection.py
│       ├── shop.py
│       └── ...
├── navigation/
│   ├── session.py
│   └── router.py
├── ui/
│   ├── menu.py
│   └── messages.py
└── utils/
    └── logging.py

tests/
├── integration/
│   ├── test_handlers.py
│   ├── test_navigation.py
│   └── ...
└── unit/
    ├── test_collection.py
    └── ...
```

**Structure Decision**: Keep the existing Telegram-bot layout. Implement collection orchestration in [collection.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/collection.py), add read/query helpers and collection DTOs in [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py), reuse the current session/navigation system for page/filter state, and add focused unit/integration coverage under `tests/unit` and `tests/integration`.

## Design Notes

- Aggregate collection entries by `pokemon_catalog.id` for each user so duplicates can be shown as `xN`.
- Normalize type filtering in application/query logic so stored values like `grass/poison` can be matched by separate type toggles.
- Limit active type filters to two selections and enforce `AND` matching when both are selected.
- Keep filter state in session-backed navigation payload for the active collection flow; only introduce database persistence if session-based state proves insufficient during implementation.
- Reuse the existing pokemon reward card path where possible for collection detail navigation, but treat the card UI itself as a follow-up enhancement if the current card payload is incomplete.

## Implementation Phases

### Phase 1 - Data and query layer

- Add collection DTOs for aggregated entry rows, filter state, and paginated results.
- Implement database queries to fetch a user’s collection grouped by species with quantity counts.
- Add support for filtering by rarities, normalized types, and duplicates-only.
- Add pagination support with a fixed page size of 12.

### Phase 2 - Telegram collection flow

- Replace the placeholder `collection_handler` with a real collection screen.
- Add callback routes for collection pagination, filter screen navigation, filter toggles, reset, and detail-card actions.
- Render compact collection text plus entry buttons below the summary.
- Preserve active filters and current page through callback navigation.

### Phase 3 - Tests and observability

- Add unit tests for collection aggregation and filter semantics.
- Add integration tests for Telegram navigation, filter toggles, reset, pagination, and empty-state behavior.
- Add structured logs for collection renders, filter changes, and detail-card opens.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
