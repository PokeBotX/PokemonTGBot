# Feature Specification: Collection Browsing and Filters

**Feature Branch**: `003-collection-filters`  
**Created**: 2026-03-16  
**Status**: Draft  
**Input**: User description: "сделать просмотр коллекции покемонов в Telegram с экраном коллекции, отдельным экраном фильтров, фильтрацией по редкости и стихиям, режимом только с дубликатами и кнопкой сброса фильтров"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the collection and browse owned pokemon (Priority: P1)

Пользователь открывает раздел `Коллекция` и видит свою коллекцию покемонов в Telegram-сообщении с текущей страницей, списком найденных записей и навигацией по страницам.

**Why this priority**: Без базового просмотра коллекции пользователь не может проверить, что он уже выбил, и не может пользоваться последующими фильтрами.

**Independent Test**: Открыть раздел `Коллекция` у пользователя с сохранёнными покемонами и убедиться, что бот показывает список, счётчики результатов и кнопки навигации по страницам.

**Acceptance Scenarios**:

1. **Given** пользователь открыл главное меню, **When** он нажимает кнопку `Коллекция` или вводит `/collection`, **Then** бот открывает экран коллекции с первой страницей результатов.
2. **Given** у пользователя есть покемоны в коллекции, **When** бот отрисовывает экран коллекции, **Then** он показывает обращение к пользователю, текущую страницу, список найденных покемонов в формате одной строки на вид покемона и общее количество найденных результатов.
3. **Given** у пользователя больше результатов, чем помещается на одну страницу, **When** он нажимает кнопку следующей или предыдущей страницы, **Then** бот открывает соседнюю страницу без потери активных фильтров.
4. **Given** у пользователя нет покемонов, подходящих под текущие условия поиска, **When** экран коллекции отрисовывается, **Then** бот явно пишет, что совпадений нет, и оставляет доступ к фильтрам и сбросу фильтров.

---

### User Story 2 - Filter collection by rarity and type (Priority: P1)

Пользователь может открыть экран фильтров коллекции и отобрать покемонов по редкости и по стихиям.

**Why this priority**: Фильтры по редкости и типам нужны, чтобы коллекция оставалась читаемой после роста числа покемонов.

**Independent Test**: Открыть экран фильтров, включить один или несколько фильтров, вернуться в коллекцию и убедиться, что показаны только подходящие покемоны.

**Acceptance Scenarios**:

1. **Given** пользователь находится в коллекции, **When** он нажимает кнопку `Фильтры`, **Then** бот открывает отдельный экран настроек фильтрации для текущей коллекции.
2. **Given** экран фильтров открыт, **When** пользователь включает одну или несколько редкостей, **Then** при возврате в коллекцию бот показывает только покемонов выбранных редкостей.
3. **Given** экран фильтров открыт, **When** пользователь включает одну или две стихии, **Then** при возврате в коллекцию бот показывает только покемонов, у которых присутствуют все выбранные типы.
4. **Given** у покемона указаны два типа в формате вроде `grass/poison`, **When** пользователь фильтрует по этим двум типам одновременно, **Then** такой покемон входит в результаты.
5. **Given** экран фильтров открыт, **When** пользователь пытается выбрать больше двух стихий одновременно, **Then** бот не включает третью стихию и сохраняет ограничение в две активные стихии.

---

### User Story 3 - Show only duplicate pokemon and reset filters (Priority: P1)

Пользователь может показать только тех покемонов, которые есть в нескольких экземплярах, а затем одной кнопкой полностью сбросить активные фильтры.

**Why this priority**: Поиск дубликатов нужен для практических действий игрока, а быстрый сброс нужен для возврата к полной коллекции без ручного отключения каждого фильтра.

**Independent Test**: Включить режим дубликатов, убедиться, что показываются только покемоны с количеством больше одного, затем нажать `Сброс` и убедиться, что коллекция снова отображается без ограничений.

**Acceptance Scenarios**:

1. **Given** экран фильтров открыт, **When** пользователь включает режим `Только дубликаты`, **Then** коллекция показывает только тех покемонов, у которых количество экземпляров с одним и тем же `pokemon_catalog.id` больше одного.
2. **Given** активны любые фильтры коллекции, **When** пользователь нажимает кнопку `Сброс`, **Then** бот очищает все активные фильтры и возвращает пользователя к полной коллекции.
3. **Given** после включения фильтра дубликатов совпадений нет, **When** бот показывает коллекцию, **Then** он явно сообщает, что подходящих дубликатов не найдено.

---

### User Story 4 - Inspect collection entries while keeping filter context (Priority: P2)

Пользователь может открыть коллекцию, перейти на страницу с результатами и сохранить выбранные фильтры при дальнейшей навигации по коллекции.

**Why this priority**: Фильтры теряют смысл, если при переходах между страницами они сбрасываются.

**Independent Test**: Включить несколько фильтров, перейти на другую страницу и убедиться, что бот сохраняет те же условия просмотра.

**Acceptance Scenarios**:

1. **Given** пользователь применил фильтры по редкости, стихиям и/или дубликатам, **When** он листает страницы коллекции, **Then** все выбранные фильтры остаются активными.
2. **Given** пользователь возвращается из экрана фильтров в экран коллекции, **When** коллекция открывается снова, **Then** она использует уже сохранённое состояние фильтров для этого пользователя.
3. **Given** пользователь видит страницу коллекции, **When** он нажимает кнопку конкретного покемона под списком, **Then** бот открывает отдельную карточку этого покемона.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated collection section reachable from the existing main menu and the `/collection` command.
- **FR-002**: System MUST render the collection as a Telegram message view with a short header, current page number, result summary, and inline keyboard navigation.
- **FR-002**: System MUST render the collection as a Telegram message view with a short header, current page number, result summary, and inline keyboard navigation.
- **FR-003**: System MUST show collection results using the existing `user_pokemon` ownership data joined with `pokemon_catalog`.
- **FR-004**: System MUST include pagination for collection results when the number of matching records exceeds one page.
- **FR-005**: System MUST preserve active collection filters when the user moves between collection pages.
- **FR-006**: System MUST provide a separate filter screen for the collection rather than mixing all filter controls into the main collection text body.
- **FR-007**: System MUST allow the user to filter collection results by one or more rarities chosen from `Legendary`, `Epic`, `Rare`, and `Common`.
- **FR-008**: System MUST allow the user to filter collection results by pokemon types based on individual normalized type values rather than combined raw strings like `dark/water`.
- **FR-009**: System MUST limit simultaneous type selection to at most two active types.
- **FR-010**: System MUST treat a multi-type pokemon as matching the type filter only when all selected types are present in its stored type set.
- **FR-011**: System MUST allow the user to enable a `duplicates only` filter that limits results to pokemon with more than one owned instance.
- **FR-012**: System MUST provide a `Reset filters` action that clears all active collection filters in one interaction.
- **FR-013**: System MUST show the user which filters are currently active when rendering the filter screen.
- **FR-014**: System MUST show a clear empty-state message when no owned pokemon match the current filters.
- **FR-015**: System MUST keep the collection usable for users with no owned pokemon by showing an empty-state message and keeping access to filter controls.
- **FR-016**: System MUST store collection filter state in a way that survives callback navigation inside the current viewing flow.
- **FR-017**: System MUST preserve Telegram-first UX by keeping collection and filter messages concise and actionable.
- **FR-018**: System MUST expose a back action from the filter screen to the collection screen and from the collection screen to the main menu.
- **FR-019**: System MUST keep duplicate-click safety for collection callbacks, including pagination and filter toggles.
- **FR-020**: System MUST log collection rendering, filter changes, and pagination actions with structured logs sufficient for debugging.
- **FR-021**: System MUST display the count of found collection entries after filters are applied.
- **FR-022**: System MUST group duplicate ownership at the pokemon species level for collection browsing, so the user sees a quantity-aware entry rather than one line per identical owned instance.
- **FR-023**: System MUST render each collection line in the compact format `<rarity marker> <name> x<quantity> | id: <pokemon_id>`.
- **FR-024**: System MUST use a page size of `12` collection entries per page.
- **FR-025**: System MUST expose per-entry buttons below the collection list that open a pokemon card view for the corresponding collection entry.
- **FR-026**: System MUST apply filter changes immediately on toggle and MUST NOT require a separate `Apply` button.
- **FR-027**: System MUST keep the collection layout approximately aligned with the requested Telegram mockup: text summary at the top, entry buttons below, and a dedicated filter/settings screen.

### Key Entities *(include if feature involves data)*

- **Collection Entry**: Aggregated view of one pokemon species owned by a user, including pokemon id, name, rarity, type, and owned quantity.
- **Collection Filter State**: Current user-selected criteria for collection browsing, including selected rarities, up to two selected types, duplicates-only flag, and current page.
- **Collection Page**: Paginated slice of filtered collection entries plus counts for total matches and current page index.
- **Collection Card Action**: Inline action tied to a collection entry button that opens a dedicated pokemon card view while preserving the current collection browsing context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with owned pokemon can open `Коллекция` and see the first page of results in one Telegram interaction.
- **SC-002**: A user can apply at least one rarity filter and at least one type filter, and the collection results update without losing pagination controls.
- **SC-003**: A user can enable `duplicates only` and see only pokemon species with owned quantity greater than `1`.
- **SC-004**: A user can press `Сброс` once and return to the unfiltered collection view without manually toggling individual filters off.
- **SC-005**: Collection pagination keeps the active filters intact across page transitions.
- **SC-006**: A user with no matching records receives a readable empty-state message instead of a broken or blank collection screen.
