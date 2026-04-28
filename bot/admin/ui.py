"""UI helpers for the admin bot."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.ui.html import escape_html

SECTION_ROOT = "adm"
SECTION_GRANTS = "adg"
SECTION_POKEMON = "adp"
SECTION_IMAGES = "adi"
SECTION_AUDIT = "ada"
SECTION_AUDIT_EXPORT = "aae"
SECTION_BROADCAST = "adb"
SECTION_CONFIRM = "adc"
SECTION_CANCEL = "adx"
SECTION_GRANT_POKEDOLLAR = "ag1"
SECTION_GRANT_POKECOIN = "ag2"
SECTION_GRANT_POKEMON = "ag3"
SECTION_CREATE_POKEMON = "ap1"
SECTION_EDIT_POKEMON = "ap2"
SECTION_EDIT_POKEMON_NAME = "apn"
SECTION_EDIT_POKEMON_TYPE = "apt"
SECTION_EDIT_POKEMON_RARITY = "apr"
SECTION_EDIT_POKEMON_HP = "aph"
SECTION_EDIT_POKEMON_ATTACK = "apa"
SECTION_EDIT_POKEMON_DEFENSE = "apd"
SECTION_EDIT_POKEMON_STAMINA = "aps"
SECTION_IMAGE_UPLOAD_VARIANT = "ai1"
SECTION_IMAGE_EDIT_SOURCE = "ai2"
SECTION_IMAGE_EDIT_VARIANT = "ai3"

ADMIN_SECTIONS: dict[str, str] = {
    SECTION_GRANTS: "Выдачи",
    SECTION_POKEMON: "Каталог покемонов",
    SECTION_IMAGES: "Изображения",
    SECTION_AUDIT: "Аудит",
    SECTION_BROADCAST: "Рассылка",
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
            [
                InlineKeyboardButton("📣 Рассылка", callback_data=build_admin_callback(SECTION_BROADCAST, session_id)),
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
            [
                InlineKeyboardButton("✏️ Редактировать вид", callback_data=build_admin_callback(SECTION_EDIT_POKEMON, session_id)),
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


def build_admin_audit_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build the audit section keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Обновить", callback_data=build_admin_callback(SECTION_AUDIT, session_id)),
                InlineKeyboardButton("📤 Экспорт", callback_data=build_admin_callback(SECTION_AUDIT_EXPORT, session_id)),
            ],
            build_admin_back_keyboard(session_id).inline_keyboard[0],
        ]
    )


def build_admin_broadcast_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build the broadcast section keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✍️ Новая рассылка", callback_data=build_admin_callback(SECTION_BROADCAST, session_id)),
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
        "Все изменяющие операции сначала показывают preview, потом ждут подтверждение, и только после этого трогают БД или MinIO.\n\n"
        "Выберите нужный раздел ниже."
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
        "Здесь можно выдать пользователю валюту или конкретного покемона.\n"
        "Бот сам проведёт по шагам и перед выполнением обязательно покажет подтверждение."
    )


def get_pokemon_section_text() -> str:
    """Return the pokemon catalog section text."""
    return (
        "🆕 <b>Каталог покемонов</b>\n\n"
        "Здесь можно создать нового покемона с полным набором полей каталога или точечно исправить существующий вид.\n"
        "Перед сохранением бот покажет итоговый preview."
    )


def build_admin_edit_pokemon_field_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Build field-selection keyboard for pokemon species edits."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Имя", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_NAME, session_id)),
                InlineKeyboardButton("Тип", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_TYPE, session_id)),
                InlineKeyboardButton("Редкость", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_RARITY, session_id)),
            ],
            [
                InlineKeyboardButton("HP", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_HP, session_id)),
                InlineKeyboardButton("ATK", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_ATTACK, session_id)),
            ],
            [
                InlineKeyboardButton("DEF", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_DEFENSE, session_id)),
                InlineKeyboardButton("SPD", callback_data=build_admin_callback(SECTION_EDIT_POKEMON_STAMINA, session_id)),
            ],
            build_admin_back_keyboard(session_id).inline_keyboard[0],
        ]
    )


def get_edit_pokemon_intro_text() -> str:
    """Return intro text before species edit starts."""
    return (
        "✏️ <b>Редактирование вида покемона</b>\n\n"
        "Сначала отправьте <code>pokemon_id</code> существующего вида."
    )


def get_edit_pokemon_field_text(*, pokemon_id: int, name: str) -> str:
    """Prompt for field selection after pokemon lookup."""
    return (
        "✏️ <b>Редактирование вида покемона</b>\n\n"
        f"Покемон: <b>{escape_html(name)}</b> (#{pokemon_id})\n"
        "Теперь выберите поле, которое нужно изменить."
    )


def get_edit_pokemon_value_prompt(*, pokemon_id: int, name: str, field_label: str, current_value: str) -> str:
    """Prompt for the new field value."""
    return (
        "✏️ <b>Новое значение</b>\n\n"
        f"Покемон: <b>{escape_html(name)}</b> (#{pokemon_id})\n"
        f"Поле: <b>{escape_html(field_label)}</b>\n"
        f"Сейчас: <code>{escape_html(current_value)}</code>\n\n"
        "Отправьте новое значение одним сообщением."
    )


def get_edit_pokemon_summary_text(*, pokemon_id: int, name: str, field_label: str, old_value: str, new_value: str) -> str:
    """Return confirmation summary for one species point edit."""
    return (
        "Будет обновлён вид покемона:\n"
        f"• Покемон: <b>{escape_html(name)}</b> (#{pokemon_id})\n"
        f"• Поле: <b>{escape_html(field_label)}</b>\n"
        f"• Было: <code>{escape_html(old_value)}</code>\n"
        f"• Станет: <code>{escape_html(new_value)}</code>"
    )


def get_images_section_text() -> str:
    """Return the image management section text."""
    return (
        "🖼 <b>Изображения</b>\n\n"
        "Здесь можно загружать новые арты и привязывать их к существующим покемонам как image variant.\n"
        "Также здесь редактируются source, порядок и default-вариант."
    )


def get_broadcast_intro_text() -> str:
    """Return intro text before broadcast compose starts."""
    return (
        "📣 <b>Рассылка</b>\n\n"
        "Отправьте текст сообщения, которое нужно разослать по групповым чатам, где сейчас состоит основной бот."
    )


def get_broadcast_empty_targets_text() -> str:
    """Return empty-target warning for broadcast flow."""
    return (
        "📣 <b>Рассылка</b>\n\n"
        "Подходящих групповых чатов для рассылки сейчас нет."
    )


def get_broadcast_summary_text(*, chat_count: int, message_text: str) -> str:
    """Return confirmation summary for a pending broadcast."""
    preview = message_text.strip()
    if len(preview) > 800:
        preview = preview[:797] + "..."
    return (
        "Будет отправлена текстовая рассылка:\n"
        f"• Чатов: <b>{chat_count}</b>\n\n"
        f"<blockquote>{escape_html(preview)}</blockquote>"
    )


def format_admin_audit_status(status: str) -> str:
    """Return a short human-readable status label."""
    return {
        "pending": "ожидает",
        "success": "успешно",
        "failed": "ошибка",
        "canceled": "отменено",
        "expired": "истекло",
    }.get(status, status)


def _format_admin_audit_timestamp(value: datetime) -> str:
    localized = value.astimezone(UTC)
    return localized.strftime("%Y-%m-%d %H:%M UTC")


def get_admin_audit_text(records: list[object]) -> str:
    """Render recent admin audit records for the audit screen."""
    if not records:
        return (
            "🧾 <b>Аудит</b>\n\n"
            "Записей пока нет."
        )

    lines = ["🧾 <b>Аудит</b>", "", "Последние действия:"]
    for record in records:
        actor = f"@{escape_html(record.actor_username)}" if getattr(record, "actor_username", None) else str(record.actor_telegram_id)
        target = getattr(record, "target_username", None)
        target_label = f" → @{escape_html(target)}" if target else ""
        lines.append(
            "• "
            f"<code>{_format_admin_audit_timestamp(record.created_at)}</code>\n"
            f"  <b>{escape_html(record.action_type)}</b> · {escape_html(format_admin_audit_status(record.status))}\n"
            f"  {actor}{target_label}"
        )
    lines.append("")
    lines.append("Экспорт выгружает расширенную текстовую сводку последних записей.")
    return "\n".join(lines)


def build_admin_audit_export_text(records: list[object]) -> str:
    """Build text export payload for audit records."""
    if not records:
        return "Admin audit export\n\nNo records."

    chunks = ["Admin audit export", ""]
    for record in records:
        chunks.extend(
            [
                f"id: {record.audit_id}",
                f"created_at: {record.created_at.isoformat()}",
                f"action_type: {record.action_type}",
                f"status: {record.status}",
                f"actor_telegram_id: {record.actor_telegram_id}",
                f"actor_username: {record.actor_username or ''}",
                f"target_user_id: {record.target_user_id or ''}",
                f"target_telegram_id: {record.target_telegram_id or ''}",
                f"target_username: {record.target_username or ''}",
                f"input_payload: {json.dumps(record.input_payload, ensure_ascii=False, sort_keys=True)}",
                f"result_payload: {json.dumps(record.result_payload, ensure_ascii=False, sort_keys=True)}",
                f"error_message: {record.error_message or ''}",
                "",
            ]
        )
    return "\n".join(chunks).strip() + "\n"


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
        "Если подтвердите, бот выполнит это действие с доступом к БД и MinIO.\n"
        "Если отмените, никаких изменений не произойдёт."
    )


def get_action_canceled_text(action_label: str) -> str:
    """Return user-facing confirmation cancel text."""
    return (
        "↩️ <b>Действие отменено</b>\n\n"
        f"{escape_html(action_label)} не будет выполнено."
    )


def get_action_expired_text(action_label: str) -> str:
    """Return user-facing confirmation expiry text."""
    return (
        "⌛ <b>Подтверждение истекло</b>\n\n"
        f"Окно для действия {escape_html(action_label)} уже закрылось.\n"
        "Запустите его заново из меню."
    )
