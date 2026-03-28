# Feature Specification: Market System

**Feature Branch**: `006-market-system`  
**Created**: 2026-03-20  
**Status**: Draft  
**Input**: User description: "сделать рынок, где пользователи могут продавать и покупать покемонов за pokecoin; у каждого максимум 2 активных слота продажи; на лоты списывается комиссия 1% в день, первый день сразу; при нехватке баланса лот снимается и покемон возвращается; в покупке нужны фильтры по редкости и опция показывать только доступные по балансу; при продаже показываются чужие заявки на покупку; пользователи могут оставлять заявки на покупку; нужна кнопка мои лоты с возможностью снять лот; вход в рыночный flow должен идти с карточки покемона через кнопку `Рынок` и через командный сценарий"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse active sale listings and buy pokemon (Priority: P1)

Пользователь открывает рынок, переходит в раздел покупки и просматривает активные лоты других игроков, чтобы купить конкретного покемона за `pokecoin`.

**Why this priority**: Это основное назначение рынка. Без просмотра и покупки активных лотов рынок не выполняет свою главную функцию.

**Independent Test**: Открыть `Рынок -> Купить`, увидеть список активных лотов других игроков, применить фильтры и успешно купить доступного по балансу покемона.

**Acceptance Scenarios**:

1. **Given** пользователь открывает рынок, **When** он нажимает `Купить`, **Then** бот показывает активные лоты других пользователей, отсортированные по умолчанию от новых к старым.
2. **Given** у пользователя есть `pokecoin`, **When** он нажимает кнопку покупки по конкретному лоту, **Then** бот списывает цену лота с покупателя, переводит покемона покупателю и завершает лот.
3. **Given** пользователь пытается купить свой собственный лот, **When** бот проверяет владельца лота, **Then** покупка отклоняется.
4. **Given** у пользователя недостаточно `pokecoin`, **When** он пытается купить лот, **Then** бот отклоняет покупку и не меняет лот.
5. **Given** два пользователя одновременно пытаются купить один и тот же лот, **When** один из них успевает первым, **Then** только одна покупка завершается успешно, а второй получает отказ.

---

### User Story 2 - Filter market listings while buying (Priority: P1)

Пользователь может сужать список лотов при покупке по редкости, по доступности по балансу и по сортировке.

**Why this priority**: Без фильтрации длинный список лотов быстро становится неудобным.

**Independent Test**: Открыть `Купить`, включить фильтр по редкости, включить `только доступные по балансу`, переключить сортировку и убедиться, что список меняется корректно.

**Acceptance Scenarios**:

1. **Given** пользователь открыл раздел покупки, **When** он включает фильтр по редкости, **Then** бот показывает только лоты с выбранной редкостью.
2. **Given** пользователь включает фильтр `только хватает`, **When** бот пересчитывает список, **Then** остаются только лоты, цена которых не превышает текущий баланс пользователя в `pokecoin`.
3. **Given** пользователь меняет сортировку на `сначала дешёвые`, **When** бот рендерит список, **Then** лоты сортируются по цене по возрастанию.
4. **Given** фильтры не выбраны, **When** бот показывает раздел покупки, **Then** по умолчанию используется сортировка `сначала новые`.

---

### User Story 2A - Open market action from a pokemon card (Priority: P1)

Пользователь открывает карточку покемона и запускает рыночный сценарий прямо из неё через кнопку `Рынок`.

**Why this priority**: Это основной UX-вход в рынок, который ты описал. Без него пользовательский сценарий будет ощущаться оторванным от карточек покемонов.

**Independent Test**: Открыть карточку покемона и нажать `Рынок`; если покемон есть у пользователя, бот предлагает продажу, если нет — создание заявки на покупку.

**Acceptance Scenarios**:

1. **Given** пользователь открыл карточку покемона, которым владеет, **When** он нажимает `Рынок`, **Then** бот запускает сценарий продажи именно этого покемона.
2. **Given** пользователь открыл карточку покемона, которым не владеет, **When** он нажимает `Рынок`, **Then** бот запускает сценарий создания заявки на покупку именно этого покемона.
3. **Given** пользователь запускает рыночный сценарий из карточки, **When** бот просит цену, **Then** он принимает её через командный ввод, а затем показывает короткое подтверждение.

---

### User Story 3 - Create and maintain sale listings (Priority: P1)

Пользователь может выставить принадлежащего ему покемона на продажу за `pokecoin`, видеть свои активные лоты и снимать их вручную.

**Why this priority**: Без возможности выставить покемона рынок не наполняется предложением.

**Independent Test**: Создать лот на конкретного покемона, увидеть его в `Мои лоты`, затем снять лот и убедиться, что покемон вернулся владельцу.

**Acceptance Scenarios**:

1. **Given** пользователь владеет конкретным экземпляром покемона, **When** он выставляет его на продажу, **Then** создаётся лот на этот экземпляр, а сам покемон становится недоступен для других действий рынка.
2. **Given** пользователь пытается выставить заблокированного покемона, **When** бот валидирует выбор, **Then** лот не создаётся.
3. **Given** у пользователя уже есть 2 активных лота, **When** он пытается выставить третий, **Then** бот отклоняет создание лота.
4. **Given** пользователь создаёт лот, **When** бот сохраняет его, **Then** первый день комиссии списывается сразу с баланса в `pokecoin`.
5. **Given** пользователь открывает `Мои лоты`, **When** бот рендерит экран, **Then** он показывает только активные лоты пользователя и кнопку снятия для каждого.
6. **Given** пользователь снимает свой активный лот, **When** бот завершает действие, **Then** покемон сразу возвращается владельцу без дополнительного списания комиссии.
7. **Given** пользователь запускает продажу из карточки покемона, **When** бот просит цену, **Then** пользователь вводит её командой, а затем видит короткое подтверждение с информацией, хватает ли ему средств на стартовую комиссию.

---

### User Story 4 - Keep listing commission and auto-remove unpaid listings (Priority: P1)

Система ежедневно списывает комиссию `1%` от цены активного лота, а при нехватке баланса автоматически снимает лот и возвращает покемона владельцу.

**Why this priority**: Это обязательное экономическое правило рынка и ключевое ограничение для удержания лотов.

**Independent Test**: Создать лот, дождаться/смоделировать следующий расчёт комиссии, проверить списание; затем обнулить баланс ниже комиссии и убедиться, что лот автоматически снимается.

**Acceptance Scenarios**:

1. **Given** пользователь выставляет лот, **When** лот создаётся, **Then** система сразу списывает первую дневную комиссию `1%` от стоимости лота.
2. **Given** активный лот пережил ещё одни сутки, **When** запускается ежедневный расчёт комиссии, **Then** система пытается списать очередной `1%` от цены лота.
3. **Given** у владельца лота недостаточно `pokecoin` для очередного списания, **When** запускается ежедневный расчёт комиссии, **Then** лот автоматически снимается, а покемон возвращается владельцу.
4. **Given** активный лот достиг возраста `5` дней, **When** истекает срок жизни лота, **Then** лот снимается и пользователь должен создать его заново, если хочет продолжить продажу.

---

### User Story 5 - Sell to existing buy requests (Priority: P2)

Пользователь может открыть раздел продажи и увидеть чужие заявки на покупку конкретных покемонов, чтобы быстро продать подходящий экземпляр.

**Why this priority**: Это вторая половина рынка и удобный shortcut для прямой сделки без ручного ожидания покупателя.

**Independent Test**: Один пользователь создаёт заявку на покупку конкретного покемона, другой открывает `Продать`, видит эту заявку и продаёт свой экземпляр.

**Acceptance Scenarios**:

1. **Given** в системе есть активные заявки на покупку, **When** пользователь нажимает `Продать`, **Then** бот показывает чужие заявки на конкретных покемонов.
2. **Given** пользователь пытается закрыть свою собственную заявку, **When** бот проверяет владельца заявки, **Then** действие отклоняется.
3. **Given** у пользователя есть подходящий незалоченный экземпляр покемона, **When** он принимает заявку, **Then** покемон передаётся покупателю, а `pokecoin` переводятся продавцу.
4. **Given** у пользователя нет подходящего экземпляра или покемон заблокирован, **When** он пытается закрыть заявку, **Then** действие отклоняется.

---

### User Story 6 - Create and keep buy requests (Priority: P2)

Пользователь может оставлять заявки на покупку конкретных покемонов за `pokecoin` и держать не более `5` активных заявок одновременно.

**Why this priority**: Без заявок на покупку раздел `Продать` неполон и не выполняет свою роль.

**Independent Test**: Создать заявку на конкретного покемона, увидеть её активной, затем принять её другим пользователем или снять/закрыть её по лимиту.

**Acceptance Scenarios**:

1. **Given** пользователь хочет купить конкретного покемона, **When** он создаёт заявку, **Then** система сохраняет цену в `pokecoin` и конкретный `pokemon_catalog.id`.
2. **Given** у пользователя уже есть `5` активных заявок на покупку, **When** он пытается создать ещё одну, **Then** бот отклоняет действие.
3. **Given** пользователь создаёт заявку на покупку, **When** другой пользователь открывает `Продать`, **Then** эта заявка появляется в списке доступных чужих заявок.
4. **Given** пользователь создаёт заявку на покупку, **When** бот принимает цену, **Then** нужная сумма `pokecoin` резервируется сразу.
5. **Given** пользователь отменяет свою заявку на покупку, **When** бот снимает заявку, **Then** зарезервированные `pokecoin` возвращаются пользователю.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated market root screen with at least `Купить`, `Продать`, and `Мои лоты`.
- **FR-001A**: System MUST provide a market entry action from a pokemon card through a `Рынок` button.
- **FR-002**: System MUST use `pokecoin` as the only market currency in version 1.
- **FR-003**: System MUST treat a sale listing as a listing of a concrete pokemon instance from `user_pokemon`, not a species template.
- **FR-004**: System MUST allow listing any owned, unlocked pokemon instance, including the last remaining copy of that species.
- **FR-005**: System MUST forbid listing locked pokemon.
- **FR-006**: System MUST prevent a user from having more than `2` active sale listings at the same time.
- **FR-007**: System MUST charge a listing commission equal to `1%` of the listing price per day in `pokecoin`.
- **FR-008**: System MUST charge the first day commission immediately when the listing is created.
- **FR-009**: System MUST run recurring commission checks once per day for active listings.
- **FR-010**: System MUST automatically remove a listing and return the pokemon to its owner if the owner cannot pay the next daily commission.
- **FR-011**: System MUST limit a sale listing lifetime to `5` days, after which the user must recreate it manually.
- **FR-012**: System MUST return the pokemon to its owner immediately when the owner manually removes the listing.
- **FR-013**: System MUST NOT charge an extra commission when a user manually removes a listing after the currently paid day has already been charged.
- **FR-014**: System MUST show only active listings from other users in the `Купить` view.
- **FR-015**: System MUST support filtering active sale listings by rarity.
- **FR-016**: System MUST support filtering active sale listings to only those affordable by the current user’s `pokecoin` balance.
- **FR-017**: System MUST support sorting active sale listings at least by `newest first` and `cheapest first`.
- **FR-018**: System MUST default the `Купить` view to `newest first`.
- **FR-019**: System MUST prevent a user from buying their own listing.
- **FR-020**: System MUST prevent a listing purchase when the buyer does not have enough `pokecoin`.
- **FR-021**: System MUST transfer the sold pokemon to the buyer and the price to the seller atomically.
- **FR-022**: System MUST ensure only one buyer can successfully purchase a listing.
- **FR-023**: System MUST provide a `Мои лоты` screen that shows only the user’s active sale listings.
- **FR-024**: System MUST allow removing an active listing from `Мои лоты`.
- **FR-025**: System MUST support buy requests for a concrete `pokemon_catalog.id` and a concrete `pokecoin` price.
- **FR-026**: System MUST prevent a user from having more than `5` active buy requests at the same time.
- **FR-027**: System MUST show only other users’ active buy requests in the `Продать` view.
- **FR-028**: System MUST prevent a user from accepting their own buy request.
- **FR-029**: System MUST prevent a user from fulfilling a buy request with a locked pokemon.
- **FR-030**: System MUST allow fulfilling a buy request only with a matching owned pokemon instance.
- **FR-031**: System MUST transfer the pokemon to the buy-request owner and transfer the `pokecoin` to the seller atomically when a request is fulfilled.
- **FR-032**: System MUST provide a way to create buy requests for a concrete pokemon from a card-based and command-based flow.
- **FR-033**: System MUST send user-facing confirmations at least for successful listing creation and successful purchase.
- **FR-034**: System MUST preserve market integrity across concurrent clicks and repeated callbacks.
- **FR-035**: System SHOULD keep list screens compact and pagination-friendly in Telegram UI.
- **FR-036**: System MUST request sale price and buy-request price through a command-based text input flow and then show a short confirmation before finalizing.
- **FR-037**: System MUST tell the seller during listing confirmation whether the current `pokecoin` balance is sufficient for the initial `1%` commission.
- **FR-038**: System MUST reserve the full `pokecoin` amount immediately when a buy request is created.
- **FR-039**: System MUST return the reserved `pokecoin` amount when the user cancels an active buy request.
- **FR-040**: System MUST provide a `Мои заявки` screen for managing the user’s own active buy requests.
- **FR-041**: System MUST allow the user to manually cancel their own active buy request.
- **FR-042**: System MUST show only buy requests that the current user can actually fulfill in the `Продать` view.
- **FR-043**: System MUST show remaining listing lifetime in days on the user-facing listing-management screens.
- **FR-044**: System SHOULD reuse a shared pokemon-card rendering layer for market, profile, collection, search, and encounter flows, while allowing shop-specific card rendering to stay separate.
- **FR-045**: System MUST use two separate command syntaxes for price entry: one for sale listing price input and one for buy-request price input.
- **FR-046**: System MUST support market access without a dedicated request-only command by relying on the market root screen and pokemon-card entry points.

### Key Entities *(include if feature involves data)*

- **Market Listing**: Active sale offer for one specific `user_pokemon` instance, including seller, price, creation time, next commission checkpoint, and status.
- **Buy Request**: Active request to purchase one concrete pokemon species (`pokemon_catalog.id`) for a specific `pokecoin` amount.
- **Reserved Buy Funds**: Locked `pokecoin` amount held for an active buy request until it is fulfilled or canceled.
- **Market Slot Usage**: Per-user limits for active sale listings (`2`) and active buy requests (`5`).
- **Commission Cycle**: Recurring billing state that tracks when the next `1%` listing commission must be charged.
- **Market Browse Filter**: Read-model state for rarity filter, affordability filter, and sort mode in the `Купить` flow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Пользователь может открыть рынок и за один экранный flow перейти либо к покупке, либо к продаже, либо к своим лотам.
- **SC-002**: Пользователь не может держать более `2` активных лотов на продажу и более `5` активных заявок на покупку.
- **SC-003**: При создании лота первая комиссия `1%` списывается сразу и не теряется при ручном снятии лота в течение уже оплаченного дня.
- **SC-004**: Если у владельца лота не хватает `pokecoin` на следующий ежедневный платёж, лот автоматически снимается, а покемон возвращается владельцу.
- **SC-005**: Пользователь может включить фильтры `по редкости` и `только хватает`, и список покупки обновляется без показа неподходящих лотов.
- **SC-006**: Лот нельзя купить дважды, и один покемон не может одновременно участвовать в нескольких активных рыночных операциях.
- **SC-007**: Пользователь может продать покемона как через собственный лот, так и через закрытие чужой заявки на покупку.
- **SC-008**: Пользователь может запустить рыночный сценарий прямо из карточки покемона, и бот корректно различает сценарии `продать` и `создать заявку`.

## Decisions Locked

- **DL-001**: Для ввода цены используются две разные команды: отдельная для продажи и отдельная для заявки на покупку.
- **DL-002**: Отдельная команда только для заявок не требуется; в первой версии достаточно входа через карточку покемона и основной экран рынка.
