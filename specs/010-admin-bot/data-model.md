# Admin Bot Data Model

## Core Runtime Entities

### Admin Actor
- Telegram user id from `ADMIN_BOT_ALLOWED_IDS`
- Uses the separate admin bot only in private chat
- All privileged actions are attributed to this actor in audit

### Admin Pending Action
- Staged mutation waiting for explicit confirmation
- Stored in admin-menu session data
- Contains:
  - `action_type`
  - human title
  - human description
  - input payload
  - optional target user identity
  - creation timestamp

### Admin Audit Record
- Persisted in `admin_action_audit`
- Tracks:
  - actor DB id / Telegram id / username
  - target DB id / Telegram id / username
  - action type
  - status
  - input payload
  - result payload
  - error message
  - created timestamp

## Planned Operation Entities

### Currency Grant Draft
- target `@username`
- currency code
- amount

### Pokemon Grant Draft
- target `@username`
- `pokemon_id`

### Pokemon Draft
- full `pokemon_catalog` payload

### Image Upload Draft
- Telegram photo/document payload
- target `pokemon_id`
- source URL
- `display_order`
- `is_default`

