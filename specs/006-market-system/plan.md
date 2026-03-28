# Implementation Plan: Market System

**Branch**: `006-market-system` | **Date**: 2026-03-21 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/006-market-system/spec.md)  
**Input**: Feature specification from `/specs/006-market-system/spec.md`

## Summary

Add a Telegram-native player market where users can sell owned pokemon instances and fulfill buy requests using `pokecoin`. The system will support two active sale slots per user, five active buy requests per user, immediate and recurring daily listing commission, five-day listing expiry, browseable sale listings with compact filters, seller-facing buy-request discovery, and card-driven market entry from shared pokemon cards. The implementation will extend the database schema for listing state, buy requests, reserved funds, and commission timing; add market-specific Telegram flows for browsing, confirmation, and command-based price entry; and introduce a shared pokemon-card layer for non-shop modules so market actions can start directly from pokemon cards.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog, redis  
**Storage**: PostgreSQL for listings, buy requests, reserved `pokecoin`, commission state, and market ownership checks; Redis optionally reused for lightweight pending-input/session helpers but not as the source of truth for market transactions  
**Testing**: pytest, pytest-asyncio, pytest-mock  
**Target Platform**: Linux-hosted Telegram bot in polling and webhook modes, serving private chat market flows with callback-driven navigation and command-based price entry  
**Project Type**: Telegram bot application with async handlers, PostgreSQL-backed economy state, and inline-keyboard UI  
**Performance Goals**: Market browse flows should query only the needed page/filter slice; purchases and request fulfillment must complete atomically in a single transaction; market card entry should reuse shared rendering instead of duplicating per-module card logic  
**Constraints**: Currency is `pokecoin` only; sales use concrete `user_pokemon` instances; active sale slots capped at `2`; active buy requests capped at `5`; first `1%` commission charged immediately; listings expire after `5` days; buy-request funds must be reserved immediately; locked pokemon cannot be sold or used to fulfill requests; card-driven market actions must branch into sell vs buy-request based on ownership  
**Scale/Scope**: One new market subsystem with root screen, buy view, sell view, my listings, my requests, price-entry commands, daily commission lifecycle, and shared card helpers for non-shop card flows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Telegram-first UX: Pass. The market is designed around compact Telegram screens, inline buttons, and short confirmation messages, with price entry handled by explicit commands rather than free-form long conversations.
- Consistency & ownership: Pass with implementation requirement. Market transactions must atomically transfer pokemon instances, release/reserve `pokecoin`, and prevent self-trades, double-buys, and locked-pokemon misuse.
- Scope-driven delivery: Pass. Version 1 covers listings, purchases, buy requests, my listings, my requests, commissions, expiry, and card entry; advanced analytics, dynamic pricing hints, and full-blown negotiation flows stay out of scope.
- Test-first critical paths: Pass with implementation requirement. Tests are required for sale-slot limits, buy-request limits, commission debit, auto-removal, reserved-fund lifecycle, concurrent purchase safety, and card-entry branching.
- Observability & debuggability: Pass with implementation requirement. Structured logs must capture listing creation, commission debit, auto-removal, purchase completion, request creation, request fulfillment, and card-entry routing.

## Project Structure

### Documentation (this feature)

```text
specs/006-market-system/
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
│   ├── sections/
│   │   ├── market.py
│   │   ├── profile.py
│   │   ├── collection.py
│   │   └── ...
│   └── ...
├── navigation/
│   ├── router.py
│   └── session.py
├── ui/
│   ├── menu.py
│   ├── messages.py
│   └── ...
└── ...

sql/
└── schema.sql

tests/
├── integration/
│   ├── test_handlers.py
│   ├── test_navigation.py
│   └── ...
└── unit/
    ├── test_database.py
    └── ...
```

**Structure Decision**: Keep the existing project layout. Implement market orchestration in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py), extend [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) for transactional market state, and add a shared non-shop pokemon-card helper under `bot/ui/` or a nearby reusable module before integrating card-driven market entry.

## Design Notes

- Use PostgreSQL as the market source of truth; do not keep listing state only in session or Redis.
- Model sale listings and buy requests separately; they have different limits, lifecycles, and balance semantics.
- Reserve full `pokecoin` amount immediately for buy requests to avoid fake liquidity.
- Track listing commission timestamps explicitly instead of trying to infer them from creation date alone.
- Reuse existing pending-input/session mechanisms for command-based price entry, but scope them carefully so private market flows do not break group-message encounter handling.
- Introduce a shared pokemon-card rendering/helper layer for collection/profile/search/encounter/market flows, while leaving shop-specific card rendering separate.
- Keep market browse queries SQL-first with pagination and filter clauses; avoid Python-side full-list filtering for sale listings or buy requests.

## Implementation Phases

### Phase 1 - Data model and transactional foundations

- Extend schema for sale listings, buy requests, reserved-fund tracking, commission timestamps, listing expiry, and request status.
- Add database DTOs/read models for market browse pages, listing summaries, request summaries, and market-card action context.
- Add transactional helpers for listing creation, listing removal, purchase completion, request creation, request cancellation, and request fulfillment.

### Phase 2 - Shared pokemon-card market entry

- Introduce a reusable non-shop pokemon-card rendering layer.
- Add a `Рынок` button to shared cards.
- Route card entry into `sell this pokemon` when the user owns the pokemon, otherwise into `create buy request`.

### Phase 3 - Buy-side market screens

- Implement market root and `Купить` flow in [market.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/market.py).
- Add rarity filter, affordability filter, and sort-mode state.
- Implement purchase confirmation and atomic buy completion.

### Phase 4 - Sell-side and request-side flows

- Implement `Продать` to show only fulfillable foreign buy requests.
- Implement request fulfillment from owned unlocked pokemon.
- Implement `Мои лоты` and `Мои заявки`, including manual cancellation/removal flows.

### Phase 5 - Price entry and lifecycle automation

- Add separate command-based price entry flows for sale listings and buy requests.
- Add compact confirmation messages for both flows.
- Implement commission billing, auto-removal on insufficient funds, and five-day listing expiry.

### Phase 6 - Testing, safety, and polish

- Add concurrency and integrity tests for listing purchase and request fulfillment.
- Add structured logs for the full market lifecycle.
- Tighten message length, button clarity, and failure feedback in Telegram UI.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
