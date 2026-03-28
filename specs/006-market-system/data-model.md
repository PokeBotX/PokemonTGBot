# Market Data Model

## Core Tables

### `market_listings`
- Represents one active or historical sale listing for a concrete `user_pokemon.id`
- Uses `pokecoin` via `currency_id`
- Tracks:
  - seller
  - concrete pokemon instance
  - price
  - status
  - first commission charged at creation
  - next commission checkpoint
  - hard expiry timestamp
  - purchaser when sold

### `market_buy_requests`
- Represents one active or historical request to buy a concrete `pokemon_catalog.id`
- Uses `pokecoin` via `currency_id`
- Stores:
  - requester
  - requested pokemon species
  - offered price
  - reserved amount
  - status
  - fulfillment seller and transferred `user_pokemon.id`

## Hard Invariants

- One `user_pokemon` can have at most one active sale listing.
- Locked pokemon cannot be listed or used to fulfill a buy request.
- Active sale listings are limited to `2` per user.
- Active buy requests are limited to `5` per user.
- Buy request funds are reserved immediately by debiting `user_balances`.
- Listing creation charges the first daily commission immediately.

## Statuses

### Listing statuses
- `active`
- `sold`
- `removed`
- `expired`

### Buy-request statuses
- `active`
- `fulfilled`
- `canceled`

## Derived Read Models

- `MarketListingSummary`
- `MarketBuyRequestSummary`
- `MarketBrowsePage`
- `MarketPurchaseResult`
- `MarketRequestFulfillmentResult`

