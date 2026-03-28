# Feature Specification: Chat Pokemon Encounters

**Feature Branch**: `004-chat-encounters`  
**Created**: 2026-03-17  
**Status**: Draft  
**Input**: User description: "в чатах иногда прибегает покемон; кто первый нажал, тот пытается поймать; если не поймал, может пробовать другой пользователь; в личных сообщениях функция не работает; есть 3 тира покеболов; спавн после кулдауна 4 часа и только после 10 сообщений или команды find"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Spawn a wild pokemon encounter in a group chat (Priority: P1)

После выполнения условий в групповом чате бот публикует encounter-сообщение с изображением покемона и кнопками поимки.

**Why this priority**: Без самого появления покемона вся механика ловли не существует.

**Independent Test**: Включить encounter flow в групповом чате, выполнить условия спавна и убедиться, что бот отправляет сообщение с изображением, текстом вида "кто-то пришёл..." и кнопками покеболов.

**Acceptance Scenarios**:

1. **Given** с момента прошлого появления покемона в чате прошло не меньше 4 часов, **When** после этого в чате набирается 10 новых сообщений, **Then** бот может сгенерировать нового покемона в этом чате.
2. **Given** с момента прошлого появления покемона в чате прошло не меньше 4 часов, **When** пользователь в этом чате вызывает команду `find`, **Then** бот может сгенерировать нового покемона в этом чате без ожидания 10 сообщений.
3. **Given** покемон появляется в чате, **When** бот публикует encounter, **Then** в сообщении видны только изображение покемона, короткий текст вроде `Кто-то пришёл...`, и кнопки доступных покеболов.
4. **Given** encounter-trigger приходит из личного чата, **When** бот проверяет контекст, **Then** механика encounter не активируется и в личных сообщениях не поддерживается.

---

### User Story 2 - Let any chat member try to catch the encountered pokemon (Priority: P1)

Любой участник чата может нажать на кнопку покебола и попытаться поймать прибежавшего покемона, в отличие от обычных menu-кнопок, которые привязаны к одному пользователю.

**Why this priority**: Это ключевое отличие encounter-механики от остальной навигации бота.

**Independent Test**: Отправить encounter в групповом чате и убедиться, что разные пользователи могут по очереди пытаться ловить одного и того же покемона.

**Acceptance Scenarios**:

1. **Given** в чате активен encounter, **When** любой участник чата нажимает на кнопку покебола, **Then** бот принимает попытку независимо от того, кто открыл или увидел сообщение первым.
2. **Given** пользователь уже пытался поймать текущего encounter-покемона, **When** он снова нажимает любую encounter-кнопку, **Then** бот не даёт ему вторую попытку в рамках этого же encounter.
3. **Given** один пользователь не смог поймать покемона, **When** другой пользователь нажимает кнопку покебола, **Then** бот разрешает следующую попытку на того же encounter-покемона.

---

### User Story 3 - Resolve encounter capture using ball tiers and rarity-based spawn odds (Priority: P1)

Encounter-покемон выбирается по тем же шансам редкости, что и в гаче, а результат поимки зависит от выбранного типа покебола.

**Why this priority**: Это главный игровой цикл новой функции.

**Independent Test**: Зафиксировать encounter покемона, выполнить попытки разными покеболами и убедиться, что используются корректный покемон, правильные кнопки и корректный исход попытки.

**Acceptance Scenarios**:

1. **Given** бот создаёт нового encounter-покемона, **When** он выбирает вид покемона, **Then** редкость выбирается с теми же шансами, что и в магазине/гаче.
2. **Given** encounter активен, **When** пользователь выбирает `обычный покебол`, `ультрабол` или `мастербол`, **Then** бот рассчитывает результат попытки по правилам для выбранного тира покебола.
3. **Given** попытка поимки успешна, **When** бот завершает encounter, **Then** покемон добавляется в коллекцию поймавшего пользователя, а encounter в чате закрывается.
4. **Given** попытка поимки неуспешна, **When** бот завершает попытку, **Then** encounter остаётся активным для других пользователей, пока покемон не будет пойман или encounter не завершится по другим правилам.
5. **Given** пользователь не смог поймать encounter-покемона, **When** бот завершает попытку, **Then** бот показывает краткое всплывающее уведомление через callback answer без отдельного нового сообщения в чат.
6. **Given** пользователь успешно поймал encounter-покемона, **When** бот завершает encounter, **Then** исходное encounter-сообщение редактируется так, чтобы вместо старого текста и кнопок было написано, какой именно это был покемон и кто его поймал.

---

### User Story 4 - Respect chat cooldown and hidden spawn progression (Priority: P2)

Пользователи не видят кулдаун появления, но encounter не должен появляться чаще разрешённого интервала.

**Why this priority**: Это защищает групповые чаты от спама и удерживает игровую петлю под контролем.

**Independent Test**: Сымитировать повторные сообщения в одном и том же чате и убедиться, что до истечения 4 часов новый encounter не появляется, даже если счётчик сообщений уже набран.

**Acceptance Scenarios**:

1. **Given** в чате недавно уже появлялся encounter, **When** пользователи продолжают писать сообщения или вызывают `find`, **Then** до истечения 4 часов новый encounter не появляется.
2. **Given** кулдаун в 4 часа истёк, **When** в чате ещё не набралось 10 новых сообщений и никто не вызывал `search`, **Then** encounter не появляется автоматически.
3. **Given** encounter уже активен в чате, **When** приходят новые сообщения или вызывается `search`, **Then** бот не создаёт второй активный encounter поверх первого.
4. **Given** encounter появился в чате, **When** в течение 5 минут его никто не поймал, **Then** бот завершает encounter, убирает изображение и кнопки, и оставляет текст `Тут кто-то был...`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support pokemon encounter spawns only in non-private chats.
- **FR-002**: System MUST NOT activate encounter spawning in private dialogs with the bot.
- **FR-003**: System MUST track encounter cooldown separately per chat.
- **FR-004**: System MUST require at least 4 hours between encounter spawns in the same chat.
- **FR-005**: System MUST require either 10 new chat messages after cooldown expiry or an explicit `find` command in the chat to trigger the next encounter.
- **FR-006**: System MUST keep the encounter cooldown hidden from end users.
- **FR-007**: System MUST render an encounter as a chat message containing only the pokemon image, a short encounter text, and ball-choice buttons.
- **FR-008**: System MUST choose encountered pokemon rarity using the same rarity distribution already used by the gacha/shop flow.
- **FR-009**: System MUST allow any chat participant to press encounter buttons, regardless of who triggered or first opened the encounter message.
- **FR-010**: System MUST enforce at most one capture attempt per user for the same encounter.
- **FR-011**: System MUST keep the encounter open after a failed capture attempt so other users can continue trying.
- **FR-012**: System MUST close the encounter after a successful capture.
- **FR-013**: System MUST add a successfully caught pokemon to the catching user’s collection.
- **FR-014**: System MUST expose three ball choices in the encounter UI: regular pokeball, ultraball, and masterball.
- **FR-015**: System MUST treat the regular pokeball as infinitely available.
- **FR-016**: System MUST integrate ultraball and masterball availability with the existing user inventory model.
- **FR-017**: System MUST prevent a user from using a ball they do not currently have available.
- **FR-018**: System MUST use the following capture chances per attempt: regular pokeball `60%`, ultraball `80%`, masterball `100%`.
- **FR-019**: System MUST consume ultraball and masterball from user inventory on every encounter attempt, including failed attempts.
- **FR-020**: System MUST treat masterball as a guaranteed catch when the user has one available.
- **FR-021**: System MUST use the exact command name `/find` as the manual encounter trigger.
- **FR-022**: System MUST expire an active encounter 5 minutes after spawn if no one catches the pokemon.
- **FR-023**: System MUST edit the encounter message after timeout so that the image and buttons are removed and only a short text like `Тут кто-то был...` remains.
- **FR-024**: System MUST report failed catch attempts via Telegram callback-answer notification rather than a separate chat message.
- **FR-025**: System MUST edit the original encounter message on successful catch so that it shows which pokemon was caught and which user caught it instead of the old prompt and ball buttons.
- **FR-026**: System MUST keep encounter state consistent under concurrent clicks from multiple users in the same chat.
- **FR-027**: System MUST log spawn creation, catch attempts, successful captures, failed captures, timeout cleanup, and cooldown blocks with structured logs.
- **FR-028**: System MUST ensure only one active encounter exists per chat at a time.
- **FR-029**: System MUST provide a dedicated chat command `find` as an encounter trigger path after cooldown expiry.

### Key Entities *(include if feature involves data)*

- **Chat Encounter State**: Persistent per-chat state describing cooldown, active encounter status, encountered pokemon, and message counters since the last spawn.
- **Encounter Attempt**: One user’s single allowed catch attempt against a specific active encounter.
- **Encounter Pokemon**: The selected pokemon species and associated image/metadata shown in the encounter message.
- **Encounter Ball Choice**: The ball tier used for a catch attempt, including availability and capture rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: В групповом чате после выполнения условий спавна бот создаёт ровно один encounter без появления дубликатов.
- **SC-002**: Любой участник чата может нажать на кнопку encounter-покебола, даже если сообщение изначально увидел не он.
- **SC-003**: Один и тот же пользователь не может сделать вторую попытку поимки в рамках одного encounter.
- **SC-004**: После успешной поимки покемон появляется в коллекции поймавшего пользователя и encounter больше не принимает новые попытки.
- **SC-005**: До истечения 4 часов новый encounter в том же чате не появляется, даже если в чат пришло много сообщений.
- **SC-006**: Encounter never starts from private chat activity.
- **SC-007**: Если в течение 5 минут никто не поймал покемона, encounter автоматически завершается и сообщение меняется на текст про исчезнувшего покемона без кнопок.
