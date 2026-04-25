"""UI helpers for the admin bot."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.ui.html import escape_html

SECTION_ROOT = "adm"
SECTION_GRANTS = "adg"
SECTION_POKEMON = "adp"
SECTION_IMAGES = "adi"
SECTION_AUDIT = "ada"
SECTION_CONFIRM = "adc"
SECTION_CANCEL = "adx"
SECTION_GRANT_POKEDOLLAR = "ag1"
SECTION_GRANT_POKECOIN = "ag2"
SECTION_GRANT_POKEMON = "ag3"
SECTION_CREATE_POKEMON = "ap1"
SECTION_IMAGE_UPLOAD_VARIANT = "ai1"
SECTION_IMAGE_EDIT_SOURCE = "ai2"
SECTION_IMAGE_EDIT_VARIANT = "ai3"

ADMIN_SECTIONS: dict[str, str] = {
    SECTION_GRANTS: "Выдачи",
    SECTION_POKEMON: "Каталог покемонов",
    SECTION_IMAGES: "Изображения",
    SECTION_AUDIT: "Аудит",
}


def build_admin_callback(section: str, session_id: str) -> str:
    """Build callback data for the admin bot."""
    return f"menu:{section}:{session_id}"


def build_admin_root_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build the main admin menu keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💸 Выдачи", callback_data=build_admin_callback(SECTION_GRANTS, session_id)),
                InlineKeyboardButton("🆕 Каталог", callback_data=build_admin_callback(SECTION_POKEMON, session_id)),
            ],
            [
                InlineKeyboardButton("🖼 Изображения", callback_data=build_admin_callback(SECTION_IMAGES, session_id)),
                InlineKeyboardButton("🧾 Аудит", callback_data=build_admin_callback(SECTION_AUDIT, session_id)),
            ],
        ]
    )


def build_admin_back_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build a back-to-root keyboard for admin detail screens."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬅️ В меню", callback_data=build_admin_callback(SECTION_ROOT, session_id)),
            ]
        ]
    )


def build_admin_grants_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build the grants section keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💵 PokéDollar", callback_data=build_admin_callback(SECTION_GRANT_POKEDOLLAR, session_id)),
                InlineKeyboardButton("🪙 PokéCoin", callback_data=build_admin_callback(SECTION_GRANT_POKECOIN, session_id)),
            ],
            [
                InlineKeyboardButton("🎁 Покемон", callback_data=build_admin_callback(SECTION_GRANT_POKEMON, session_id)),
            ],
            build_admin_back_keyboard(session_id).inline_keyboard[0],
        ]
    )


def build_admin_pokemon_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build the pokemon catalog section keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🆕 Создать покемона", callback_data=build_admin_callback(SECTION_CREATE_POKEMON, session_id)),
            ],
            build_admin_back_keyboard(session_id).inline_keyboard[0],
        ]
    )


def build_admin_images_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build the images section keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬆️ Загрузить вариант", callback_data=build_admin_callback(SECTION_IMAGE_UPLOAD_VARIANT, session_id)),
            ],
            [
                InlineKeyboardButton("🔗 Изменить source", callback_data=build_admin_callback(SECTION_IMAGE_EDIT_SOURCE, session_id)),
                InlineKeyboardButton("↕️ Порядок / default", callback_data=build_admin_callback(SECTION_IMAGE_EDIT_VARIANT, session_id)),
            ],
            build_admin_back_keyboard(session_id).inline_keyboard[0],
        ]
    )


def build_admin_confirmation_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build a standard confirm/cancel keyboard for privileged actions."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=build_admin_callback(SECTION_CONFIRM, session_id)),
                InlineKeyboardButton("❌ Отмена", callback_data=build_admin_callback(SECTION_CANCEL, session_id)),
            ]
        ]
    )


def get_admin_welcome_text(username: str | None) -> str:
    """Return root admin menu text."""
    label = f"@{escape_html(username)}" if username else "superadmin"
    return (
        f"🛠 <b>Админ-бот</b>\n\n"
        f"Привет, {label}.\n"
        "Здесь мы работаем только в личке и только через подтверждаемые действия.\n\n"
        "Уже готово:\n"
        "• доступ по allowlist из env\n"
        "• отдельный state для второго бота\n"
        "• общий confirm-каркас\n"
        "• аудит всех будущих мутаций\n\n"
        "Ниже можно открыть нужный раздел."
    )


def get_private_only_text() -> str:
    """Return private-chat-only warning."""
    return "⚠️ Этот админ-бот работает только в личке."


def get_access_denied_text() -> str:
    """Return access denied warning."""
    return "⛔ У вас нет доступа к этому админ-боту."


def get_placeholder_section_text(title: str) -> str:
    """Return placeholder text for not-yet-implemented admin sections."""
    return (
        f"🧩 <b>{escape_html(title)}</b>\n\n"
        "Каркас раздела уже готов. Сами действия подключим следующими шагами через общий confirm-flow и аудит."
    )


def get_grants_section_text() -> str:
    """Return the root grants section text."""
    return (
        "💸 <b>Выдачи</b>\n\n"
        "Здесь можно безопасно выдать пользователю валюту или конкретного покемона.\n"
        "Дальше бот сам проведёт нас по шагам и перед выполнением обязательно покажет подтверждение."
    )


def get_pokemon_section_text() -> str:
    """Return the pokemon catalog section text."""
    return (
        "🆕 <b>Каталог покемонов</b>\n\n"
        "Здесь можно создать нового покемона с полным набором полей каталога."
    )


def get_images_section_text() -> str:
    """Return the image management section text."""
    return (
        "🖼 <b>Изображения</b>\n\n"
        "Здесь можно загружать новые арты и привязывать их к существующим покемонам как image variant."
    )


def get_image_upload_intro_text() -> str:
    """Return intro text before the image upload wizard starts."""
    return (
        "⬆️ <b>Загрузка варианта</b>\n\n"
        "Сначала отправьте картинку как photo или document."
    )


def get_image_upload_pokemon_prompt() -> str:
    """Prompt for pokemon id after media has been received."""
    return (
        "🧬 <b>Привязка арта</b>\n\n"
        "Изображение принято. Теперь отправьте <code>pokemon_id</code>, к которому нужно привязать этот арт."
    )


def get_image_upload_source_prompt(pokemon_name: str, pokemon_id: int) -> str:
    """Prompt for source URL."""
    return (
        "🔗 <b>Источник арта</b>\n\n"
        f"Покемон: <b>{escape_html(pokemon_name)}</b> (#{pokemon_id})\n"
        "Отправьте ссылку на источник арта или <code>-</code>, если хотите пропустить."
    )


def get_image_upload_order_prompt() -> str:
    """Prompt for display order."""
    return (
        "🔢 <b>Порядок варианта</b>\n\n"
        "Отправьте число <code>display_order</code> больше нуля."
    )


def get_image_upload_default_prompt() -> str:
    """Prompt for default-variant choice."""
    return (
        "⭐ <b>Вариант по умолчанию</b>\n\n"
        "Отправьте <code>да</code> или <code>нет</code>."
    )


def get_image_upload_summary_text(*, pokemon_id: int, pokemon_name: str, source: str | None, display_order: int, is_default: bool, file_name: str | None) -> str:
    """Return confirmation summary for a new image variant."""
    source_text = source or "—"
    file_text = file_name or "telegram-upload"
    default_text = "да" if is_default else "нет"
    return (
        "Будет загружен новый image variant:\n"
        f"• Покемон: <b>{escape_html(pokemon_name)}</b> (#{pokemon_id})\n"
        f"• Файл: <code>{escape_html(file_text)}</code>\n"
        f"• Source: <code>{escape_html(source_text)}</code>\n"
        f"• display_order: <b>{display_order}</b>\n"
        f"• default: <b>{default_text}</b>"
    )


def get_image_credit_id_prompt(action_label: str) -> str:
    """Prompt for image_credit id."""
    return (
        f"🖼 <b>{escape_html(action_label)}</b>\n\n"
        "Отправьте <code>image_credit_id</code> одним числом."
    )


def get_image_source_edit_prompt(image_credit_id: int) -> str:
    """Prompt for new source URL."""
    return (
        "🔗 <b>Изменение source</b>\n\n"
        f"image_credit_id: <code>{image_credit_id}</code>\n"
        "Отправьте новый URL или <code>-</code>, чтобы очистить source."
    )


def get_variant_pokemon_id_prompt() -> str:
    """Prompt for pokemon id for variant metadata editing."""
    return (
        "🧬 <b>Параметры варианта</b>\n\n"
        "Сначала отправьте <code>pokemon_id</code>."
    )


def get_variant_image_credit_id_prompt(pokemon_id: int) -> str:
    """Prompt for image_credit id for variant metadata editing."""
    return (
        "🧩 <b>Параметры варианта</b>\n\n"
        f"pokemon_id: <code>{pokemon_id}</code>\n"
        "Теперь отправьте <code>image_credit_id</code> нужного варианта."
    )


def get_variant_order_prompt() -> str:
    """Prompt for new display order."""
    return (
        "🔢 <b>Новый порядок</b>\n\n"
        "Отправьте новый <code>display_order</code> больше нуля."
    )


def get_variant_default_prompt() -> str:
    """Prompt for default toggle."""
    return (
        "⭐ <b>Новый default</b>\n\n"
        "Отправьте <code>да</code> или <code>нет</code>."
    )


def get_image_source_update_summary_text(*, image_credit_id: int, source: str | None) -> str:
    """Return confirmation summary for source update."""
    source_text = source or "—"
    return (
        "Будет обновлён source изображения:\n"
        f"• image_credit_id: <code>{image_credit_id}</code>\n"
        f"• source: <code>{escape_html(source_text)}</code>"
    )


def get_variant_update_summary_text(*, pokemon_id: int, image_credit_id: int, display_order: int, is_default: bool) -> str:
    """Return confirmation summary for variant metadata update."""
    default_text = "да" if is_default else "нет"
    return (
        "Будут обновлены параметры варианта:\n"
        f"• pokemon_id: <code>{pokemon_id}</code>\n"
        f"• image_credit_id: <code>{image_credit_id}</code>\n"
        f"• display_order: <b>{display_order}</b>\n"
        f"• default: <b>{default_text}</b>"
    )


def get_create_pokemon_intro_text() -> str:
    """Return intro text before the pokemon creation wizard starts."""
    return (
        "🆕 <b>Создание покемона</b>\n\n"
        "Сейчас бот по очереди спросит все поля каталога.\n"
        "Для необязательного типа можно отправить <code>-</code>."
    )


def get_create_pokemon_field_prompt(*, field_label: str, step: int, total_steps: int, hint: str) -> str:
    """Return prompt for one pokemon draft field."""
    return (
        f"🧩 <b>Создание покемона</b>\n\n"
        f"Шаг <b>{step}/{total_steps}</b>\n"
        f"Поле: <b>{escape_html(field_label)}</b>\n\n"
        f"{escape_html(hint)}"
    )


def get_create_pokemon_summary_text(*, pokemon_id: int, name: str, pokemon_type: str | None, rarity: str, base_hp: int, base_attack: int, base_defense: int, base_stamina: int) -> str:
    """Return human-readable summary of the pokemon draft."""
    pokemon_type_text = pokemon_type or "—"
    return (
        "Будет создан новый покемон:\n"
        f"• ID: <code>{pokemon_id}</code>\n"
        f"• Имя: <b>{escape_html(name)}</b>\n"
        f"• Тип: <b>{escape_html(pokemon_type_text)}</b>\n"
        f"• Редкость: <b>{escape_html(rarity)}</b>\n"
        f"• HP: <b>{base_hp}</b>\n"
        f"• ATK: <b>{base_attack}</b>\n"
        f"• DEF: <b>{base_defense}</b>\n"
        f"• SPD: <b>{base_stamina}</b>"
    )


def get_grant_username_prompt(action_label: str) -> str:
    """Prompt for a target username."""
    return (
        f"👤 <b>{escape_html(action_label)}</b>\n\n"
        "Отправьте username пользователя в формате <code>@username</code>."
    )


def get_grant_amount_prompt(currency_label: str, username: str) -> str:
    """Prompt for a numeric currency amount."""
    return (
        f"💰 <b>Выдача {escape_html(currency_label)}</b>\n\n"
        f"Получатель: <code>@{escape_html(username.lstrip('@'))}</code>\n"
        "Теперь отправьте сумму одним числом."
    )


def get_grant_pokemon_prompt(username: str) -> str:
    """Prompt for pokemon id."""
    return (
        "🎁 <b>Выдача покемона</b>\n\n"
        f"Получатель: <code>@{escape_html(username.lstrip('@'))}</code>\n"
        "Теперь отправьте <code>pokemon_id</code> одним числом."
    )


def get_pending_action_text(*, title: str, description: str) -> str:
    """Return confirmation preview text."""
    return (
        f"⚠️ <b>{escape_html(title)}</b>\n\n"
        f"{escape_html(description)}\n\n"
        "Если подтвердите, бот выполнит это действие с доступом к БД и MinIO."
    )


def get_action_canceled_text(action_label: str) -> str:
    """Return user-facing confirmation cancel text."""
    return f"↩️ Действие отменено: {escape_html(action_label)}"
