"""Unit tests for shared non-shop pokemon card helpers."""

from bot.ui.pokemon_cards import PokemonCardData, build_pokemon_card_keyboard, render_pokemon_card_caption


def test_render_pokemon_card_caption_renders_common_non_shop_fields() -> None:
    caption = render_pokemon_card_caption(
        PokemonCardData(
            pokemon_id=25,
            name="Pikachu",
            rarity="Rare",
            pokemon_type="electric",
            base_hp=35,
            base_attack=55,
            base_defense=40,
            base_stamina=90,
            trainer_label="@ash",
            quantity=2,
            user_pokemon_id=250,
        )
    )
    assert "Pikachu" in caption
    assert "@ash" in caption
    assert "Количество: <b>2</b>" in caption
    assert "ID экземпляра: <b>250</b>" in caption


def test_render_pokemon_card_caption_omits_optional_lines_when_missing() -> None:
    caption = render_pokemon_card_caption(
        PokemonCardData(
            pokemon_id=150,
            name="Mewtwo",
            rarity="Legendary",
            pokemon_type=None,
            base_hp=106,
            base_attack=110,
            base_defense=90,
            base_stamina=130,
        )
    )
    assert "Тренер:" not in caption
    assert "Количество:" not in caption
    assert "ID экземпляра:" not in caption
    assert "Тип: <b>unknown</b>" in caption


def test_render_pokemon_card_caption_escapes_html_fields() -> None:
    caption = render_pokemon_card_caption(
        PokemonCardData(
            pokemon_id=25,
            name="Pika<b>chu</b>",
            rarity="Rare<script>",
            pokemon_type="electric&fire",
            base_hp=35,
            base_attack=55,
            base_defense=40,
            base_stamina=90,
            trainer_label='@ash<&>',
        )
    )
    assert "Pika&lt;b&gt;chu&lt;/b&gt;" in caption
    assert "Rare&lt;script&gt;" in caption
    assert "electric&amp;fire" in caption
    assert "@ash&lt;&amp;&gt;" in caption


def test_build_pokemon_card_keyboard_can_include_market_button() -> None:
    keyboard = build_pokemon_card_keyboard("session-1", include_market_button=True)
    assert keyboard.inline_keyboard[0][0].text == "🏪 Рынок"
    assert keyboard.inline_keyboard[0][0].callback_data == "menu:mce:session-1"


def test_build_pokemon_card_keyboard_can_include_release_button() -> None:
    keyboard = build_pokemon_card_keyboard(
        "session-2",
        include_market_button=True,
        include_release_button=True,
    )
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "🏪 Рынок" in labels
    assert "🕊 Отпустить" in labels
    assert "menu:pkr:session-2" in callbacks


def test_build_pokemon_card_keyboard_can_include_extra_button() -> None:
    keyboard = build_pokemon_card_keyboard(
        "session-3",
        include_market_button=True,
        include_release_button=True,
        include_extra_button=True,
    )
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "⚙️ Дополнительно" in labels
    assert "menu:pkm:session-3" in callbacks
