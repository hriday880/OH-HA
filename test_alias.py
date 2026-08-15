import os
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings

class MyConfig(BaseSettings):
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN"),
    )

os.environ["TELEGRAM_TOKEN"] = "my_token"
cfg = MyConfig()
print("TOKEN:", cfg.telegram_bot_token)
