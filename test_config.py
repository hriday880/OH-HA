import os
os.environ["TELEGRAM_BOT_TOKEN"] = "my-secret-token"
from bot.config import load_config
cfg = load_config()
print(f"TOKEN: {cfg.telegram_bot_token}")
