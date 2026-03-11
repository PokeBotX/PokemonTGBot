# Implementation Plan: Shop, Daily Bonus, and Gacha

**Branch**: `002-shop-system` | **Date**: 2026-03-11 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/002-shop-system/spec.md)
**Input**: Feature specification from `/specs/002-shop-system/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a complete shop flow inside the Telegram bot: shop screen rendering, `pokedollar` daily bonus claiming, single and `x5` gacha spins with rarity rules and pity counters, single-item purchases for `ultraball` and `masterball`, and a non-functional VIP placeholder. Implementation will extend the existing Telegram menu/navigation flow, persist shop state in PostgreSQL, reuse the existing pokemon catalog and user-owned pokemon tables, and add tests around economy integrity, pity progression, and duplicate-click safety.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog, python-dotenv  
**Storage**: PostgreSQL for balances, owned pokemon, shop state, and catalog data  
**Testing**: pytest, pytest-asyncio, pytest-mock  
**Target Platform**: Linux-hosted Telegram bot in polling and webhook modes  
**Project Type**: Telegram bot application with async handlers and PostgreSQL-backed state  
**Performance Goals**: Callback interactions should feel immediate in Telegram; critical button presses should answer quickly and complete normal shop actions within a single user interaction  
**Constraints**: Must preserve balance integrity, avoid negative balances, survive duplicate callback presses, persist pity counters across restarts, keep Telegram messages concise, and use fallback `image.png` when pokemon art is missing  
**Scale/Scope**: One new shop flow, one new persistent shop-state model, shop item purchases, daily bonus claiming, and gacha reward generation for existing catalog data

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Telegram-first UX: Pass. The feature is fully button-driven, exposes pity and bonus state directly in messages, and returns explicit feedback for successful claims, insufficient funds, and unavailable bonus timing.
- Consistency & ownership: Pass with implementation requirement. Balance spending, reward issuance, and pity updates must be handled atomically in PostgreSQL so duplicate clicks cannot mint currency or duplicate pokemon rewards.
- Scope-driven delivery: Pass. Version 1 includes shop, bonus, standard spins, item purchases, and VIP placeholder only; targeted premium spins are explicitly excluded.
- Test-first critical paths: Pass with implementation requirement. Tests are required for balance deduction, one-hour bonus claim gating, `x5` sequential pity progression, guarantee thresholds, and duplicate-click protection.
- Observability & debuggability: Pass with implementation requirement. Structured logs must capture purchase attempts, bonus claims, gacha outcomes, pity resets, and transactional failures without leaking sensitive data.

## Project Structure

### Documentation (this feature)

```text
specs/002-shop-system/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
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
│       ├── shop.py
│       ├── back.py
│       ├── collection.py
│       ├── market.py
│       └── ...
├── navigation/
│   ├── context.py
│   ├── router.py
│   └── session.py
├── ui/
│   ├── menu.py
│   └── messages.py
└── utils/
    └── logging.py

sql/
└── schema.sql

scripts/
└── import_pokedex_xlsx.py

tests/
├── integration/
│   ├── test_handlers.py
│   └── test_navigation.py
└── unit/
    ├── test_context.py
    ├── test_menu.py
    ├── test_router.py
    └── test_session.py
```

**Structure Decision**: Keep the existing single-project Telegram bot layout. Implement shop orchestration in [`bot/handlers/sections/shop.py`](/home/deck/Desktop/pokemonbot/bot/handlers/sections/shop.py), extend [`bot/db/database.py`](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [`sql/schema.sql`](/home/deck/Desktop/pokemonbot/sql/schema.sql) for persistent shop state and economy operations, and add unit/integration coverage under [`tests/unit`](/home/deck/Desktop/pokemonbot/tests/unit) and [`tests/integration`](/home/deck/Desktop/pokemonbot/tests/integration).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
