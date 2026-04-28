# Feature Specification: Admin Bot Operations

**Feature Branch**: `012-admin-bot-ops`  
**Created**: 2026-04-29  
**Status**: Draft  
**Input**: User description: "для админ-бота нужно добавить просмотр и экспорт аудита, точечное редактирование вида покемона и рассылку текстового сообщения по групповым чатам, где бот сейчас состоит"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View and export admin audit records (Priority: P1)

Superadmin может открыть аудит в админ-боте, посмотреть последние записи и выгрузить их наружу в удобном текстовом формате.

**Why this priority**: После появления большого числа privileged actions нужен операционный обзор без ручного SQL.

**Independent Test**: Superadmin открывает раздел аудита, видит последние записи, затем нажимает экспорт и получает файл или текстовую выгрузку с теми же записями.

**Acceptance Scenarios**:

1. **Given** superadmin открывает раздел аудита, **When** бот запрашивает данные, **Then** он показывает последние записи `admin_action_audit` с actor, action, status и timestamp.
2. **Given** записей много, **When** superadmin просматривает аудит, **Then** бот отдаёт ограниченный и читаемый срез вместо бесконечного текста.
3. **Given** superadmin выбирает экспорт аудита, **When** бот формирует выгрузку, **Then** он отправляет export в пригодном для чтения формате без ручного доступа к БД.
4. **Given** в аудите нет записей, **When** superadmin открывает раздел, **Then** бот показывает empty state вместо ошибки.

---

### User Story 2 - Edit an existing pokemon species safely (Priority: P1)

Superadmin может точечно редактировать вид покемона в `pokemon_catalog`, не пересоздавая его целиком.

**Why this priority**: Каталог уже живой, и дальше чаще нужны точечные исправления, а не только создание новых видов.

**Independent Test**: Superadmin выбирает поле у существующего `pokemon_id`, меняет значение, подтверждает действие и видит обновление в `pokemon_catalog`.

**Acceptance Scenarios**:

1. **Given** superadmin выбирает точечное редактирование покемона, **When** бот получает существующий `pokemon_id`, **Then** он даёт выбрать поддерживаемое поле вида.
2. **Given** superadmin указывает новое значение, **When** бот валидирует его, **Then** он показывает confirmation preview с текущим и новым значением.
3. **Given** superadmin подтверждает изменение, **When** операция проходит успешно, **Then** бот обновляет только выбранное поле вида покемона.
4. **Given** `pokemon_id` не существует или новое значение невалидно, **When** бот валидирует ввод, **Then** он отклоняет операцию с явной ошибкой и без записи в каталог.
5. **Given** superadmin отменяет операцию, **When** бот закрывает flow, **Then** никаких изменений в `pokemon_catalog` не происходит.

---

### User Story 3 - Broadcast a text message to group chats where the bot is present (Priority: P1)

Superadmin может отправить confirmable текстовую рассылку по групповым и супергрупповым чатам, где основной бот сейчас состоит.

**Why this priority**: Операционные объявления и быстрые коммуникации с пользователями не должны требовать ручного обхода чатов.

**Independent Test**: Superadmin набирает текст рассылки, видит preview с количеством целевых чатов, подтверждает действие и получает итог по числу успешных и неуспешных отправок.

**Acceptance Scenarios**:

1. **Given** superadmin запускает рассылку, **When** он отправляет текст сообщения, **Then** бот строит preview с числом целевых group/supergroup чатов.
2. **Given** целевой список пуст, **When** бот пытается построить preview, **Then** он сообщает, что подходящих чатов нет, и не создаёт pending mutation.
3. **Given** superadmin подтверждает рассылку, **When** бот отправляет сообщения, **Then** он шлёт текст только в групповые и супергрупповые чаты, где основной бот сейчас состоит.
4. **Given** часть чатов недоступна или Telegram вернул ошибки, **When** рассылка завершается, **Then** бот показывает итог с успешными и неуспешными отправками и фиксирует это в аудите.
5. **Given** superadmin отменяет рассылку на этапе preview, **When** pending action закрывается, **Then** ни в один чат ничего не отправляется.

---

### User Story 4 - Confirm and audit operational admin actions (Priority: P1)

Любой новый operational action в админ-боте должен подтверждаться и попадать в аудит так же строго, как существующие выдачи и image flows.

**Why this priority**: Новый operational surface нельзя добавлять в обход уже выстроенной safety-модели.

**Independent Test**: Инициировать просмотр/экспорт аудита, редактирование покемона и рассылку, проверить preview, confirm/cancel поведение и audit trail.

**Acceptance Scenarios**:

1. **Given** superadmin запускает mutate-операцию, **When** бот показывает preview, **Then** текст явно описывает последствия подтверждения.
2. **Given** superadmin подтверждает mutate-операцию, **When** она завершается, **Then** бот пишет понятный итог и добавляет audit record.
3. **Given** superadmin отменяет операцию, **When** pending action закрывается, **Then** мутирующее действие не выполняется и это отражается в аудите.
4. **Given** действие падает в процессе, **When** бот ловит ошибку, **Then** он возвращает operator-friendly error и записывает failure в аудит.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose an admin-audit browse flow inside the existing admin bot.
- **FR-002**: System MUST show recent `admin_action_audit` entries in a bounded, human-readable format.
- **FR-003**: System MUST support exporting admin audit data from the bot without requiring direct database access.
- **FR-004**: System MUST support editing an existing pokemon species in `pokemon_catalog` through point edits rather than full recreation.
- **FR-005**: System MUST support selecting a concrete supported field before editing a pokemon species.
- **FR-006**: System MUST validate `pokemon_id`, field name, and new field value before confirmation.
- **FR-007**: System MUST show confirmation preview for pokemon-species edits with the target field and new value.
- **FR-008**: System MUST support broadcasting plain text messages to group and supergroup chats only.
- **FR-009**: System MUST scope broadcast targets to chats where the main bot is currently present.
- **FR-010**: System MUST show a dry-run preview for broadcasts that includes target chat count before confirmation.
- **FR-011**: System MUST return a post-broadcast summary with success/failure counts.
- **FR-012**: System MUST reuse the existing admin pending-action and audit frameworks introduced in feature `010-admin-bot`.
- **FR-013**: System MUST record audit trail entries for pokemon-species edits and broadcast attempts, including partial failures.
- **FR-014**: System MUST preserve private-chat-only and env-allowlist access restrictions from the existing admin bot.
- **FR-015**: System SHOULD keep broadcast delivery bounded and operator-friendly, preferring one staged batch run over an unbounded free-form worker flow.

### Key Entities *(include if feature involves data)*

- **Admin Audit View**: A bounded operator-facing representation of recent `admin_action_audit` rows.
- **Admin Audit Export**: A serialized export of audit records suitable for download or copyable inspection.
- **Admin Species Edit Draft**: A staged point-edit action for one `pokemon_catalog` field on one species.
- **Admin Broadcast Draft**: A staged text-only outbound message prepared for delivery to qualifying group chats.
- **Broadcast Target Chat**: A group or supergroup chat where the main bot is currently present and eligible for operational messages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Superadmin can browse recent audit records directly from the admin bot.
- **SC-002**: Superadmin can export audit data from the admin bot without running SQL manually.
- **SC-003**: Superadmin can edit a single field of an existing pokemon species through a confirmed Telegram flow.
- **SC-004**: Superadmin can send a confirmed plain-text broadcast to eligible group chats and receive delivery summary counts.
- **SC-005**: Every new mutating operation added by this feature still uses confirmation and produces an audit trail.

## Decisions Locked

- **DL-001**: Audit support in this feature means `view + export`, not only raw persistence.
- **DL-002**: Pokemon editing in this feature targets species rows, not user-owned instances.
- **DL-003**: Species editing uses point edits, not full recreate/edit-all-at-once flows.
- **DL-004**: Broadcast targets are only group/supergroup chats where the main bot is currently present.
- **DL-005**: Broadcast payloads are text-only in the first version.
- **DL-006**: Broadcast flow must always include a dry-run/preview step before confirmation.
