# Feature Specification: Profile System

**Feature Branch**: `005-profile-system`  
**Created**: 2026-03-20  
**Status**: Draft  
**Input**: User description: "сделать профиль с общей информацией, настройками, рефкой, плейсхолдерами для команды и VIP; в профиле показать Telegram ID, возраст аккаунта, прогресс по уникальным покемонам и редкостям; обложку можно ставить только из уже имеющихся у пользователя покемонов; в настройках нужны язык, обложка и смена ника"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View the main profile screen (Priority: P1)

Пользователь открывает профиль и видит краткую сводку по аккаунту, коллекции и основным разделам профиля.

**Why this priority**: Это основная точка входа в профиль; без неё остальная настройка не имеет ценности.

**Independent Test**: Открыть профиль из меню или через команду и убедиться, что бот показывает имя пользователя, Telegram ID, возраст аккаунта, общий прогресс по уникальным покемонам и кнопки профиля.

**Acceptance Scenarios**:

1. **Given** пользователь открывает профиль, **When** бот формирует экран профиля, **Then** в сообщении видно обращение вида `👤 <имя>, ваш профиль:` и строку `🆔 <telegram_id>`.
2. **Given** пользователь имеет пойманных покемонов, **When** бот отображает профиль, **Then** он показывает прогресс по уникальным видам покемонов в формате `X из 1025 (Y%)`.
3. **Given** у пользователя есть покемоны разных редкостей, **When** бот отображает профиль, **Then** он показывает аналогичный прогресс по редкостям с количеством уникальных покемонов нужной редкости и процентом от общего числа видов этой редкости.
4. **Given** аккаунт пользователя уже существует некоторое время, **When** бот показывает профиль, **Then** он отображает возраст аккаунта в человекочитаемом формате вроде `3 дня`.
5. **Given** пользователь открыл профиль, **When** бот показывает клавиатуру, **Then** на экране есть кнопки `Настройки`, `Рефка`, `Боевая команда`, `VIP` и `Назад в меню`.

---

### User Story 2 - Open settings and change profile data (Priority: P1)

Пользователь может открыть настройки профиля и изменить ник или язык, а также перейти к настройке обложки.

**Why this priority**: Настройки составляют основную полезную часть профиля в первой версии.

**Independent Test**: Открыть `Настройки`, изменить ник, сменить язык и убедиться, что данные сохраняются в БД и повторно отображаются в профиле.

**Acceptance Scenarios**:

1. **Given** пользователь нажал `Настройки`, **When** бот открывает экран настроек, **Then** на экране есть кнопки `Язык`, `Обложка`, `Смена ника`, `Назад в профиль`, `Назад в меню`.
2. **Given** пользователь меняет ник через профиль, **When** бот сохраняет изменение, **Then** новое значение записывается в `users.nickname` и используется в профиле.
3. **Given** пользователь меняет язык, **When** бот завершает действие, **Then** новое значение записывается в пользовательские настройки в БД.
4. **Given** язык пока не влияет на тексты бота, **When** пользователь успешно меняет язык, **Then** бот всё равно подтверждает сохранение без обещания немедленного перевода интерфейса.

---

### User Story 3 - View and use the referral screen (Priority: P2)

Пользователь может открыть реферальный раздел и получить только свою персональную реферальную ссылку.

**Why this priority**: Это отдельный полезный раздел профиля, но он не блокирует базовую работу профиля и настроек.

**Independent Test**: Нажать `Рефка` и убедиться, что бот показывает персональную ссылку и кнопки возврата.

**Acceptance Scenarios**:

1. **Given** пользователь нажал `Рефка`, **When** бот открывает раздел, **Then** он показывает только персональную реферальную ссылку пользователя без статистики приглашений.
2. **Given** пользователь находится в разделе рефки, **When** он нажимает `Назад в профиль`, **Then** бот возвращает его на главный экран профиля.

---

### User Story 4 - Choose a profile cover from owned pokemon (Priority: P1)

Пользователь может выбрать обложку профиля только из изображений тех покемонов, которые уже есть в его коллекции.

**Why this priority**: Обложка является главным визуальным элементом профиля и требует отдельного контролируемого сценария.

**Independent Test**: Открыть выбор обложки, найти покемона по имени, выбрать его и убедиться, что обложка профиля обновилась; для пользователя без выбора должна использоваться `image_profile.png`.

**Acceptance Scenarios**:

1. **Given** пользователь ещё не выбирал обложку, **When** бот показывает профиль, **Then** по умолчанию используется изображение `image_profile.png`.
2. **Given** пользователь открывает настройку `Обложка`, **When** бот показывает сценарий выбора, **Then** поиск и выбор доступны только по покемонам, которые уже принадлежат пользователю.
3. **Given** у пользователя нет нужного покемона, **When** он пытается выбрать не принадлежащего ему покемона как обложку, **Then** бот отклоняет выбор и оставляет текущую обложку без изменений.
4. **Given** пользователь выбрал принадлежащего ему покемона, **When** бот сохраняет выбор, **Then** изображение этого покемона становится обложкой профиля.
5. **Given** пользователь вернулся в профиль после выбора обложки, **When** бот повторно рендерит экран, **Then** профиль показывается уже с новой обложкой.

---

### User Story 5 - Keep placeholder sections for battle team and VIP (Priority: P3)

Разделы `Боевая команда` и `VIP` уже видны в профиле, но в первой версии работают как заглушки.

**Why this priority**: Кнопки нужны для целостности интерфейса, но их реальная логика пока вне текущего объёма.

**Independent Test**: Нажать `Боевая команда` и `VIP` и убедиться, что бот открывает понятные placeholder-экраны без ошибки.

**Acceptance Scenarios**:

1. **Given** пользователь нажал `Боевая команда`, **When** раздел ещё не реализован, **Then** бот показывает внятную заглушку и даёт вернуться назад.
2. **Given** пользователь нажал `VIP`, **When** раздел ещё не реализован, **Then** бот показывает внятную заглушку и даёт вернуться назад.

---

### User Story 6 - Search pokemon by name without loading the entire catalog (Priority: P2)

Пользователь может искать покемона по имени через отдельный сценарий поиска, а бот должен обрабатывать поиск эффективно, не загружая сразу весь каталог из `1025` покемонов в память или в Telegram UI.

**Why this priority**: Эта механика нужна для будущего `/search` и для удобного выбора обложки, но не блокирует базовый профиль.

**Independent Test**: Запустить поиск по части имени, убедиться, что при одном результате сразу открывается карточка, а при нескольких показывается компактный список вариантов.

**Acceptance Scenarios**:

1. **Given** пользователь вводит имя покемона или его часть, **When** бот находит ровно один подходящий вариант, **Then** бот сразу показывает карточку найденного покемона.
2. **Given** пользователь вводит имя покемона или его часть, **When** бот находит несколько подходящих вариантов, **Then** бот показывает компактный список вариантов примерно в формате списка результатов, а не грузит весь каталог сразу.
3. **Given** пользователь использует поиск при выборе обложки, **When** бот выполняет запрос, **Then** он ищет только среди покемонов, которыми пользователь уже владеет.
4. **Given** каталог содержит `1025` покемонов, **When** пользователь выполняет поиск, **Then** бот применяет фильтрацию и ограничение результатов на уровне SQL, а не загружает все записи целиком в Python.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a dedicated profile screen accessible from the main menu and the `/profile` command.
- **FR-002**: System MUST display the current user’s visible name and Telegram ID on the main profile screen.
- **FR-003**: System MUST calculate and display the number of unique pokemon species the user owns out of the global catalog size `1025`.
- **FR-004**: System MUST display the unique-species completion percent alongside the total unique count.
- **FR-005**: System MUST display unique-species progress by rarity, including count and percent for each rarity bucket.
- **FR-006**: System MUST calculate account age from the user creation timestamp and show it in a human-readable relative format like `3 дня`.
- **FR-007**: System MUST show profile action buttons for `Настройки`, `Рефка`, `Боевая команда`, `VIP`, and return navigation.
- **FR-008**: System MUST provide a settings screen with `Язык`, `Обложка`, and `Смена ника`.
- **FR-009**: System MUST persist nickname changes into `users.nickname`.
- **FR-010**: System MUST persist language changes into the user settings record in the database.
- **FR-011**: System MUST acknowledge language changes even if the rest of the bot UI remains functionally unchanged for now.
- **FR-012**: System MUST provide a referral screen that shows only the user’s personal referral link in version 1.
- **FR-013**: System MUST support a profile cover image for the profile screen.
- **FR-014**: System MUST use `image_profile.png` as the default profile cover when the user has not chosen a custom one.
- **FR-015**: System MUST allow selecting a profile cover only from pokemon images already present in the bot and already owned by the user.
- **FR-016**: System MUST provide cover selection through a pokemon search flow rather than through a full collection list.
- **FR-017**: System MUST reject any attempt to set a profile cover to a pokemon the user does not own.
- **FR-018**: System MUST persist the chosen cover so the same cover is used on subsequent profile openings.
- **FR-019**: System MUST keep `Боевая команда` and `VIP` buttons visible on the main profile screen, but their first version MAY be placeholder-only.
- **FR-020**: System MUST provide `Назад в профиль` from nested profile screens and `Назад в меню` from the profile root.
- **FR-021**: System MUST preserve Telegram-style clarity and avoid long unstructured profile text blocks.
- **FR-022**: System MUST use only pokemon images already known to the bot storage/image system for profile covers.
- **FR-023**: System MUST keep profile ownership rules strict: a user can never use another user’s pokemon image as their profile cover.
- **FR-024**: System MUST reserve the `/search` command name for pokemon-name search rather than chat encounter spawning.
- **FR-025**: System MUST support searching pokemon by name or partial name.
- **FR-026**: System MUST immediately open the pokemon card when the search returns exactly one result.
- **FR-027**: System MUST show a compact selectable result list when the search returns multiple matches.
- **FR-028**: System MUST restrict cover-selection search results to pokemon owned by the current user.
- **FR-029**: System MUST execute pokemon-name search with SQL-side filtering and limiting rather than loading the full `1025`-pokemon catalog into Python first.

### Key Entities *(include if feature involves data)*

- **Profile Summary**: Read model containing the user-facing profile header, Telegram ID, account age, global unique-pokemon progress, rarity progress, and current cover information.
- **User Settings**: Persistent per-user settings including language and selected cover image reference.
- **Profile Cover Candidate**: Pokemon owned by the user that is eligible to become the profile cover because it has an image already available in the bot.
- **Referral Link**: User-specific shareable URL shown in the referral section.
- **Pokemon Search Result**: One compact search hit that can either resolve directly to a pokemon card or appear as one item inside a short result list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Пользователь открывает профиль не более чем за один Telegram action flow и видит заголовок, Telegram ID, возраст аккаунта и прогресс по коллекции.
- **SC-002**: Экран профиля показывает общий прогресс по уникальным покемонам и прогресс по редкостям без рассинхронизации с фактическими данными коллекции.
- **SC-003**: Пользователь может изменить ник и при следующем открытии профиля увидеть новое значение.
- **SC-004**: Пользователь может изменить язык, и новое значение сохраняется в БД даже если тексты бота пока визуально не меняются.
- **SC-005**: Пользователь без выбранной обложки всегда видит стандартную `image_profile.png`.
- **SC-006**: Пользователь может установить обложку только из своих покемонов; попытка выбрать чужого или недоступного покемона не изменяет профиль.
- **SC-007**: Раздел `Рефка` показывает только персональную ссылку пользователя без лишних метрик.
- **SC-008**: Поиск по имени покемона не требует загрузки всего каталога целиком и при нескольких совпадениях показывает компактный список вариантов.
