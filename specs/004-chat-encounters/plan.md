# Implementation Plan: Chat Pokemon Encounters

**Branch**: `004-chat-encounters` | **Date**: 2026-03-17 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/004-chat-encounters/spec.md)  
**Input**: Feature specification from `/specs/004-chat-encounters/spec.md`

## Summary

Add a group-chat-only encounter system where a wild pokemon can appear in a chat after a hidden cooldown and trigger conditions are met. The bot will track per-chat cooldowns and message counts, spawn exactly one active encounter at a time, allow any chat participant to attempt capture once per encounter, resolve catches using three ball tiers with configured probabilities, and close encounters on successful capture or after a 5-minute timeout. Implementation will extend the Telegram bot with group message handling, a new `/find` command, persistent encounter state in PostgreSQL, and encounter-specific callback rules that intentionally do not enforce the usual single-user button ownership.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog, redis  
**Storage**: PostgreSQL for persistent encounter state, per-chat cooldown/message counters, capture attempts, and reward issuance; Redis-backed menu sessions when enabled, with in-memory fallback  
**Testing**: pytest, pytest-asyncio, pytest-mock  
**Target Platform**: Linux-hosted Telegram bot in polling and webhook modes, operating in private chats and group chats  
**Project Type**: Telegram bot application with async handlers, PostgreSQL-backed game state, and callback-driven UI  
**Performance Goals**: Message-triggered encounter checks should remain lightweight; capture button resolution must complete in a single callback interaction; concurrent clicks from different users must resolve consistently without double-catching  
**Constraints**: Encounter flow must work only in non-private chats, keep cooldown hidden from users, preserve one active encounter per chat, allow any user to press encounter buttons, enforce one attempt per user per encounter, support timeout cleanup after 5 minutes, and reuse existing pokemon ownership tables and inventory tables where possible  
**Scale/Scope**: One new encounter subsystem, one new manual `/find` trigger, one new group-message trigger path, per-chat cooldown logic, and catch resolution using existing pokemon and item data

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Telegram-first UX: Pass. The mechanic is chat-native, button-based, and intentionally concise: one image, one short encounter text, short callback notifications on failure, and a single edited message on success or timeout.
- Consistency & ownership: Pass with implementation requirement. Encounter resolution must atomically handle winner selection, inventory consumption, attempt recording, and reward issuance so concurrent clicks cannot duplicate captures or consume the same encounter twice.
- Scope-driven delivery: Pass. Version 1 includes spawn logic, `/find`, capture attempts, timeout cleanup, and reward issuance only; richer encounter animations or advanced chat economy mechanics stay out of scope.
- Test-first critical paths: Pass with implementation requirement. Tests are required for cooldown gating, 10-message trigger logic, one-attempt-per-user enforcement, concurrent capture safety, timeout cleanup, and inventory consumption.
- Observability & debuggability: Pass with implementation requirement. Structured logs must capture per-chat spawn checks, encounter creation, attempt outcomes, timeout expiration, and reward persistence.

## Project Structure

### Documentation (this feature)

```text
specs/004-chat-encounters/
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
│   │   ├── chat.py
│   │   ├── shop.py
│   │   └── ...
│   └── ...
├── navigation/
│   ├── router.py
│   └── session.py
├── ui/
│   ├── menu.py
│   └── messages.py
└── utils/
    └── logging.py

sql/
└── schema.sql

tests/
├── integration/
│   ├── test_handlers.py
│   ├── test_navigation.py
│   └── ...
└── unit/
    ├── test_chat_encounters.py
    └── ...
```

**Structure Decision**: Keep the existing bot layout. Implement encounter orchestration in a dedicated handler module tied to group-message activity and encounter callbacks, extend [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) and [sql/schema.sql](/home/deck/Desktop/pokemonbot/sql/schema.sql) for per-chat encounter state and attempt tracking, and add focused unit/integration coverage under `tests/unit` and `tests/integration`.

## Design Notes

- Introduce persistent per-chat encounter state rather than trying to infer cooldown from message history.
- Track message progression since the last eligible spawn in the database so encounter logic works across restarts.
- Model active encounter attempts separately enough to enforce one attempt per user per encounter without blocking other users.
- Do not reuse the normal menu-session ownership guard for encounter buttons; encounter callbacks need a dedicated path that validates chat/message context but intentionally allows multiple users.
- Reuse existing pokemon reward issuance and inventory concepts where practical: regular pokeball is virtual/infinite, ultraball and masterball consume rows from `user_items`.
- Handle timeout cleanup explicitly so the encounter message can be edited to `Тут кто-то был...` after 5 minutes.

## Implementation Phases

### Phase 1 - Data and spawn state

- Add persistent encounter/chat state models and schema support.
- Track per-chat cooldown timestamps, message counters, active encounter metadata, and user attempts.
- Add database helpers for spawn eligibility checks and encounter creation.

### Phase 2 - Telegram trigger flow

- Add a group-message handler to count messages and check spawn eligibility.
- Add `/find` command support for group chats.
- Publish encounter messages with image plus three ball buttons.

### Phase 3 - Capture resolution

- Add encounter-specific callback handling that allows any user in the chat to click.
- Resolve capture chances, consume inventory where needed, and award the pokemon on success.
- Emit callback notifications for failed attempts and edit the encounter message on success.

### Phase 4 - Timeout and safety

- Add 5-minute encounter expiration handling and encounter cleanup.
- Protect against concurrent clicks and double-capture conditions.
- Add structured logs and end-to-end tests for cooldown, attempts, success, failure, and timeout.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
