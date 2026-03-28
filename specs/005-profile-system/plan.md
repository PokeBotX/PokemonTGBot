# Implementation Plan: Profile System

**Branch**: `005-profile-system` | **Date**: 2026-03-20 | **Spec**: [spec.md](/home/deck/Desktop/pokemonbot/specs/005-profile-system/spec.md)  
**Input**: Feature specification from `/specs/005-profile-system/spec.md`

## Summary

Replace the current profile placeholder with a real Telegram profile flow. The new profile will show the user name, Telegram ID, account age, unique-pokemon completion progress, rarity-based completion progress, and a cover image. It will include nested screens for settings and referral link, real persistence for nickname and language changes, a cover-selection flow based on pokemon the user already owns, a reusable pokemon-name search flow reserved under `/search`, and placeholder-only sections for battle team and VIP.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: python-telegram-bot, asyncpg, structlog  
**Storage**: PostgreSQL for users, user settings, pokemon ownership, and image references; Redis-backed menu sessions when enabled with in-memory fallback  
**Testing**: pytest, pytest-asyncio, pytest-mock  
**Target Platform**: Linux-hosted Telegram bot in polling and webhook modes  
**Project Type**: Telegram bot application with callback-driven UI and PostgreSQL-backed user data  
**Performance Goals**: Profile opening should remain fast enough for interactive Telegram use; profile summary queries must avoid loading more pokemon rows than needed; pokemon-name search and cover search should remain responsive even for users with large collections and must not load the entire 1025-entry catalog into Python  
**Constraints**: Cover images may only come from already-owned pokemon with existing bot images; language changes persist in DB even before runtime localization is implemented; battle team and VIP stay placeholder-only in this scope  
**Scale/Scope**: One complete profile section, one settings subsection, one referral subsection, one owned-pokemon cover search flow, one reusable pokemon-name search flow, and light persistence extensions around user settings and profile summary queries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Telegram-first UX: Pass. The feature is fully button- and message-driven, with short nested screens, explicit save feedback, and clear back navigation.
- Consistency & ownership: Pass with implementation requirement. Cover selection must verify ownership and available image metadata before persisting anything; nickname/language writes must target only the current user.
- Scope-driven delivery: Pass. Version 1 focuses on profile summary, settings, referral link, cover selection, and a lean SQL-backed pokemon-name search; battle team and VIP remain explicitly placeholder-only.
- Test-first critical paths: Pass with implementation requirement. Tests are required for profile summary metrics, nickname updates, language persistence, ownership-gated cover selection, and default cover behavior.
- Observability & debuggability: Pass with implementation requirement. Structured logs should capture profile renders, settings changes, cover search/select actions, and rejected cover attempts.

## Project Structure

### Documentation (this feature)

```text
specs/005-profile-system/
├── plan.md
└── spec.md
```

### Source Code (repository root)

```text
bot/
├── db/
│   └── database.py
├── handlers/
│   ├── commands.py
│   ├── navigation.py
│   └── sections/
│       ├── profile.py
│       └── ...
├── navigation/
│   ├── router.py
│   └── session.py
├── ui/
│   ├── menu.py
│   └── messages.py
└── ...

sql/
└── schema.sql

tests/
├── integration/
│   ├── test_handlers.py
│   └── ...
└── unit/
    └── ...
```

**Structure Decision**: Keep all profile UX in [profile.py](/home/deck/Desktop/pokemonbot/bot/handlers/sections/profile.py), extend [database.py](/home/deck/Desktop/pokemonbot/bot/db/database.py) with focused read/write methods for profile summary and settings changes, and reuse the existing session/navigation model for nested profile screens and multi-step input flows.

## Design Notes

- Profile summary should be backed by direct SQL aggregates rather than loading the full collection into Python.
- Rarity progress should count unique owned species per rarity and compare against total catalog species per rarity.
- Cover selection should use a search-driven flow over the user’s owned pokemon only, not a full browsable list.
- The reserved `/search` feature should reuse the same search primitives but query via SQL filtering plus result limits instead of preloading the entire pokemon catalog.
- Persist the chosen cover through existing image reference concepts where possible; default to `image_profile.png` when nothing is selected.
- Keep team/VIP buttons in the keyboard to preserve layout, but route them to explicit placeholders.
- Use a nested navigation shape: profile root -> settings -> language/nickname/cover actions -> back to profile.

## Implementation Phases

### Phase 1 - Profile summary and root screen

- Add database query support for account age, unique-pokemon totals, and rarity-based profile progress.
- Replace the profile placeholder with a real root screen and profile keyboard.
- Wire direct `/profile` access into the same real screen.

### Phase 2 - Settings persistence

- Add settings screen rendering and nested profile routing.
- Implement nickname change flow and database write.
- Implement language write flow with persistence-only semantics for now.

### Phase 3 - Referral and placeholders

- Add a dedicated referral screen that shows only the user’s referral link.
- Add placeholder screens for battle team and VIP with proper back navigation.

### Phase 4 - Cover selection

- Add default cover rendering using `image_profile.png`.
- Build owned-pokemon cover search and selection flow.
- Enforce ownership and image availability before saving the cover choice.

### Phase 5 - Pokemon-name search

- Add a reusable pokemon-name search query that filters and limits in SQL.
- Return direct card output on a single match and a compact choice list on multiple matches.
- Reuse the same search foundation for cover selection where ownership-scoped results are needed.

### Phase 6 - Validation and polish

- Add tests for summary metrics, settings updates, referral rendering, default cover fallback, and ownership-gated cover selection.
- Add structured logs for profile opens and settings changes.
- Review message length and navigation clarity across nested profile screens.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
