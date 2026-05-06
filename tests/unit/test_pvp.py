"""Unit tests for PvP battle helpers."""

from bot.handlers.sections.pvp import (
    PvpBattleSnapshot,
    _damage_from_roll,
    _playback_delay_seconds,
    _render_battle_log_lines,
    _roll_result_label,
    _run_pvp_battle,
    _stat_triangle_modifier,
    _type_roll_modifier,
)


def _snapshot(
    name: str,
    *,
    pokemon_types: tuple[str, ...],
    hp: int = 100,
    attack: int = 70,
    defense: int = 60,
    speed: int = 65,
) -> PvpBattleSnapshot:
    return PvpBattleSnapshot(
        user_pokemon_id=1,
        pokemon_id=1,
        image_credit_id=None,
        name=name,
        form_badge=None,
        pokemon_types=pokemon_types,
        max_hp=hp,
        current_hp=hp,
        attack=attack,
        defense=defense,
        speed=speed,
    )


def test_type_roll_modifier_is_neutral_when_one_type_is_effective_and_other_is_resisted() -> None:
    attacker_types = ("fire", "grass")
    defender_types = ("water",)

    assert _type_roll_modifier(attacker_types, defender_types) == 0


def test_type_roll_modifier_stacks_when_both_attacker_types_are_effective() -> None:
    attacker_types = ("water", "grass")
    defender_types = ("rock",)

    assert _type_roll_modifier(attacker_types, defender_types) == 3


def test_stat_triangle_modifier_rewards_attack_speed_and_defense_edges() -> None:
    attacker = _snapshot("A", pokemon_types=("fire",), attack=90, defense=80, speed=85)
    defender = _snapshot("D", pokemon_types=("grass",), attack=40, defense=60, speed=50)

    assert _stat_triangle_modifier(attacker, defender) > 0


def test_roll_result_labels_follow_spec_bands() -> None:
    assert _roll_result_label(-1) == "miss"
    assert _roll_result_label(0) == "weak"
    assert _roll_result_label(5) == "weak"
    assert _roll_result_label(6) == "normal"
    assert _roll_result_label(11) == "normal"
    assert _roll_result_label(12) == "effective"
    assert _roll_result_label(17) == "effective"
    assert _roll_result_label(18) == "supereffective"


def test_damage_from_roll_only_zeroes_on_miss() -> None:
    attacker = _snapshot("A", pokemon_types=("fire",), attack=20, defense=20, speed=20)
    defender = _snapshot("D", pokemon_types=("grass",), attack=20, defense=200, speed=20)

    assert _damage_from_roll(attacker, defender, -1) == 0
    assert _damage_from_roll(attacker, defender, 0) >= 1
    assert _damage_from_roll(attacker, defender, 18) >= 1


def test_new_damage_formula_keeps_regular_hits_small() -> None:
    attacker = _snapshot("A", pokemon_types=("fire",), hp=100, attack=72, defense=40, speed=55)
    defender = _snapshot("D", pokemon_types=("grass",), hp=100, attack=50, defense=72, speed=45)

    damage = _damage_from_roll(attacker, defender, 11)

    assert 1 <= damage <= 10


def test_run_pvp_battle_produces_one_winner() -> None:
    challenger = _snapshot("Challenger", pokemon_types=("water",), hp=80, attack=90, defense=60, speed=70)
    defender = _snapshot("Defender", pokemon_types=("fire",), hp=80, attack=50, defense=40, speed=40)

    result = _run_pvp_battle(challenger=challenger, defender=defender)

    assert result.winner_side in {"challenger", "defender"}
    assert result.turns
    assert (result.challenger.current_hp == 0) ^ (result.defender.current_hp == 0)


def test_run_pvp_battle_no_longer_usually_ends_in_one_turn() -> None:
    challenger = _snapshot("Challenger", pokemon_types=("water",), hp=95, attack=65, defense=110, speed=65)
    defender = _snapshot("Defender", pokemon_types=("rock",), hp=80, attack=80, defense=100, speed=20)

    result = _run_pvp_battle(challenger=challenger, defender=defender)

    assert len(result.turns) > 1


def test_render_battle_log_lines_adds_spacing_between_entries() -> None:
    rendered = _render_battle_log_lines(["Первая атака.", "Вторая атака."])

    assert rendered == ["• Первая атака.", "", "• Вторая атака."]


def test_playback_delay_defaults_to_one_and_half_seconds() -> None:
    class DummyContext:
        application = type("Application", (), {"bot_data": {}})()

    assert _playback_delay_seconds(DummyContext()) == 1.5
