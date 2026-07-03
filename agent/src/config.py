import os
from dotenv import load_dotenv

# Load the local .env configuration
load_dotenv()

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# LLM Config (Gemini API uses GOOGLE_API_KEY internally)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "our business")
AGENT_NAME = os.getenv("AGENT_NAME", "Frontdesk")
BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "")
BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "")
MAP_URL = os.getenv("MAP_URL", "")
WEBSITE_URL = os.getenv("WEBSITE_URL", "")
BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "America/Los_Angeles")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

# Guardrails & Limits
DAILY_MESSAGE_CAP = int(os.getenv("DAILY_MESSAGE_CAP", "200"))
USER_RATE_LIMIT = int(os.getenv("USER_RATE_LIMIT", "5"))
USER_RATE_WINDOW = int(os.getenv("USER_RATE_WINDOW", "60"))

# Verify essential credentials
def validate_config():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Config Error: TELEGRAM_BOT_TOKEN must be set in .env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("Config Error: GEMINI_API_KEY (or GOOGLE_API_KEY) must be set in .env")
