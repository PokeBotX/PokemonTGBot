import asyncio

from db import Database


async def test_connection():
    db = Database()
    await db.connect()
    try:
        await db.init_schema()
        print("Схема БД готова")

        user_id = await db.get_or_create_user(telegram_id=123456789, username="roman")
        await db.add_balance(user_id, "pokedollar", 500)
        await db.add_balance(user_id, "pokecoin", 3)
        balances = await db.get_balances(user_id)
        print("Баланс пользователя:", balances)

        pikachu_id = await db.add_species_if_missing("Pikachu", "rare")
        caught_id = await db.catch_pokemon(user_id, pikachu_id, level=7)
        print(f"Пойман покемон, запись id={caught_id}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
