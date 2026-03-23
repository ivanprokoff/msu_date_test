from dataclasses import dataclass
import os

def _parse_admin_ids(raw: str) -> set[int]:
    return {int(x.strip()) for x in raw.split(",") if x.strip()}

# Список факультетов МГУ (добавил основные для тестов)
FACULTIES = {
    "vmk": "ВМК",
    "mech": "Мехмат",
    "ff": "ФизФак",
    "econ": "Эконом",
    "law": "Юрфак",
    "chem": "ХимФак",
    "bio": "БиоФак",
    "fbb": "ФББ",
    "fgu": "ФГУ"
}

@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    db_path: str

def load_settings() -> Settings:
    bot_token = os.environ["BOT_TOKEN"]
    admin_ids = _parse_admin_ids(os.environ.get("ADMIN_TG_IDS", ""))
    db_path = os.environ.get("DB_PATH", "/data/bot.db")
    return Settings(bot_token=bot_token, admin_ids=admin_ids, db_path=db_path)

settings = load_settings()