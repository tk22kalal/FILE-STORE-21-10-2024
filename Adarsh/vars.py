import os
from os import getenv, environ
from dotenv import load_dotenv

load_dotenv()


class Var(object):
    MULTI_CLIENT = False
    name = str(getenv('name', 'Nobita-Stream-Bot'))
    SLEEP_THRESHOLD = int(getenv('SLEEP_THRESHOLD', '60'))
    BIN_CHANNEL = int(getenv('BIN_CHANNEL', ''))
    WORKERS = int(getenv('WORKERS', '4'))
    PORT = int(getenv('PORT', 8080))
    BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
    PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  # 20 minutes
    NO_PORT = bool(getenv('NO_PORT', False))
    OWNER_USERNAME = str(getenv('OWNER_USERNAME', 'NobiDeveloperr'))

    # ── Heroku detection ────────────────────────────────────────────────────────
    if 'DYNO' in environ:
        ON_HEROKU = True
        APP_NAME = str(getenv('APP_NAME'))
    else:
        ON_HEROKU = False
        APP_NAME = None

    # ── Fixed FQDN & URL (always use the same domain) ──────────────────────────
    FQDN = "stream11.nextpulse.workers.dev"
    HAS_SSL = True
    URL = f"https://{FQDN}/"

    # ── Other optional environment variables ───────────────────────────────────
    DATABASE_URL = str(getenv('DATABASE_URL', ''))
    UPDATES_CHANNEL = str(getenv('UPDATES_CHANNEL', None))
    BANNED_CHANNELS = list(set(int(x) for x in str(getenv("BANNED_CHANNELS", "")).split()))
