# Implementation Plan: Admin Bot

**Branch**: `010-admin-bot` | **Date**: 2026-04-25 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/010-admin-bot/spec.md)  
**Input**: Feature specification from `/specs/010-admin-bot/spec.md`

## Summary

Add a second Telegram bot dedicated to administrative operations. The bot will run with its own token, allow access only to superadmins listed in env, and work only in private chats. It will provide button-driven admin flows with mandatory confirmation before every mutation. Version 1 will support currency grants, pokemon grants, creation of new pokemon species, Telegram-based image uploads into MinIO, attachment of image variants to existing pokemon, editing `image source`, and managing image-variant ordering/default. Every mutating action will produce both structured logs and an audit trail.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog, existing S3/MinIO integration helpers  
**Storage**: PostgreSQL for operational data and audit trail; the same S3/MinIO bucket set used by the main bot for uploaded images  
**Testing**: pytest, pytest-asyncio, targeted unit/integration tests for auth, pending actions, grants, and image management  
**Target Platform**: Separate Telegram bot for private-chat-only superadmin usage  
**Project Type**: Telegram bot application with button-first admin workflows and staged confirmation state  
**Performance Goals**: Admin actions should complete in one interactive Telegram flow, while image uploads and DB mutations remain bounded and auditable  
**Constraints**: Access allowlist comes from env; only one superadmin role; all mutating actions need explicit confirmation; target-user lookup is by `@username`; full pokemon creation requires all catalog fields; image uploads come from Telegram messages; admin bot reuses main DB and MinIO credentials  
**Scale/Scope**: One new privileged bot entrypoint, an admin session/pending-action layer, privileged DB services, MinIO upload flows, and audit logging

## Constitution Check

- Telegram-first UX: Pass. Admin flows remain inside Telegram with button-based confirmations.
- Consistency & ownership: Pass with implementation requirement. All privileged mutations must reuse the same DB and media storage as the main app.
- Scope-driven delivery: Pass. One spec can cover foundation plus first-operation set, while implementation can still ship in phases.
- Test-first critical paths: Pass with implementation requirement. Access control, confirmation gating, and image upload flows need direct tests.
- Observability & debuggability: Pass with implementation requirement. Every privileged action needs both user-facing result text and audit/log records.

## Project Structure

### Documentation (this feature)

```text
specs/010-admin-bot/
├── plan.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
bot/
├── admin/
│   ├── handlers/
│   ├── services/
│   ├── sessions/
│   └── ui/
├── db/
│   └── database.py
└── ...

main.py
main_local.py
main_admin.py
main_admin_local.py

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

**Structure Decision**: Keep the admin bot isolated from the public bot through dedicated entrypoints and a dedicated `bot/admin/` module tree. Reuse the shared DB layer where practical, but introduce explicit privileged services and an audit subsystem instead of scattering admin writes across generic handlers.

## Design Notes

- Use a dedicated `ADMIN_BOT_TOKEN` and explicit admin-only startup path instead of mixing privileged commands into the public bot.
- Keep superadmin access in env through a parsed allowlist such as `ADMIN_BOT_ALLOWED_IDS`.
- Prefer a staged `pending action` model over immediate mutation so confirmation is guaranteed consistently across all admin operations.
- Reuse the same PostgreSQL connection pool and S3/MinIO credentials as the main application to avoid data drift.
- Add a dedicated audit table rather than relying only on logs.
- Treat Telegram image uploads as first-class inputs: download file, upload to MinIO, then create/update `image_credits` and variant mappings.
- Make image-variant management compatible with feature `009-pokemon-image-variants` from day one.
- Keep version 1 private-chat-only and single-role-only to reduce access-control complexity.

## Implementation Phases

### Phase 1 - Admin bot foundation

- Add dedicated admin entrypoints and env parsing for token and allowlist.
- Add private-chat access guard and admin menu shell.
- Add admin pending-action/session framework with confirm/cancel pattern.

### Phase 2 - Audit and privileged service layer

- Add audit table/schema and shared helpers to record attempted/completed admin actions.
- Add privileged DB service methods for grants and pokemon catalog mutations.
- Add structured logs around all admin flows.

### Phase 3 - Currency and pokemon grant flows

- Implement button-driven flows for grant currency and grant pokemon.
- Validate `@username`, resource existence, and operation parameters before confirmation.
- Return explicit success/failure summaries after confirmation.

### Phase 4 - Pokemon creation flow

- Implement full-field pokemon creation draft flow.
- Validate complete catalog payload before confirmation.
- Create the new species transactionally and audit the result.

### Phase 5 - Image upload and image-management flows

- Accept Telegram photo/document uploads as image input.
- Upload accepted files into MinIO and create/update `image_credits`.
- Add flows for attaching new variants, editing `source`, changing display order, and marking default variants.

### Phase 6 - Verification and polish

- Add targeted tests for access control, pending confirmations, grants, pokemon creation, and image-management actions.
- Tighten UX text for dangerous actions.
- Verify that failed operations do not leave half-written DB/media state when avoidable.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Separate admin bot entrypoint and module tree | Privileged operations need isolation from the public bot and clearer deployment boundaries | Folding admin flows into the public bot increases blast radius and permission mistakes |
| Dedicated audit subsystem | Logs alone are not enough for operational accountability | Pure structlog output is harder to query and reason about after the fact |

## Notes

- Keep access control conservative: allowlist first, private chat only, one role only.
- Version 1 should optimize for safety and clarity, not operator speed at any cost.
- Prefer reusable admin service methods so later features can share confirmation, audit, and error handling patterns.
