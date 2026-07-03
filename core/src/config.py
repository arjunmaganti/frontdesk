import os
from dotenv import load_dotenv

# Load the local .env configuration
load_dotenv()

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# LLM Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

# Guardrails & Limits
DAILY_MESSAGE_CAP = int(os.getenv("DAILY_MESSAGE_CAP", "200"))
USER_RATE_LIMIT = int(os.getenv("USER_RATE_LIMIT", "5"))
USER_RATE_WINDOW = int(os.getenv("USER_RATE_WINDOW", "60"))

# Verify essential credentials
def validate_config():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Config Error: TELEGRAM_BOT_TOKEN must be set in .env")
    if not ADMIN_CHAT_ID:
        raise ValueError("Config Error: ADMIN_CHAT_ID must be set in .env")
    if not OPENAI_API_KEY:
        raise ValueError("Config Error: OPENAI_API_KEY must be set in .env")
