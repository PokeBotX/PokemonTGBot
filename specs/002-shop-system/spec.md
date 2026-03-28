# Feature Specification: Shop, Daily Bonus, and Gacha

**Feature Branch**: `002-shop-system`  
**Created**: 2026-03-11  
**Status**: Draft  
**Input**: User description: "магазин с валютой pokedollar, ежедневным бонусом, гачей на покемонов, pity-счётчиками, покупкой ультраболлов и мастерболлов, а также плейсхолдером для VIP"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the shop screen and see available actions (Priority: P1)

Пользователь открывает раздел магазина из главного меню и видит текущий баланс `pokedollar`, блок покупки, блок ежедневного бонуса, блок гачи и кнопку VIP-заглушку.

**Why this priority**: Без экрана магазина у пользователя нет точки входа в покупку предметов, крутки и получение бонуса.

**Independent Test**: Можно полностью проверить, если открыть магазин из меню и убедиться, что экран показывает баланс, кнопки покупки, кнопку бонуса, кнопку крутки и плейсхолдер VIP.

**Acceptance Scenarios**:

1. **Given** пользователь открыл главное меню, **When** он нажимает кнопку `🛒 Магазин`, **Then** бот обновляет текущее сообщение и показывает экран магазина.
2. **Given** пользователь находится в магазине, **When** экран магазина отрисовывается, **Then** бот показывает текст-приглашение вроде "Выберите желаемую опцию", затем текущий баланс `pokedollar`, прогресс pity для `Epic` и `Legendary`, блок покемонов, блок бонуса, блок предметов, кнопку VIP и кнопку возврата в меню.
3. **Given** пользователь находится в магазине, **When** он нажимает кнопку VIP, **Then** бот показывает плейсхолдер-сообщение вида "Скоро" и не меняет баланс, инвентарь или коллекцию.

---

### User Story 2 - Claim accumulated daily bonus (Priority: P1)

Пользователь может открыть магазин и забрать накопившийся ежедневный бонус в `pokedollar`.

**Why this priority**: Это основной бесплатный источник валюты, без него пользователь не сможет регулярно делать крутки и покупки.

**Independent Test**: Можно проверить отдельно от гачи, если начислить пользователю бонусное время, открыть магазин и забрать `pokedollar`.

**Acceptance Scenarios**:

1. **Given** у пользователя накопился доступный бонус, **When** он нажимает кнопку получения бонуса, **Then** бот начисляет `pokedollar` на баланс пользователя.
2. **Given** пользователь давно не забирал бонус, **When** бот рассчитывает накопление, **Then** сумма бонуса ограничивается максимумом `750 pokedollar`.
3. **Given** пользователь нажимает кнопку бонуса, **When** доступна хотя бы часть накопленного бонуса, **Then** нажатие сразу забирает бонус без дополнительного подтверждения и бот сообщает, сколько валюты начислено и сколько времени осталось до следующего доступного получения.
4. **Given** пользователь только что забрал бонус, **When** с момента выдачи прошло меньше одного часа, **Then** бот не начисляет валюту повторно и показывает, сколько осталось до следующего бонуса.

---

### User Story 3 - Buy shop items and gacha spins (Priority: P1)

Пользователь может тратить `pokedollar` на крутки, `ultraball` и `masterball`. Если денег недостаточно, недоступные варианты покупки не должны показываться как доступные действия.

**Why this priority**: Это основная петля траты валюты и подготовки к прогрессии через гачу.

**Independent Test**: Можно проверить, изменяя баланс пользователя и открывая магазин: доступны только те покупки, на которые хватает валюты.

**Acceptance Scenarios**:

1. **Given** у пользователя есть минимум `500 pokedollar`, **When** он открывает магазин, **Then** бот показывает кнопку покупки одной крутки.
2. **Given** у пользователя есть минимум `2500 pokedollar`, **When** он открывает магазин, **Then** бот показывает кнопку покупки `x5` круток.
3. **Given** у пользователя меньше `2500 pokedollar`, **When** он открывает магазин, **Then** кнопка покупки `x5` не отображается.
4. **Given** у пользователя есть минимум `200 pokedollar`, **When** он покупает `ultraball`, **Then** бот списывает `200 pokedollar` и увеличивает количество `ultraball` в инвентаре.
5. **Given** у пользователя есть минимум `1000 pokedollar`, **When** он покупает `masterball`, **Then** бот списывает `1000 pokedollar` и увеличивает количество `masterball` в инвентаре.
6. **Given** экран магазина открыт, **When** бот строит клавиатуру магазина, **Then** она содержит секцию покемонов с кнопками `Крутка x1` и `Крутка x5`, секцию бонуса с кнопкой получения бонуса, секцию предметов с кнопками `Ultraball` и `Masterball`, кнопку VIP и кнопку `Назад в меню`.

---

### User Story 4 - Receive a pokemon from gacha with rarity and pity rules (Priority: P1)

Пользователь делает крутку за `500 pokedollar` и получает случайного покемона в зависимости от редкости. Гача использует pity-счётчики для `Epic` и `Legendary`.

**Why this priority**: Это главная ценность магазина и основной источник пополнения коллекции.

**Independent Test**: Можно проверить отдельно от покупки предметов, если у пользователя есть валюта, каталог покемонов и настроенные pity-счётчики.

**Acceptance Scenarios**:

1. **Given** у пользователя есть минимум `500 pokedollar`, **When** он делает одну крутку, **Then** бот списывает `500 pokedollar`, выбирает случайного покемона по правилам редкости и добавляет его в коллекцию пользователя.
2. **Given** пользователь не выбил `Epic` за последние `14` круток, **When** он делает `15`-ю крутку, **Then** результат крутки гарантированно имеет редкость `Epic` или выше.
3. **Given** пользователь выбил покемона редкости `Epic` раньше 15-й крутки, **When** крутка успешно завершается, **Then** счётчик pity для `Epic` сбрасывается.
4. **Given** пользователь не выбил `Legendary` за последние `39` круток, **When** он делает `40`-ю крутку, **Then** результат крутки гарантированно имеет редкость `Legendary`.
5. **Given** пользователь выбил покемона редкости `Legendary` раньше 40-й крутки, **When** крутка успешно завершается, **Then** счётчик pity для `Legendary` сбрасывается.
6. **Given** крутка завершилась успешно, **When** бот отправляет результат, **Then** бот дополнительно отправляет отдельное сообщение с изображением покемона и его данными.
7. **Given** у покемона нет привязанного изображения, **When** бот отправляет сообщение с результатом, **Then** вместо отсутствующей картинки используется файл `image.png`.
8. **Given** пользователь сделал `x5` крутку, **When** все пять результатов определены, **Then** бот отправляет одно сводное сообщение со списком из пяти результатов, где для каждого результата показаны имя покемона и его редкость.
9. **Given** пользователь получил сводное сообщение по `x5` крутке, **When** он видит это сообщение, **Then** в нём доступны пять отдельных кнопок для просмотра подробной карточки каждого выпавшего покемона.

---

### User Story 5 - Track pity progress across sessions (Priority: P2)

Пользователь продолжает крутки в разные моменты времени, а pity-счётчики `Epic` и `Legendary` сохраняются между сессиями бота и между открытиями магазина.

**Why this priority**: Без сохранения pity-счётчиков система наград будет вести себя непредсказуемо и ломать ожидаемую прогрессию.

**Independent Test**: Можно проверить, если сделать часть круток, перезапустить приложение, затем убедиться, что pity продолжает считаться от сохранённого значения.

**Acceptance Scenarios**:

1. **Given** пользователь сделал несколько круток без `Epic`, **When** бот перезапускается, **Then** следующий экран магазина показывает прежний прогресс pity для `Epic`.
2. **Given** пользователь сделал несколько круток без `Legendary`, **When** бот перезапускается, **Then** pity для `Legendary` не обнуляется без причины.

---

### User Story 6 - Future premium button placeholder (Priority: P3)

Пользователь видит отдельную кнопку для VIP-функции, но на первом этапе она не содержит реальной логики покупок или преимуществ.

**Why this priority**: Кнопка нужна для совместимости с макетом интерфейса, но не влияет на основную экономику магазина.

**Independent Test**: Можно проверить отдельно, если нажать VIP и убедиться, что бот показывает только заглушку.

**Acceptance Scenarios**:

1. **Given** пользователь находится в магазине, **When** он нажимает кнопку VIP, **Then** бот сообщает, что функция пока недоступна.

## Edge Cases

- Каталог покемонов содержит достаточное количество покемонов всех четырёх редкостей, поэтому отсутствие покемона нужной редкости не рассматривается как сценарий первой версии.
- Что происходит, если у пользователя хватает денег на одну крутку, но не хватает на `x5`?
- Что происходит, если несколько нажатий на кнопку крутки приходят почти одновременно?
- Что происходит, если отдельное сообщение с результатом покемона не удалось отправить, но покемон уже выдан?
- Что происходит, если запись pity-счётчиков отсутствует для нового пользователя?
- Что происходит, если пользователь получает `Epic` на 15-й крутке и этот же результат одновременно должен считаться обычным шансом?
- Что происходит, если пользователь получает `Legendary` на 40-й крутке: сбрасывается только счётчик `Legendary`, а `Epic` pity не сбрасывается.
- Бонус накапливается линейно со скоростью `125 pokedollar` в час и ограничивается максимумом `750 pokedollar`.
- Более дорогая крутка по конкретной стихии не входит в первую версию магазина.
- Если пользователь нажимает кнопку бонуса раньше, чем прошёл один час с прошлого получения, бот не начисляет валюту и показывает только оставшееся время до следующего получения.
- Что происходит, если у пользователя хватает денег на `x5`, но не хватает места или данных для отправки пяти карточек просмотра [INFERENCE: probably summary still remains available]?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a shop section reachable from the existing main menu.
- **FR-002**: System MUST render the shop as a single message view containing at least the current `pokedollar` balance, purchase actions, daily bonus action, gacha action, and a VIP placeholder action.
- **FR-002**: System MUST render the shop as a single message view containing at least a short prompt like "Выберите желаемую опцию", the current `pokedollar` balance, visible pity counters for `Epic` and `Legendary`, pokemon purchase actions, daily bonus action, item purchase actions, a VIP placeholder action, and a return-to-menu action.
- **FR-003**: System MUST use `pokedollar` as the purchase currency for daily bonus rewards, gacha spins, `ultraball`, and `masterball`.
- **FR-004**: System MUST price one gacha spin at `500 pokedollar`.
- **FR-005**: System MUST price `ultraball` at `200 pokedollar`.
- **FR-006**: System MUST price `masterball` at `1000 pokedollar`.
- **FR-007**: System MUST show a purchase action for `x5` gacha spins only when the user balance is at least `2500 pokedollar`.
- **FR-008**: System MUST hide the `x5` gacha purchase action when the user balance is below `2500 pokedollar`.
- **FR-009**: System MUST grant `pokedollar` through an accumulated daily bonus flow.
- **FR-010**: System MUST cap unclaimed accumulated daily bonus at `750 pokedollar`.
- **FR-011**: System MUST persist enough bonus state to prevent duplicate claiming and to continue accumulation over time.
- **FR-011**: System MUST persist enough bonus state to prevent duplicate claiming, enforce a minimum one-hour interval between bonus claims, and continue accumulation over time.
- **FR-012**: System MUST select gacha rewards using rarity-based random distribution where `Legendary` has the lowest chance, `Epic` has a higher chance than `Legendary`, `Rare` has a higher chance than `Epic`, and `Common` has the highest chance.
- **FR-013**: System MUST use the following base rarity probabilities for normal gacha spins: `Legendary` `2.0%`, `Epic` `7.5%`, `Rare` `20.2%`, `Common` `70.3%`.
- **FR-014**: System MUST store each rewarded pokemon as a user-owned pokemon entry linked to the existing pokemon catalog.
- **FR-015**: System MUST maintain a pity counter for `Epic` rarity that guarantees an `Epic` or better result on the 15th spin if no `Epic` or better was obtained earlier.
- **FR-016**: System MUST reset the `Epic` pity counter whenever the user obtains an `Epic` pokemon.
- **FR-017**: System MUST maintain a pity counter for `Legendary` rarity that guarantees a `Legendary` result on the 40th spin if no `Legendary` was obtained earlier.
- **FR-018**: System MUST reset the `Legendary` pity counter whenever the user obtains a `Legendary` pokemon.
- **FR-019**: System MUST persist pity counters in the database so they survive bot restarts and later sessions.
- **FR-020**: System MUST support multi-spin purchase and execution for `x5` spins when the user has enough balance.
- **FR-020**: System MUST support multi-spin purchase and execution for `x5` spins when the user has enough balance, processing the five spins sequentially so pity counters update between each internal spin.
- **FR-021**: System MUST send a separate result message after each successful single-spin gacha reward showing the pokemon image and all currently available pokemon data.
- **FR-022**: System MUST use fallback file `image.png` when a rewarded pokemon has no linked image asset.
- **FR-023**: System MUST provide a VIP button in the shop UI as a non-functional placeholder in the first version.
- **FR-024**: System MUST not change user balance, items, or collection when the VIP placeholder is used.
- **FR-025**: System MUST create or extend database storage for shop-related state, including at minimum daily bonus accumulation and pity counters.
- **FR-026**: System MUST handle users with no existing shop state by creating default shop state on first shop access or first purchase attempt.
- **FR-027**: System MUST prevent a user from receiving a reward or spending currency twice from the same button press when duplicate callbacks arrive.
- **FR-028**: System MUST accumulate the daily bonus linearly at `125 pokedollar` per hour until it reaches the cap of `750 pokedollar`.
- **FR-029**: System MUST NOT include a type-targeted or element-targeted premium gacha spin in the first version of this feature.
- **FR-030**: System MUST organize the shop actions into the following visible groups: pokemon spins, daily bonus, items, VIP placeholder, and return to menu.
- **FR-031**: System MUST resolve the daily bonus immediately when the bonus button is pressed, without a separate confirmation screen.
- **FR-032**: System MUST show the amount received and the remaining time until the next available bonus claim after each bonus claim attempt, and if the one-hour interval has not elapsed it MUST show only the remaining time.
- **FR-033**: System MUST sell `ultraball` and `masterball` only as single-item purchases in the first version.
- **FR-034**: System MUST send one summary message for `x5` spins listing all five results by pokemon name and rarity.
- **FR-035**: System MUST attach five detail-view actions to the `x5` summary so the user can inspect each rewarded pokemon separately.
- **FR-036**: System MUST show all currently available pokemon fields in the detailed result view for a rewarded pokemon.
- **FR-037**: System MUST open detailed views for `x5` results as separate messages rather than by editing the summary message.

### Key Entities *(include if feature involves data)*

- **Shop State**: Persistent per-user state for daily bonus accumulation timestamps and pity counters for `Epic` and `Legendary`.
- **Currency Balance**: Per-user amount of `pokedollar` available for bonus claims and purchases.
- **Shop Item**: Purchasable object available in the shop, currently including `gacha_spin`, `ultraball`, and `masterball`.
- **Gacha Roll Result**: One resolved spin outcome containing the selected pokemon, spent currency, rarity outcome, and pity-counter updates.
- **User Pokemon**: A user-owned pokemon record created from a successful gacha reward and linked to `pokemon_catalog`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with sufficient balance can complete one gacha spin from the shop in one continuous flow without manual database changes.
- **SC-002**: A user with insufficient balance for `x5` spins never sees the `x5` purchase action in the shop UI.
- **SC-003**: After `15` consecutive non-epic spins, the next spin always yields `Epic` or `Legendary`.
- **SC-004**: After `40` consecutive non-legendary spins, the next spin always yields `Legendary`.
- **SC-005**: A user who claims a fully accumulated bonus can never receive more than `750 pokedollar` from one claim.
- **SC-006**: When a rewarded pokemon has no image, the result flow still completes successfully using `image.png`.
