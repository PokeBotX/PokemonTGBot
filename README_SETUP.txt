=== PokéCollect Bot - Setup Instructions ===

1. Install UV (Python package manager):
   curl -LsSf https://astral.sh/uv/install.sh | sh

2. Create .env file with your bot token:
   echo "TELEGRAM_BOT_TOKEN=your_token_here" > .env

3. Install dependencies (automatic with UV):
   uv sync

4. Run the bot:
   uv run python main.py

=== Project Structure ===
- bot/           - Bot source code
- main.py        - Entry point
- pyproject.toml - Dependencies
- tests/         - Unit & integration tests

=== Dependencies ===
- python-telegram-bot
- structlog (JSON logging)

