import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

import src.config as config
import src.telegram_bot.session as session
from src.agent.orchestrator import agent_app

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
        # Determine the time of day dynamically
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"
            
        agent_name = getattr(config, "AGENT_NAME", "Frontdesk")
        business_name = getattr(config, "BUSINESS_NAME", "our business")
        
        welcome_text = (
            f"👋 Good {time_of_day}! Welcome to <b>{business_name}</b>.\n\n"
            f"I am <b>{agent_name}</b>, your virtual concierge. Here is what I can help you with:\n\n"
            f"🔹 Answer questions about our services and policies\n"
            f"🔹 Provide contact info and booking details\n"
            f"🔹 Escalate and connect you to our staff if you need direct help\n\n"
            f"What can I assist you with today? 😊"
        )
        await update.message.reply_text(welcome_text, parse_mode="HTML")

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

def format_for_telegram(text: str) -> list[str]:
    """Converts standard Markdown formatting into clean Telegram HTML and splits into visual 'cards' if too long."""
    if not text:
        return [""]
        
    # 1. Escape basic HTML tags to avoid parser failures (since Telegram parse_mode='HTML' is very strict)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # 2. Re-enable allowed HTML tags for formatting
    # Convert bold **text** or __text__ -> <b>text</b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.*?)__", r"<b>\1</b>", text)
    
    # Convert italic *text* or _text_ -> <i>text</i>
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)
    
    # Convert code blocks ```...``` -> <pre>...</pre>
    text = re.sub(r"```(?:[a-zA-Z]+)?\n?(.*?)\n?```", r"<pre>\1</pre>", text, flags=re.DOTALL)
    
    # Convert inline code `code` -> <code>code</code>
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)
    
    # 3. Beautify headers with anchors and visual dividers
    text = re.sub(r"^#+\s+(.*?)$", r"\n<b>📍 \1</b>\n━━━━━━━━━━━━━━━━━━━━", text, flags=re.MULTILINE)
    
    # 4. Convert lists (+, -, *) to custom emoji bullets
    text = re.sub(r"^\s*[\*\-\+]\s+", "🔹 ", text, flags=re.MULTILINE)
    
    # 5. Split into separate message cards if there are large text blocks (e.g. double newlines)
    # This keeps paragraph bubbles short and neat!
    raw_blocks = text.split("\n\n")
    cards = []
    current_card = []
    current_length = 0
    
    for block in raw_blocks:
        block_stripped = block.strip()
        if not block_stripped:
            continue
        
        # If adding this block exceeds 800 characters, make it a new card/message
        if current_length + len(block_stripped) > 800 or "━━━━━━━━━━━━━━━━━━━━" in block_stripped:
            if current_card:
                cards.append("\n\n".join(current_card))
                current_card = []
                current_length = 0
        
        current_card.append(block_stripped)
        current_length += len(block_stripped) + 2
        
    if current_card:
        cards.append("\n\n".join(current_card))
        
    return [c for c in cards if c]

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
                logger.info(f"🔄 [Admin Relay] Relayed message from Admin ({chat_id}) to Visitor ({active_visitor_id}): \"{user_message}\"")
                await update.message.reply_text(f"🚀 Relayed message to visitor.")
            except Exception as e:
                logger.error(f"❌ Failed to relay message to visitor {active_visitor_id}: {e}")
                await update.message.reply_text(f"❌ Failed to relay message: {e}")
        else:
            await update.message.reply_text(
                "You are currently not connected to any visitor.\n"
                "When a visitor requests help, click the 'Reply' button in their alert to connect."
            )
        return

    # CASE 2: Message is from a Visitor
    logger.info(f"📥 [Incoming Visitor Message] Chat ID: {chat_id} | Message: \"{user_message}\"")
    
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

    # Post initial "Thinking..." status card
    status_msg = await update.message.reply_text("🧠 <i>Thinking...</i>", parse_mode="HTML")

    # D. Call the LangGraph Orchestrator
    try:
        config_run = {"configurable": {"thread_id": chat_id, "tenant_id": "standalone"}}
        result = await agent_app.ainvoke(
            {"messages": [("user", user_message)]},
            config=config_run
        )
        
        # Get final response and the classified intent
        content_val = result["messages"][-1].content
        if isinstance(content_val, list):
            final_response = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val])
        else:
            final_response = str(content_val)
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
            
        # Parse and format response into HTML cards
        cards = format_for_telegram(final_response)
        
        logger.info(f"📤 [Outgoing Bot Response] Chat ID: {chat_id} | Intent: {intent} | Response: \"{final_response}\"")
        
        # Edit the "Thinking..." status message with the first card
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=cards[0],
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        # Send subsequent cards as new message bubbles
        for card in cards[1:]:
            await context.bot.send_message(
                chat_id=chat_id,
                text=card,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Error executing agent app: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="⚠️ <i>I apologize, but I encountered an error. Please try again in a moment.</i>",
            parse_mode="HTML"
        )

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
