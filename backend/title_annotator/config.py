import os
from typing import Literal

TRUE_VALUES = {"true", "1"}


class Config():
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL",
                                      "sqlite+aiosqlite:///database.db")

        self.PRODUCTION = os.getenv(
            "PRODUCTION", str(False)).lower() in TRUE_VALUES
        self.PORT = int(os.getenv("PORT", 8002))
        self.ALLOWED_ORIGIN = os.getenv(
            "ALLOWED_ORIGIN", "http://localhost:9000")
        self.JWT_PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "supersecret")
        self.JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", None)
        self.LOGIN_EXPIRE_HOURS = int(os.getenv("LOGIN_EXPIRE_HOURS", 0))
        self.LOGIN_EXPIRE_MINUTES = int(os.getenv("LOGIN_EXPIRE_MINUTES", 2))
        self.LOGIN_EXPIRE_SECONDS = int(os.getenv("LOGIN_EXPIRE_SECONDS", 0))
        self.INVITE_TOKEN_FILE = os.getenv(
            "INVITE_TOKEN_FILE", "./invite_tokens.txt"
        )


config = Config()
