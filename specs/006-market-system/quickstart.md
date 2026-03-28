# Market Quickstart

## Current Foundation

This feature currently has:
- extended market schema
- market DTOs and transactional helpers in `bot/db/database.py`
- market route/action constants in `bot/handlers/sections/market.py`
- unit-test coverage for core math and branch helpers

## Next UI Slices

1. Add `Рынок` button to shared non-shop pokemon cards.
2. Replace market placeholder root with real `Купить / Продать / Мои лоты / Мои заявки`.
3. Implement card-entry branching:
   - owned pokemon -> sale flow
   - not owned -> buy-request flow
4. Add command-based price entry:
   - dedicated sell-price command
   - dedicated buy-price command

## Validation Targets

- listing commission math
- sale-slot and request-slot limits
- atomic purchase
- atomic request fulfillment
- SQL-first paginated browse queries

