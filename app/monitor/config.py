import os

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_TOKEN_TECX = os.getenv("BOT_TOKEN_TECX", "")
BOT_TOKEN_GOFIBRA = os.getenv("BOT_TOKEN_GOFIBRA", "")

GRUPO_1 = os.getenv("GRUPO_1", "")
GRUPO_2 = os.getenv("GRUPO_2", "")
GRUPO_3 = os.getenv("GRUPO_3", "")
GRUPO_ALERTAS = os.getenv("GRUPO_ALERTAS", "")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
INSTALL_CHECK_INTERVAL = int(os.getenv("INSTALL_CHECK_INTERVAL", "60"))
ROUTE_CHECK_INTERVAL = int(os.getenv("ROUTE_CHECK_INTERVAL", "30"))
MIN_OFFLINE_DURATION = int(os.getenv("MIN_OFFLINE_DURATION", "180"))

BASE_DIR = os.getenv("MONITOR_BASE_DIR", "/opt/monitor_os")
LOG_DIR = os.path.join(BASE_DIR, "logs")
TMP_DIR = os.path.join(BASE_DIR, "tmp")

TMP_HISTORY_DIR = os.path.join(TMP_DIR, "history")
TMP_SIGNALS_DIR = os.path.join(TMP_DIR, "signals")
TMP_INSTALL_DIR = os.path.join(TMP_DIR, "installations")
TMP_OFFLINE_DIR = os.path.join(TMP_DIR, "offline")
TMP_REMOVED_DIR = os.path.join(TMP_DIR, "removed")
TMP_PPPOE_MAP_DIR = os.path.join(TMP_DIR, "pppoe_map")

LOG_FILE = os.path.join(LOG_DIR, "monitor_os.log")
