"""Integration tests for command and section handlers."""
import pytest
from unittest.mock import AsyncMock, Mock
from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import ContextTypes

from bot.handlers.commands import changename_command, collection_command, menu_command, profile_command, search_command, section_command, shop_command, start_command
from bot.handlers.sections.profile import handle_profile_text_input, profile_handler
from bot.handlers.sections.shop import shop_handler
from bot.handlers.sections.back import back_to_menu_handler
from bot.navigation.session import session_store, MenuSession
from bot.db.database import (
    CollectionEntry,
    CollectionFilterState,
    CollectionPage,
    MarketBrowsePage,
    MarketBrowseState,
    MarketListingSummary,
    PokemonSearchEntry,
    ProfileCoverCandidate,
    ProfileRarityProgress,
    ProfileSummary,
    ShopError,
    ShopView,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()
    yield
    session_store._sessions.clear()
    session_store._callback_locks.clear()
    session_store._pending_inputs.clear()


@pytest.fixture
def mock_update():
    """Create a mock Update for private chat."""
    user = Mock(spec=User)
    user.id = 12345
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    
    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None
    
    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    
    return update


@pytest.mark.asyncio
async def test_start_command_sends_menu(mock_update):
    """Test /start command sends main menu."""
    # Mock send_message
    sent_message = Mock(spec=Message)
    sent_message.message_id = 101
    sent_message.edit_reply_markup = AsyncMock()
    
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Execute command
    await start_command(mock_update, context)
    
    # Verify message was sent
    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    
    # Check text contains welcome message
    assert "Добро пожаловать" in call_args.kwargs["text"]
    assert call_args.kwargs["parse_mode"] == "HTML"
    
    # Verify keyboard was updated with real session_id
    assert sent_message.edit_reply_markup.called
    
    # Verify session was created
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_start_command_new_user_shows_info(mock_update):
    sent_message = Mock(spec=Message)
    sent_message.message_id = 1011
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, True))
    db.consume_start_guide_flag = AsyncMock(return_value=True)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await start_command(mock_update, context)

    call_args = mock_update.effective_chat.send_message.call_args
    assert "общий гайд по боту" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called


@pytest.mark.asyncio
async def test_start_command_existing_user_sends_menu_when_guide_already_seen(mock_update):
    sent_message = Mock(spec=Message)
    sent_message.message_id = 1012
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, False))
    db.consume_start_guide_flag = AsyncMock(return_value=False)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await start_command(mock_update, context)

    call_args = mock_update.effective_chat.send_message.call_args
    assert "Добро пожаловать" in call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_shop_command_first_entry_shows_info_instead_of_shop(mock_update):
    sent_message = Mock(spec=Message)
    sent_message.message_id = 1013
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_or_create_user_status = AsyncMock(return_value=(1, True))
    db.consume_start_guide_flag = AsyncMock(return_value=True)
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await shop_command(mock_update, context)

    call_args = mock_update.effective_chat.send_message.call_args
    assert "общий гайд по боту" in call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_menu_command_sends_menu(mock_update):
    """Test /menu command sends main menu."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 102
    sent_message.edit_reply_markup = AsyncMock()
    
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await menu_command(mock_update, context)
    
    # Verify message was sent
    assert mock_update.effective_chat.send_message.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_menu_command_escapes_html_special_chars_in_user_label(mock_update):
    sent_message = Mock(spec=Message)
    sent_message.message_id = 1021
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    mock_update.effective_user.username = None
    mock_update.effective_user.first_name = "<Ash&Co>"

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await menu_command(mock_update, context)

    text = mock_update.effective_chat.send_message.call_args.kwargs["text"]
    assert "&lt;Ash&amp;Co&gt;" in text
    assert "<Ash&Co>" not in text


@pytest.mark.asyncio
async def test_shop_command_sends_shop_message(mock_update):
    """Test /shop command sends a fresh shop message."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 103
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=2500,
            pokecoin_balance=15,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=2,
            legendary_pity_counter=3,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await shop_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    assert "добро пожаловать в магазин" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_market_command_sends_market_root(mock_update):
    """Test /market command sends the real market root screen."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 104
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    mock_update.message = Mock()
    mock_update.message.text = "/market"

    db = AsyncMock()
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await section_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    assert "рынок открыт" in call_args.kwargs["text"]
    assert "pokecoin" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_market_command_can_open_buy_browse_screen() -> None:
    from bot.handlers.sections.market import show_market_screen, MARKET_VIEW_BUY

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    sent_message = Mock(spec=Message)
    sent_message.message_id = 190
    sent_message.edit_reply_markup = AsyncMock()
    chat.send_message = AsyncMock(return_value=sent_message)

    message = Mock(spec=Message)
    message.message_id = 191
    message.chat = chat
    message.message_thread_id = None

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.get_market_listings_page = AsyncMock(
        return_value=MarketBrowsePage(
            entries=[
                MarketListingSummary(
                    listing_id=1,
                    seller_user_id=777,
                    seller_label="@misty",
                    user_pokemon_id=250,
                    pokemon_id=25,
                    name="Pikachu",
                    rarity="Rare",
                    pokemon_type="electric",
                    price=500,
                    status="active",
                    listed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                    expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                    days_remaining=5,
                    image_credit_id=None,
                )
            ],
            filter_state=MarketBrowseState(),
            total_entries=1,
            current_page=1,
            total_pages=1,
            current_balance=900,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await show_market_screen(update, context, screen=MARKET_VIEW_BUY)

    call_args = chat.send_message.call_args
    assert "активные лоты" in call_args.kwargs["text"]
    assert "Pikachu" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called


@pytest.mark.asyncio
async def test_collection_command_sends_collection_section(mock_update):
    """Test /collection command sends the collection screen."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 105
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_collection_page = AsyncMock(
        return_value=CollectionPage(
            entries=[
                CollectionEntry(
                    pokemon_id=25,
                    sample_user_pokemon_id=250,
                    name="Pikachu",
                    rarity="Rare",
                    pokemon_type="electric",
                    quantity=2,
                    base_hp=35,
                    base_attack=55,
                    base_defense=40,
                    base_stamina=90,
                    image_credit_id=None,
                )
            ],
            filter_state=CollectionFilterState(),
            total_entries=1,
            current_page=1,
            total_pages=1,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await collection_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    assert "ваша коллекция" in call_args.kwargs["text"]
    assert "Pikachu x2 | id: 25" in call_args.kwargs["text"]
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_profile_command_sends_profile_section(mock_update):
    """Test /profile command sends the profile screen."""
    sent_message = Mock(spec=Message)
    sent_message.message_id = 106
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username="ash",
            nickname="Ash",
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            total_unique_owned=2,
            total_catalog=1025,
            total_unique_percent=0,
            rarity_progress=(
                ProfileRarityProgress("Legendary", 0, 50, 0),
                ProfileRarityProgress("Epic", 1, 100, 1),
                ProfileRarityProgress("Rare", 1, 250, 0),
                ProfileRarityProgress("Common", 0, 625, 0),
            ),
            profile_pic_credit_id=None,
            cover_pokemon_name=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot

    await profile_command(mock_update, context)

    assert context_bot.send_photo.called or context_bot.send_message.called
    if context_bot.send_photo.called:
        call_args = context_bot.send_photo.call_args
        rendered_text = call_args.kwargs["caption"]
    else:
        call_args = context_bot.send_message.call_args
        rendered_text = call_args.kwargs["text"]
    assert "ваш профиль" in rendered_text
    assert "12345" in rendered_text
    assert sent_message.edit_reply_markup.called
    assert len(session_store._sessions) == 1


@pytest.mark.asyncio
async def test_profile_command_escapes_html_special_chars_in_profile_label(mock_update):
    sent_message = Mock(spec=Message)
    sent_message.message_id = 1062
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)

    mock_update.effective_user.username = None
    mock_update.effective_user.first_name = "<Ash>"
    mock_update.message = Mock(spec=Message)
    mock_update.message.text = "/profile"

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username=None,
            nickname="<Ash>",
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            total_unique_owned=2,
            total_catalog=1025,
            total_unique_percent=0,
            rarity_progress=(),
            profile_pic_credit_id=None,
            cover_pokemon_name=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot

    await profile_command(mock_update, context)

    if context_bot.send_photo.called:
        rendered_text = context_bot.send_photo.call_args.kwargs["caption"]
    else:
        rendered_text = context_bot.send_message.call_args.kwargs["text"]
    assert "&lt;Ash&gt;" in rendered_text
    assert "<Ash>" not in rendered_text


@pytest.mark.asyncio
async def test_profile_command_in_group_without_target_uses_requester_profile() -> None:
    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = -10012345
    chat.type = "supergroup"

    sent_message = Mock(spec=Message)
    sent_message.message_id = 1061
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)

    message = Mock(spec=Message)
    message.message_id = 1060
    message.chat = chat
    message.from_user = user
    message.message_thread_id = None
    message.text = "/profile"
    message.reply_to_message = None

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    update.message = message

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username="ash",
            nickname=None,
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            total_unique_owned=1,
            total_catalog=1025,
            total_unique_percent=0,
            rarity_progress=(),
            profile_pic_credit_id=None,
            cover_pokemon_name=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot

    await profile_command(update, context)

    call_args = context_bot.send_photo.call_args if context_bot.send_photo.called else context_bot.send_message.call_args
    rendered_text = call_args.kwargs["caption"] if context_bot.send_photo.called else call_args.kwargs["text"]
    assert "Ash" in rendered_text
    assert "12345" in rendered_text
    assert not db.get_profile_summary_by_telegram_id.called
    assert not db.get_profile_summary_by_username.called


@pytest.mark.asyncio
async def test_profile_nickname_button_shows_command_hint() -> None:
    session = MenuSession(
        session_id="profile-session",
        chat_id=12345,
        message_id=777,
        user_id=12345,
        message_thread_id=None,
    )

    query = AsyncMock(spec=CallbackQuery)
    query.data = "menu:prn:profile-session"
    query.edit_message_text = AsyncMock()

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username="ash",
            nickname="Ash",
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                total_unique_owned=2,
                total_catalog=1025,
                total_unique_percent=0,
                rarity_progress=(),
                profile_pic_credit_id=None,
                cover_pokemon_name=None,
            )
        )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await profile_handler(update, context, session)

    if query.edit_message_text.called:
        edited_text = query.edit_message_text.call_args.kwargs["text"]
    else:
        edited_text = query.edit_message_caption.call_args.kwargs["caption"]
    assert "/changename Артём" in edited_text
    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None


@pytest.mark.asyncio
async def test_changename_command_updates_nickname(mock_update) -> None:
    mock_update.effective_message.text = "/changename New Ash"
    mock_update.effective_chat.send_message = AsyncMock()

    db = AsyncMock()
    db.update_profile_nickname = AsyncMock(return_value="New Ash")
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await changename_command(mock_update, context)

    assert db.update_profile_nickname.called
    assert mock_update.effective_chat.send_message.called


@pytest.mark.asyncio
async def test_profile_cover_search_single_match_updates_cover() -> None:
    session_store.set_pending_input(
        action="profile_cover",
        chat_id=12345,
        user_id=12345,
        source_message_id=777,
        source_message_thread_id=None,
    )

    user = Mock(spec=User)
    user.id = 12345
    user.username = "ash"
    user.first_name = "Ash"

    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.send_message = AsyncMock()

    message = Mock(spec=Message)
    message.message_id = 778
    message.chat = chat
    message.message_thread_id = None
    message.text = "Pikachu"

    update = Mock(spec=Update)
    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    db = AsyncMock()
    db.search_profile_cover_candidates = AsyncMock(
        return_value=[
            ProfileCoverCandidate(
                pokemon_id=25,
                sample_user_pokemon_id=250,
                name="Pikachu",
                rarity="Rare",
                pokemon_type="electric",
                image_credit_id=55,
            )
        ]
    )
    db.update_profile_cover = AsyncMock(return_value=55)
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username="ash",
            nickname="Ash",
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                total_unique_owned=2,
                total_catalog=1025,
                total_unique_percent=0,
                rarity_progress=(),
                profile_pic_credit_id=55,
                cover_pokemon_name=None,
            )
        )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    await handle_profile_text_input(update, context)

    assert db.search_profile_cover_candidates.called
    assert db.update_profile_cover.called
    assert context.bot.edit_message_caption.called or context.bot.edit_message_text.called
    assert chat.send_message.called
    assert session_store.get_pending_input(chat_id=12345, user_id=12345) is None


@pytest.mark.asyncio
async def test_search_command_single_result_sends_card(mock_update) -> None:
    mock_update.message = Mock()
    mock_update.message.text = "/search pikachu"
    mock_update.effective_message = mock_update.message
    mock_update.effective_message.message_id = 120
    mock_update.effective_message.message_thread_id = None

    db = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value=1)
    db.search_pokemon_catalog = AsyncMock(
        return_value=[
            PokemonSearchEntry(
                pokemon_id=25,
                name="Pikachu",
                rarity="Rare",
                pokemon_type="electric",
                base_hp=35,
                base_attack=55,
                base_defense=40,
                base_stamina=90,
                image_credit_id=None,
            )
        ]
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()
    context.bot.send_photo = AsyncMock()
    context.bot.send_message = AsyncMock()

    await search_command(mock_update, context)

    assert db.search_pokemon_catalog.called
    assert context.bot.send_photo.called or context.bot.send_message.called
    call_args = context.bot.send_photo.call_args if context.bot.send_photo.called else context.bot.send_message.call_args
    rendered_text = call_args.kwargs["caption"] if context.bot.send_photo.called else call_args.kwargs["text"]
    assert "Тренер:" not in rendered_text


@pytest.mark.asyncio
async def test_profile_command_opens_replied_user_profile_read_only(mock_update) -> None:
    replied_user = Mock(spec=User)
    replied_user.id = 777
    replied_user.username = "misty"
    replied_user.is_bot = False

    reply_message = Mock(spec=Message)
    reply_message.from_user = replied_user

    sent_message = Mock(spec=Message)
    sent_message.message_id = 180
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)
    mock_update.effective_message.reply_to_message = reply_message
    mock_update.effective_message.text = "/profile"

    db = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value=2)
    db.get_profile_summary_by_telegram_id = AsyncMock(
        return_value=ProfileSummary(
            user_id=2,
            telegram_id=777,
            tg_username="misty",
            nickname=None,
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                total_unique_owned=4,
                total_catalog=1025,
                total_unique_percent=0,
                rarity_progress=(),
                profile_pic_credit_id=None,
                cover_pokemon_name=None,
            )
        )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot
    mock_update.effective_chat.type = "group"

    await profile_command(mock_update, context)

    call_args = context_bot.send_photo.call_args if context_bot.send_photo.called else context_bot.send_message.call_args
    rendered_text = call_args.kwargs["caption"] if context_bot.send_photo.called else call_args.kwargs["text"]
    assert "@misty" in rendered_text
    assert sent_message.edit_reply_markup.called


@pytest.mark.asyncio
async def test_profile_command_ignores_reply_target_in_private_chat(mock_update) -> None:
    replied_user = Mock(spec=User)
    replied_user.id = 777
    replied_user.username = "misty"
    replied_user.is_bot = False

    reply_message = Mock(spec=Message)
    reply_message.from_user = replied_user

    sent_message = Mock(spec=Message)
    sent_message.message_id = 182
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)
    mock_update.effective_message.reply_to_message = reply_message
    mock_update.effective_message.text = "/profile"

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username="ash",
            nickname=None,
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            total_unique_owned=4,
            total_catalog=1025,
            total_unique_percent=0,
            rarity_progress=(),
            profile_pic_credit_id=None,
            cover_pokemon_name=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot

    await profile_command(mock_update, context)

    assert db.get_profile_summary.called
    assert not db.get_profile_summary_by_telegram_id.called


@pytest.mark.asyncio
async def test_profile_command_ignores_reply_target_for_topic_messages(mock_update) -> None:
    replied_user = Mock(spec=User)
    replied_user.id = 777
    replied_user.username = "misty"
    replied_user.is_bot = False

    reply_message = Mock(spec=Message)
    reply_message.from_user = replied_user

    sent_message = Mock(spec=Message)
    sent_message.message_id = 183
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)
    mock_update.effective_message.reply_to_message = reply_message
    mock_update.effective_message.text = "/profile"
    mock_update.effective_message.is_topic_message = True
    mock_update.effective_chat.type = "supergroup"

    db = AsyncMock()
    db.get_profile_summary = AsyncMock(
        return_value=ProfileSummary(
            user_id=1,
            telegram_id=12345,
            tg_username="ash",
            nickname=None,
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            total_unique_owned=4,
            total_catalog=1025,
            total_unique_percent=0,
            rarity_progress=(),
            profile_pic_credit_id=None,
            cover_pokemon_name=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot
    mock_update.effective_message.message_thread_id = 500
    reply_message.message_id = 500

    await profile_command(mock_update, context)

    assert db.get_profile_summary.called
    assert not db.get_profile_summary_by_telegram_id.called


@pytest.mark.asyncio
async def test_profile_command_uses_reply_target_for_explicit_topic_reply(mock_update) -> None:
    replied_user = Mock(spec=User)
    replied_user.id = 777
    replied_user.username = "misty"
    replied_user.is_bot = False

    reply_message = Mock(spec=Message)
    reply_message.from_user = replied_user
    reply_message.message_id = 501

    sent_message = Mock(spec=Message)
    sent_message.message_id = 184
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)
    mock_update.effective_message.reply_to_message = reply_message
    mock_update.effective_message.text = "/profile"
    mock_update.effective_message.is_topic_message = True
    mock_update.effective_message.message_thread_id = 500
    mock_update.effective_chat.type = "supergroup"

    db = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value=2)
    db.get_profile_summary_by_telegram_id = AsyncMock(
        return_value=ProfileSummary(
            user_id=2,
            telegram_id=777,
            tg_username="misty",
            nickname=None,
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            total_unique_owned=4,
            total_catalog=1025,
            total_unique_percent=0,
            rarity_progress=(),
            profile_pic_credit_id=None,
            cover_pokemon_name=None,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot

    await profile_command(mock_update, context)

    assert db.get_profile_summary_by_telegram_id.called


@pytest.mark.asyncio
async def test_profile_command_opens_user_by_username_argument(mock_update) -> None:
    sent_message = Mock(spec=Message)
    sent_message.message_id = 181
    sent_message.edit_reply_markup = AsyncMock()
    context_bot = Mock()
    context_bot.send_photo = AsyncMock(return_value=sent_message)
    context_bot.send_message = AsyncMock(return_value=sent_message)
    mock_update.effective_message.text = "/profile @misty"
    mock_update.message = mock_update.effective_message

    db = AsyncMock()
    db.get_profile_summary_by_username = AsyncMock(
        return_value=ProfileSummary(
            user_id=2,
            telegram_id=777,
            tg_username="misty",
            nickname=None,
            language="ru",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                total_unique_owned=4,
                total_catalog=1025,
                total_unique_percent=0,
                rarity_progress=(),
                profile_pic_credit_id=None,
                cover_pokemon_name=None,
            )
        )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = context_bot

    await profile_command(mock_update, context)

    call_args = context_bot.send_photo.call_args if context_bot.send_photo.called else context_bot.send_message.call_args
    rendered_text = call_args.kwargs["caption"] if context_bot.send_photo.called else call_args.kwargs["text"]
    assert "@misty" in rendered_text
    assert sent_message.edit_reply_markup.called


@pytest.mark.asyncio
async def test_profile_command_unknown_username_sends_warning(mock_update) -> None:
    mock_update.effective_message.text = "/profile @unknown_user"
    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.send_message = AsyncMock()

    db = AsyncMock()
    db.get_profile_summary_by_username = AsyncMock(side_effect=ShopError("Я пока не знаю этого пользователя."))
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application
    context.bot = Mock()

    await profile_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    call_args = mock_update.effective_chat.send_message.call_args
    sent_text = call_args.args[0] if call_args.args else call_args.kwargs["text"]
    assert "Я пока не знаю этого пользователя." in sent_text


@pytest.mark.asyncio
async def test_search_command_multiple_results_sends_list(mock_update) -> None:
    sent_message = Mock(spec=Message)
    sent_message.message_id = 130
    sent_message.edit_reply_markup = AsyncMock()
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    mock_update.message = Mock()
    mock_update.message.text = "/search char"
    mock_update.effective_message = mock_update.message
    mock_update.effective_message.message_id = 121
    mock_update.effective_message.message_thread_id = None

    db = AsyncMock()
    db.get_or_create_user = AsyncMock(return_value=1)
    db.search_pokemon_catalog = AsyncMock(
        return_value=[
            PokemonSearchEntry(4, "Charmander", "Rare", "fire", 39, 52, 43, 65, None),
            PokemonSearchEntry(5, "Charmeleon", "Rare", "fire", 58, 64, 58, 80, None),
        ]
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    await search_command(mock_update, context)

    assert mock_update.effective_chat.send_message.called
    assert sent_message.edit_reply_markup.called


@pytest.mark.asyncio
async def test_section_handler_shows_placeholder():
    """Test shop handler renders the shop screen."""
    # Create a session
    session = MenuSession(
        session_id="test-session-123",
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    session_store._sessions[session.session_id] = session
    
    # Mock callback query
    query = AsyncMock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock()
    
    user = Mock(spec=User)
    user.id = 67890
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    
    message = Mock(spec=Message)
    message.message_id = 100
    message.chat = chat
    
    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    db = AsyncMock()
    db.get_shop_view = AsyncMock(
        return_value=ShopView(
            user_id=1,
            balance=2500,
            pokecoin_balance=0,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=2,
            legendary_pity_counter=3,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        )
    )
    application = Mock()
    application.bot_data = {"db": db}
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.application = application

    # Execute handler
    await shop_handler(update, context, session)
    
    # Verify message was edited
    assert query.edit_message_text.called
    call_args = query.edit_message_text.call_args
    
    # Check shop text
    assert "добро пожаловать в магазин" in call_args.kwargs["text"]
    assert "Ваш баланс" in call_args.kwargs["text"]
    assert "Выберите желаемый раздел" in call_args.kwargs["text"]

    # Verify new session was created for back button
    assert len(session_store._sessions) == 2


@pytest.mark.asyncio
async def test_back_to_menu_handler_returns_to_menu():
    """Test back button returns to main menu."""
    session = MenuSession(
        session_id="test-session-456",
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    session_store._sessions[session.session_id] = session
    
    # Mock callback query
    query = AsyncMock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock()
    
    user = Mock(spec=User)
    user.id = 67890
    
    chat = Mock(spec=Chat)
    chat.id = 12345
    
    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = user
    update.effective_chat = chat
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Execute handler
    await back_to_menu_handler(update, context, session)
    
    # Verify message was edited
    assert query.edit_message_text.called
    call_args = query.edit_message_text.call_args
    
    # Check main menu text
    assert "Добро пожаловать" in call_args.kwargs["text"]
    
    # Verify new session was created
    assert len(session_store._sessions) == 2


@pytest.mark.asyncio
async def test_command_handler_with_forum_topic(mock_update):
    """Test command handler supports forum topics."""
    # Convert to forum topic
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_chat.is_forum = True
    mock_update.effective_message.message_thread_id = 42
    
    sent_message = Mock(spec=Message)
    sent_message.message_id = 200
    sent_message.edit_reply_markup = AsyncMock()
    
    mock_update.effective_chat.send_message = AsyncMock(return_value=sent_message)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    await start_command(mock_update, context)
    
    # Verify message_thread_id was passed
    call_args = mock_update.effective_chat.send_message.call_args
    assert call_args.kwargs.get("message_thread_id") == 42
    
    # Verify session has thread_id
    session_id = list(session_store._sessions.keys())[0]
    session = session_store._sessions[session_id]
    assert session.message_thread_id == 42


@pytest.mark.asyncio
async def test_section_handler_error_handling():
    """Test section handler gracefully handles edit errors."""
    session = MenuSession(
        session_id="test-session-error",
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    
    # Mock callback query that raises error on edit
    query = AsyncMock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock(side_effect=Exception("Message was deleted"))
    
    update = Mock(spec=Update)
    update.callback_query = query
    update.effective_user = Mock(id=67890)
    update.effective_chat = Mock(id=12345)
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Should not raise exception
    await shop_handler(update, context, session)
    
    # Verify edit was attempted
    assert query.edit_message_text.called
