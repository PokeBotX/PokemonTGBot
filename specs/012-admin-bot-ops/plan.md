# Implementation Plan: Admin Bot Operations

**Branch**: `012-admin-bot-ops` | **Date**: 2026-04-29 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/012-admin-bot-ops/spec.md)  
**Input**: Feature specification from `/specs/012-admin-bot-ops/spec.md`

## Summary

Extend the existing admin bot with three new operational capabilities: browse/export admin audit history, point-edit pokemon species in `pokemon_catalog`, and send preview-confirmed plain-text broadcasts to eligible group chats where the main bot is currently present. The feature builds on the already shipped admin-bot foundation, reusing its access control, pending-action confirmation model, and audit framework. The implementation should stay conservative: private-chat-only, one superadmin role, explicit confirmation for all mutations, bounded exports, and dry-run preview for broadcasts.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog, existing admin pending/audit framework  
**Storage**: PostgreSQL for audit/catalog/chat lookups; existing operational bot state tables for chat targeting  
**Testing**: pytest, pytest-asyncio, focused unit and integration tests for audit browse/export, species edits, and broadcast delivery  
**Target Platform**: Existing separate admin bot, private-chat-only  
**Project Type**: Telegram bot operational workflow extension  
**Performance Goals**: Bounded audit views/exports; broadcasts should complete in one operator flow with a clear outcome summary  
**Constraints**: Reuse existing admin-bot allowlist and confirm model; broadcast payload is text-only; targets limited to group/supergroup chats where the main bot is present; species edits are point edits only  
**Scale/Scope**: One new spec layered on top of the existing admin bot rather than a separate service

## Constitution Check

- Telegram-first UX: Pass. All operator flows remain inside the admin bot.
- Consistency & ownership: Pass. The feature extends the existing admin-bot boundaries rather than creating a third control plane.
- Scope-driven delivery: Pass. The spec is one coherent operational slice with three related capabilities.
- Test-first critical paths: Pass with implementation requirement. Broadcast preview/confirm/failure and species point edits need direct tests.
- Observability & debuggability: Pass with implementation requirement. Exports, summaries, and audit coverage are core outcomes of the feature itself.

## Project Structure

### Documentation (this feature)

```text
specs/012-admin-bot-ops/
├── plan.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
bot/
├── admin/
│   ├── handlers.py
│   ├── pending.py
│   ├── session.py
│   └── ui.py
├── db/
│   └── database.py
└── ...

sql/
└── schema.sql

tests/
├── integration/
│   └── test_admin_bot_flow.py
└── unit/
    ├── test_admin_access.py
    ├── test_admin_actions.py
    └── test_admin_images.py
```

**Structure Decision**: Reuse the existing admin-bot module tree and extend its handlers/UI instead of creating another operational subsystem. Keep database access in explicit privileged helpers within `bot/db/database.py`.

## Design Notes

- Add audit browse/export as a first-class admin section rather than telling operators to inspect DB tables manually.
- Model species edits as point edits with a selected field name and one new value, then a shared confirmation step.
- Keep broadcast target resolution server-side and deterministic, using known bot-presence data rather than free-form chat lists.
- Favor bounded audit exports, such as the most recent N records or a constrained filter set, over unbounded dumps.
- Treat broadcasts as mutating operational actions and put them through the same preview/confirm/audit path as grants.
- Prefer resilient post-run broadcast summaries with counts and sample failures instead of hard-failing the whole operator experience on one bad chat.

## Implementation Phases

### Phase 1 - Audit browse/export

- Add admin audit view section and recent-record list rendering.
- Add export action with bounded output.
- Add privileged DB helpers for recent audit fetch and export payload assembly.

### Phase 2 - Pokemon species point edits

- Add species-edit entry flow by `pokemon_id`.
- Add field-selection UI and field-specific validation.
- Add confirmation preview and transactional DB mutation helpers.

### Phase 3 - Broadcast by eligible chats

- Add broadcast compose flow with text intake.
- Add target-chat resolution for group/supergroup chats where the main bot is present.
- Add dry-run preview, confirmation, send loop, and итог summary.

### Phase 4 - Verification and polish

- Add targeted unit/integration coverage for audit, species edits, and broadcasts.
- Tighten user-facing copy for dangerous or high-blast-radius actions.
- Add rollout notes for operational usage and deployment expectations.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Broadcast flow inside admin bot | Operators need one control plane for urgent announcements | External scripts or SQL-driven fanout bypass confirmation, audit, and operator UX |
| Audit export from Telegram | Operators need portable operational evidence without SSH/SQL | Relying only on DB access undermines the point of the admin bot |

## Notes

- Stay conservative with blast radius: no rich media broadcast, no free-form chat targeting, no instance-level pokemon editing in this slice.
- Reuse existing admin confirmation and audit primitives wherever possible so this feature behaves like the already shipped admin flows.
