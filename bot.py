import asyncio
import os
import random
from typing import Final

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from db import Database


load_dotenv("poke.env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Добавь TELEGRAM_BOT_TOKEN в poke.env")

POKEMON_POOL: Final[list[tuple[str, str, int]]] = [
    ("Pidgey", "common", 55),
    ("Rattata", "common", 55),
    ("Eevee", "uncommon", 35),
    ("Pikachu", "rare", 20),
    ("Dratini", "epic", 8),
]

REWARD_BY_RARITY: Final[dict[str, int]] = {
    "common": 25,
    "uncommon": 45,
    "rare": 80,
    "epic": 140,
}

db = Database()
dp = Dispatcher()


def _weighted_choice() -> tuple[str, str]:
    names = [item[0] for item in POKEMON_POOL]
    rarities = [item[1] for item in POKEMON_POOL]
    weights = [item[2] for item in POKEMON_POOL]
    idx = random.choices(range(len(names)), weights=weights, k=1)[0]
    return names[idx], rarities[idx]


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    if not message.from_user:
        return

    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    balances = await db.get_balances(user_id)
    if not balances:
        await db.add_balance(user_id, "pokedollar", 100)
        await db.add_balance(user_id, "pokecoin", 1)

    await message.answer(
        "Бот готов. Команды:\n"
        "/catch - поймать покемона\n"
        "/balance - посмотреть валюту\n"
        "/profile - статистика тренера"
    )


@dp.message(Command("balance"))
async def balance_handler(message: Message) -> None:
    if not message.from_user:
        return

    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
    balances = await db.get_balances(user_id)
    pokedollar = balances.get("pokedollar", 0)
    pokecoin = balances.get("pokecoin", 0)
    await message.answer(f"Твой баланс:\nPokéDollar: {pokedollar}\nPokéCoin: {pokecoin}")


@dp.message(Command("profile"))
async def profile_handler(message: Message) -> None:
    if not message.from_user:
        return

    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
    balances = await db.get_balances(user_id)
    pokemon_count = await db.get_user_pokemon_count(user_id)

    await message.answer(
        "Профиль тренера:\n"
        f"Поймано покемонов: {pokemon_count}\n"
        f"PokéDollar: {balances.get('pokedollar', 0)}\n"
        f"PokéCoin: {balances.get('pokecoin', 0)}"
    )


@dp.message(Command("catch"))
async def catch_handler(message: Message) -> None:
    if not message.from_user:
        return

    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
    name, rarity = _weighted_choice()
    species_id = await db.add_species_if_missing(name, rarity)
    level = random.randint(1, 20)
    await db.catch_pokemon(user_id, species_id, level)

    reward = REWARD_BY_RARITY[rarity]
    await db.add_balance(user_id, "pokedollar", reward)

    await message.answer(
        f"Ты поймал {name} ({rarity}) {level} lvl!\n"
        f"+{reward} PokéDollar"
    )


@dp.message(F.text == "/help")
async def help_handler(message: Message) -> None:
    await message.answer("/start /catch /balance /profile")


async def main() -> None:
    await db.connect()
    await db.init_schema()
    bot = Bot(BOT_TOKEN)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
