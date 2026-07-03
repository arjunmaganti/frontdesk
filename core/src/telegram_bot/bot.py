import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

import core.src.config as config
import core.src.telegram_bot.session as session
from core.src.agent.orchestrator import agent_app

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and explains the bot's purpose."""
    chat_id = str(update.effective_chat.id)
    
    if chat_id == str(config.ADMIN_CHAT_ID):
        await update.message.reply_text(
            "👋 Hello Admin! You are logged into the Front Desk Bot control panel.\n\n"
            "Whenever a visitor triggers an escalation, you will receive an alert here with buttons to reply directly."
        )
    else:
        await update.message.reply_text(
            "👋 Welcome! I am the automated Front Desk Assistant.\n\n"
            "How can I help you today? (e.g., Ask me about check-in rules, parking, or Wi-Fi)."
        )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes button clicks from the admin."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = str(update.effective_chat.id)
    
    # Verify only the admin can click buttons
    if chat_id != str(config.ADMIN_CHAT_ID):
        return

    if data.startswith("reply_to_"):
        visitor_chat_id = data.replace("reply_to_", "")
        
        # Enable direct reply mode for the admin
        session.set_active_visitor(visitor_chat_id)
        session.set_visitor_paused(visitor_chat_id, True)
        
        await query.edit_message_text(
            text=f"💬 **Connected to Visitor ({visitor_chat_id})**\n\n"
                 "Any text you send here next will be forwarded directly to the visitor.\n"
                 "To end the conversation and turn the AI back on, click the button below.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Resolve Chat", callback_data=f"resolve_chat_{visitor_chat_id}")
            ]])
        )
        
    elif data.startswith("resolve_chat_"):
        visitor_chat_id = data.replace("resolve_chat_", "")
        
        # Reactivate AI and clear routing state
        session.set_visitor_paused(visitor_chat_id, False)
        session.clear_active_visitor()
        
        await query.edit_message_text(text="✅ **Chat Resolved.** AI assistant is back online for this visitor.")
        
        # Notify the visitor
        try:
            await context.bot.send_message(
                chat_id=visitor_chat_id,
                text="🔔 *The front desk staff has closed the chat. The automated assistant is back online to help you!*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send resolve message to visitor: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages from visitors and the admin."""
    chat_id = str(update.effective_chat.id)
    user_message = update.message.text

    # CASE 1: Message is from the Admin/Owner
    if chat_id == str(config.ADMIN_CHAT_ID):
        # Check who the admin is currently replying to
        active_visitor_id = session.get_active_visitor()
        
        if active_visitor_id:
            # If the admin types /resolve, close it immediately
            if user_message.strip() == "/resolve":
                session.set_visitor_paused(active_visitor_id, False)
                session.clear_active_visitor()
                await update.message.reply_text("✅ Chat resolved. AI bot reactivated.")
                await context.bot.send_message(
                    chat_id=active_visitor_id,
                    text="🔔 *The front desk staff has closed the chat. The automated assistant is back online to help you!*",
                    parse_mode="Markdown"
                )
                return
            
            # Relay the admin's message directly to the visitor
            try:
                await context.bot.send_message(
                    chat_id=active_visitor_id,
                    text=f"✉️ **Front Desk Staff:**\n{user_message}"
                )
                await update.message.reply_text(f"🚀 Relayed message to visitor.")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to relay message: {e}")
        else:
            await update.message.reply_text(
                "You are currently not connected to any visitor.\n"
                "When a visitor requests help, click the 'Reply' button in their alert to connect."
            )
        return

    # CASE 2: Message is from a Visitor
    
    # A. Check if the AI session is paused (Handoff is active and owner has control)
    if session.is_visitor_paused(chat_id):
        # We silently ignore or log the message so the AI doesn't double-reply
        logger.info(f"Visitor {chat_id} messaged, but AI is paused. Waiting for admin.")
        return

    # B. Guardrail 1: Rate Limiter (Spam Protection)
    if session.check_rate_limit(chat_id):
        await update.message.reply_text("⚠️ You are sending messages too quickly. Please wait a moment.")
        return

    # C. Guardrail 2: Daily Budget Cap check
    if session.check_daily_cap():
        await update.message.reply_text(
            "Our automated assistant has reached its maximum query limit for today.\n"
            "If you need immediate assistance, please call our front desk directly."
        )
        return

    # Increment usage count
    session.increment_daily_usage()

    # D. Call the LangGraph Orchestrator
    try:
        config_run = {"configurable": {"thread_id": chat_id, "tenant_id": "standalone"}}
        result = await agent_app.ainvoke(
            {"messages": [("user", user_message)]},
            config=config_run
        )
        
        # Get final response and the classified intent
        final_response = result["messages"][-1].content
        intent = result.get("intent", "kb_query")
        
        # E. Handle Handoff Action
        if intent == "handoff":
            # 1. Pause the AI
            session.set_visitor_paused(chat_id, True)
            
            # 2. Alert the Admin with inline buttons
            keyboard = [
                [
                    InlineKeyboardButton("💬 Reply to Visitor", callback_data=f"reply_to_{chat_id}"),
                    InlineKeyboardButton("✅ Resolve Chat", callback_data=f"resolve_chat_{chat_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=config.ADMIN_CHAT_ID,
                text=f"🚨 **Handoff Escalation Triggered!**\n\n"
                     f"👤 **Visitor Chat ID:** `{chat_id}`\n"
                     f"💬 **Visitor Message:** \"{user_message}\"\n\n"
                     f"AI bot has been muted. Choose an option below:",
                reply_markup=reply_markup
            )
            
        # Send reply back to the visitor
        await update.message.reply_text(final_response)

    except Exception as e:
        logger.error(f"Error executing agent app: {e}")
        await update.message.reply_text("I apologize, but I encountered an error. Please try again in a moment.")

def build_bot_app():
    """Initializes the python-telegram-bot application."""
    # Ensure config variables are set
    config.validate_config()
    
    # Initialize SQLite database
    session.init_db()
    
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Add Command & Message handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return app
