import sys
import logging
from src.telegram_bot.bot import build_bot_app

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger("frontdesk-main")

def main():
    print("---------------------------------------------")
    print("🚀 Booting Front Desk Telegram Bot...")
    print("Loading configurations and initializing SQLite...")
    
    try:
        app = build_bot_app()
        print("SQLite Database initialized successfully.")
        print("Bot is now starting up in polling mode...")
        print("Press Ctrl+C to stop.")
        print("---------------------------------------------")
        
        # Start the bot. This blocks until Ctrl+C is pressed.
        app.run_polling()
        
    except ValueError as val_err:
        logger.error(f"Configuration Error: {val_err}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Critical error during boot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
