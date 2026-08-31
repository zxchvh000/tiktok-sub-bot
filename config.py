import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8802380295:AAEiNPdXsjOhrRIM19j4aXvP6D-dhHA4qbs")
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip()]
SESSION_DIR = os.path.join(os.path.dirname(__file__), "sessions")
