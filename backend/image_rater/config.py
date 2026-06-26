from pydantic_settings import BaseSettings


class Config(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///database.sqlite"
    PRODUCTION: bool = False
    PORT: int = 8003
    ALLOWED_ORIGIN: str = "http://pchradis2.fit.vutbr.cz:9006"
    JWT_PRIVATE_KEY: str = "supersecret"
    SECRET: str = "XYZ123"
    ADMIN: str = "admin@example.com"
    ADMIN_PASSWORD: str = "admin123"
    STATIC_DIR: str = "static"


config = Config()
