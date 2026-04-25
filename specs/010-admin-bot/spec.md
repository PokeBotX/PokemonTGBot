# Feature Specification: Admin Bot

**Feature Branch**: `010-admin-bot`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: User description: "нужен второй админ-бот с доступом к БД и MinIO, чтобы через него выдавать валюту, выдавать покемонов, создавать новых покемонов, загружать картинки, добавлять картинки существующему покемону, править image source и другие админ-действия; пользоваться им могут только superadmin-пользователи из env; бот работает только в личке; все действия подтверждаются кнопками и логируются"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Restrict admin bot access to superadmins (Priority: P1)

Только разрешённые superadmin-пользователи могут пользоваться вторым ботом, и только в личке.

**Why this priority**: Без жёсткого контроля доступа весь админ-бот небезопасен.

**Independent Test**: Разрешённый пользователь пишет боту в личке и получает меню. Неразрешённый пользователь или пользователь в групповом чате получает отказ.

**Acceptance Scenarios**:

1. **Given** Telegram user id присутствует в `ADMIN_BOT_ALLOWED_IDS`, **When** пользователь пишет боту в личке, **Then** бот допускает его к админ-функциям.
2. **Given** user id отсутствует в списке superadmin в env, **When** пользователь пишет боту, **Then** бот отвечает отказом и не открывает меню.
3. **Given** разрешённый superadmin пишет боту не в личке, **When** бот проверяет тип чата, **Then** бот отвечает, что админ-бот доступен только в личке.
4. **Given** бот перезапускается, **When** он загружает конфиг, **Then** список разрешённых superadmin подхватывается из env без отдельной БД-таблицы.

---

### User Story 2 - Execute currency and pokemon grants safely (Priority: P1)

Superadmin может выдать пользователю валюту или конкретного покемона, но каждое действие сначала показывается как подтверждаемая операция с описанием последствий.

**Why this priority**: Это самый частый operational flow для поддержки и администрирования.

**Independent Test**: Superadmin инициирует выдачу валюты и выдачу покемона по `@username`, видит экран подтверждения, подтверждает действие и получает итоговый результат.

**Acceptance Scenarios**:

1. **Given** superadmin инициирует выдачу валюты по `@username`, **When** пользователь найден, **Then** бот показывает подтверждение с валютой, суммой и целевым пользователем.
2. **Given** superadmin подтверждает выдачу валюты, **When** БД-операция проходит успешно, **Then** баланс пользователя увеличивается и бот показывает итоговое сообщение.
3. **Given** superadmin инициирует выдачу покемона по `@username` и `pokemon_id`, **When** пользователь и покемон найдены, **Then** бот показывает подтверждение с параметрами операции.
4. **Given** superadmin подтверждает выдачу покемона, **When** операция завершается, **Then** пользователю создаётся новый `user_pokemon`, а бот сообщает id экземпляра.
5. **Given** `@username` не найден или `pokemon_id` не существует, **When** superadmin инициирует операцию, **Then** бот отвечает понятной ошибкой без выполнения действия.

---

### User Story 3 - Create a new pokemon species from the admin bot (Priority: P1)

Superadmin может создать нового покемона с полным набором полей каталога через бот с обязательным подтверждением.

**Why this priority**: Без этого админ-бот не покрывает управление каталогом покемонов.

**Independent Test**: Superadmin задаёт полный набор полей для нового покемона, подтверждает действие и затем видит, что запись появилась в `pokemon_catalog`.

**Acceptance Scenarios**:

1. **Given** superadmin заполнил все обязательные поля нового покемона, **When** бот валидирует данные, **Then** он показывает итоговый экран подтверждения.
2. **Given** superadmin подтверждает создание, **When** операция успешна, **Then** новая запись создаётся в `pokemon_catalog`.
3. **Given** `pokemon_id` уже занят или поля невалидны, **When** бот валидирует запрос, **Then** он отклоняет операцию с явной ошибкой.
4. **Given** superadmin отменяет подтверждение, **When** бот закрывает операцию, **Then** в каталог не вносится никаких изменений.

---

### User Story 4 - Upload and manage pokemon images through Telegram (Priority: P1)

Superadmin может отправить изображение боту, загрузить его в MinIO, создать `image_credit`, привязать его к существующему покемону как variant, изменить `source`, default-variant и порядок отображения.

**Why this priority**: После появления image variants админ-бот должен уметь администрировать весь image-pipeline end-to-end.

**Independent Test**: Superadmin отправляет изображение `Cloyster`, выбирает `pokemon_id`, задаёт source, подтверждает действие и затем видит новый variant у покемона.

**Acceptance Scenarios**:

1. **Given** superadmin отправляет картинку боту как photo или document, **When** бот получает файл, **Then** он может использовать его как вход для создания нового image variant.
2. **Given** superadmin выбирает существующего покемона и задаёт metadata изображения, **When** бот показывает подтверждение, **Then** он описывает, что файл будет загружен в MinIO и привязан к species.
3. **Given** superadmin подтверждает добавление изображения, **When** операция завершается успешно, **Then** бот создаёт `image_credit`, загружает объект в MinIO и создаёт mapping в `pokemon_image_variants`.
4. **Given** superadmin редактирует `image source` существующего варианта, **When** операция подтверждается, **Then** бот обновляет `image_credits.source`.
5. **Given** superadmin меняет `display_order` или `is_default`, **When** операция подтверждается, **Then** порядок и default variant обновляются без нарушения уникальных ограничений.

---

### User Story 5 - Confirm and audit every admin mutation (Priority: P1)

Любое изменяющее действие должно сначала показывать описание последствий, а после подтверждения логироваться в аудит.

**Why this priority**: Это основной safety layer для админ-бота.

**Independent Test**: Инициировать любую изменяющую операцию, увидеть подтверждение, подтвердить её и затем проверить наличие audit trail.

**Acceptance Scenarios**:

1. **Given** superadmin инициирует изменяющую операцию, **When** бот показывает preview, **Then** в нём явно написано, что произойдёт после подтверждения.
2. **Given** superadmin нажимает `Подтвердить`, **When** операция проходит, **Then** бот пишет итог операции и фиксирует audit record.
3. **Given** superadmin нажимает `Отмена`, **When** бот закрывает pending action, **Then** изменений в БД и MinIO не происходит.
4. **Given** операция падает посередине, **When** бот получает ошибку, **Then** он показывает ошибку superadmin и пишет audit/log запись о неуспешной операции.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run as a separate Telegram bot with its own token and entrypoint.
- **FR-002**: System MUST allow access only to Telegram user ids listed in env configuration.
- **FR-003**: System MUST restrict all admin-bot usage to private chats only.
- **FR-004**: System MUST expose button-driven admin flows rather than command-only UX for the primary operations.
- **FR-005**: System MUST require explicit confirmation before every mutating operation.
- **FR-006**: System MUST show a human-readable description of what will happen before confirmation.
- **FR-007**: System MUST support granting currency to a target user identified by `@username`.
- **FR-008**: System MUST support granting a pokemon to a target user identified by `@username` and a concrete `pokemon_id`.
- **FR-009**: System MUST support creating a new pokemon species with the full set of catalog fields.
- **FR-010**: System MUST support receiving uploaded images from Telegram as either photo or document.
- **FR-011**: System MUST upload accepted admin images into the same MinIO/S3 storage used by the main application.
- **FR-012**: System MUST create or update `image_credits` records for uploaded images.
- **FR-013**: System MUST support attaching a new image to an existing pokemon species as an image variant.
- **FR-014**: System MUST support editing `image_credits.source` for an existing image variant.
- **FR-015**: System MUST support editing image-variant order and default flag for a pokemon species.
- **FR-016**: System MUST use the same PostgreSQL database and S3/MinIO credentials as the main application.
- **FR-017**: System MUST validate user existence, pokemon existence, and operation arguments before showing the confirmation screen.
- **FR-018**: System MUST cancel pending admin actions cleanly if the user declines the confirmation or the flow expires.
- **FR-019**: System MUST record an audit trail for every attempted mutating operation, including actor, target, action type, inputs, result, and timestamp.
- **FR-020**: System SHOULD expose structured logs for every admin action and confirmation step.
- **FR-021**: System MUST keep dangerous operations transactional where possible so partial DB updates do not silently succeed.
- **FR-022**: System MUST return clear user-facing errors when target `@username`, `pokemon_id`, or uploaded image metadata is invalid.
- **FR-023**: System MUST support image-management actions for the multi-variant pokemon image system introduced in feature `009-pokemon-image-variants`.
- **FR-024**: System MUST NOT expose admin features to the main public bot.

### Key Entities *(include if feature involves data)*

- **Admin Actor**: A Telegram user whose id is present in `ADMIN_BOT_ALLOWED_IDS` and is allowed to execute privileged actions.
- **Admin Pending Action**: A staged mutation waiting for explicit confirmation, including full preview payload and expiry metadata.
- **Admin Audit Record**: A durable record of one attempted or completed privileged action with actor, parameters, result, and timestamps.
- **Admin Image Upload**: A Telegram-delivered image payload that can be persisted to MinIO and linked to `image_credits`.
- **Admin Pokemon Draft**: A full set of pokemon catalog fields prepared for creation before final confirmation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Только пользователи из env-based allowlist могут открыть и использовать админ-бота.
- **SC-002**: Любое изменяющее действие сначала показывает экран подтверждения с описанием последствий.
- **SC-003**: Superadmin может выдать валюту и покемона целевому пользователю через один Telegram flow без прямого доступа к SQL.
- **SC-004**: Superadmin может создать нового покемона через бот без ручного редактирования БД.
- **SC-005**: Superadmin может загрузить изображение через Telegram и привязать его к existing species как новый image variant.
- **SC-006**: После любой админ-операции существует audit trail, по которому можно понять кто, что и когда сделал.

## Decisions Locked

- **DL-001**: Список superadmin хранится в env, не в отдельной БД-таблице.
- **DL-002**: Это отдельный бот с отдельным токеном.
- **DL-003**: Админ-бот используется только в личке.
- **DL-004**: На первой версии есть только один уровень доступа: `superadmin`.
- **DL-005**: Основной UX строится на кнопках, а не на command-first интерфейсе.
- **DL-006**: Любое изменяющее действие требует подтверждения с описанием эффекта.
- **DL-007**: Идентификация target-user в первой версии идёт по `@username`.
- **DL-008**: Создание нового покемона требует полный набор полей каталога.
- **DL-009**: Загрузка изображений поддерживает обычные Telegram photo и document.
- **DL-010**: Image-management в админ-боте обязан уметь работать с image variants, source, order и default.
