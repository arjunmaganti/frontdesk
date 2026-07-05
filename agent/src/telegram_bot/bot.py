import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

import src.config as config
import src.telegram_bot.session as session
from src.agent.orchestrator import agent_app
from src.db import get_pg_connection

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and handles visitor and admin deep links."""
    chat_id = str(update.effective_chat.id)
    args = context.args
    
    # 1. Handle Admin Deep Link Activation
    if args and args[0].startswith("a_"):
        business_id = args[0].replace("a_", "")
        biz_name = session.bind_business_admin(business_id, chat_id)
        if biz_name:
            # Retrieve current business configuration to check flyer status
            biz_config = session.get_business_config(business_id)
            flyer_url = biz_config.get("flyer_url") if biz_config else None
            
            welcome_msg = (
                f"✅ <b>Activation Complete!</b>\n\n"
                f"Greetings! You are now successfully connected as the Admin of <b>{biz_name}</b>.\n"
                f"You will receive customer alerts and direct escalations here.\n\n"
            )
            
            if flyer_url:
                welcome_msg += f"📄 <b>Print-Ready Flyer:</b> <a href=\"{flyer_url}\">Download PDF Flyer</a>\n\n"
            else:
                welcome_msg += (
                    f"📄 <b>Flyer Status:</b> Your print-ready marketing flyer is currently being compiled "
                    f"and will be delivered to this chat shortly!\n\n"
                )
                
            welcome_msg += "Type /settings at any time to open your control panel."
            
            await update.message.reply_text(
                welcome_msg,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"⚠️ <b>Onboarding Error</b>\n\n"
                f"Business ID <code>{business_id}</code> was not found in the database.\n"
                f"Please ensure the business has been uploaded to the staging tables first.",
                parse_mode="HTML"
            )
        return

    # 2. Handle Visitor Deep Link Routing
    if args and args[0].startswith("v_"):
        business_id = args[0].replace("v_", "")
        session.set_visitor_business(chat_id, business_id)
        
    # Check if the visitor is linked to any business
    business_id = session.get_visitor_business(chat_id)
    
    # Retrieve business configurations
    biz_config = session.get_business_config(business_id) if business_id else None
    
    # If not a visitor, check if they are a registered admin of a business
    if not biz_config:
        admin_biz = session.get_business_by_admin(chat_id)
        if admin_biz:
            await update.message.reply_text(
                f"👋 Hello Admin! You are logged into the Front Desk control panel for <b>{admin_biz['business_name']}</b>.\n\n"
                f"Whenever a customer triggers an escalation, you will receive an alert here with buttons to reply directly.",
                parse_mode="HTML"
            )
            return
            
        # Default fallback if no business link exists
        await update.message.reply_text(
            "👋 Welcome to Frontdesk!\n\n"
            "To get started, please click the custom chat link provided by the business you're visiting.",
            parse_mode="HTML"
        )
        return

    # Retrieve tenant-specific variables
    agent_name = biz_config.get("agent_name") or "Kim"
    business_name = biz_config.get("business_name") or "our business"
    website_url = biz_config.get("website_url")
    map_url = biz_config.get("map_url")
    timezone_str = biz_config.get("business_timezone") or "America/Los_Angeles"

    # Evaluate dynamic greeting based on timezone local time
    from zoneinfo import ZoneInfo
    from datetime import datetime
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles")
        
    hour = datetime.now(tz).hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    welcome_text = (
        f"👋 Good {time_of_day}! Welcome to <b>{business_name}</b>.\n\n"
        f"I am <b>{agent_name}</b>, your friendly virtual concierge. I am here to make your visit smooth and answer any questions you might have!\n\n"
        f"Here is what I can do for you:\n"
        f"🔹 Answer questions about our services and policies\n"
        f"🔹 Provide location and contact details\n"
        f"🔹 Instantly connect you to our staff if you need direct help\n\n"
        f"How can I assist you today? 😊"
    )

    # Setup welcome markup buttons using the business configs
    welcome_buttons = []
    if website_url:
        welcome_buttons.append(InlineKeyboardButton("🌐 Visit Website", url=website_url))
    if map_url:
        welcome_buttons.append(InlineKeyboardButton("📍 View Map", url=map_url))

    welcome_markup = InlineKeyboardMarkup([welcome_buttons]) if welcome_buttons else None
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=welcome_markup)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the admin settings panel for the registered business owner."""
    chat_id = str(update.effective_chat.id)
    admin_biz = session.get_business_by_admin(chat_id)
    
    if not admin_biz:
        await update.message.reply_text(
            "⚠️ <b>Settings Access Denied</b>\n\n"
            "You are not registered as an admin for any business on this platform.\n"
            "Please use your custom activation link to connect your Telegram account first.",
            parse_mode="HTML"
        )
        return
        
    business_id = admin_biz["business_id"]
    biz_config = session.get_business_config(business_id)
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Recrawl Website", callback_data=f"settings_recrawl_{business_id}"),
            InlineKeyboardButton("📷 Get Customer QR", callback_data=f"settings_qr_{business_id}")
        ]
    ]
    
    # Add link to printable PDF flyer if it has been compiled
    flyer_url = biz_config.get("flyer_url")
    if flyer_url:
        keyboard.append([
            InlineKeyboardButton("📄 Download Flyer (PDF)", url=flyer_url)
        ])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚙️ <b>Settings Dashboard: {biz_config['business_name']}</b>\n\n"
        f"👤 <b>AI Assistant Name:</b> {biz_config['agent_name']}\n"
        f"🌐 <b>Website URL:</b> {biz_config['website_url']}\n"
        f"📍 <b>Phone:</b> {biz_config.get('business_phone') or 'Not Extracted'}\n"
        f"🗺️ <b>Address:</b> {biz_config.get('business_address') or 'Not Extracted'}\n"
        f"📧 <b>Email:</b> {biz_config.get('business_email') or 'Not Extracted'}\n"
        f"🌍 <b>Timezone:</b> <code>{biz_config['business_timezone']}</code>\n\n"
        f"Select an option below to manage your virtual front desk:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes button clicks from the admin."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = str(update.effective_chat.id)
    
    # 1. Handle Settings Recrawl Option
    if data.startswith("settings_recrawl_"):
        business_id = data.replace("settings_recrawl_", "")
        
        # Verify the requester is actually the admin for this business
        biz_config = session.get_business_config(business_id)
        if not biz_config or biz_config["admin_chat_id"] != chat_id:
            return
            
        # Queue the job in crawl_jobs
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.crawl_jobs (business_id, website_url, status) VALUES (%s, %s, 'pending')",
                    (business_id, biz_config["website_url"])
                )
                conn.commit()
        finally:
            conn.close()
            
        await query.edit_message_text(
            text=f"🔄 <b>Crawl Task Queued!</b>\n\n"
                 f"The background scraper has been notified to scan <code>{biz_config['website_url']}</code> "
                 f"and update the search database for <b>{biz_config['business_name']}</b>.\n\n"
                 f"You will receive an alert here when the compilation is complete!",
            parse_mode="HTML"
        )
        return

    # 2. Handle Settings Get Customer QR Option
    if data.startswith("settings_qr_"):
        business_id = data.replace("settings_qr_", "")
        
        # Verify the requester is actually the admin for this business
        biz_config = session.get_business_config(business_id)
        if not biz_config or biz_config["admin_chat_id"] != chat_id:
            return
            
        # Generate QR code for customer link in memory
        import io
        import qrcode
        bot_username = os.getenv("TELEGRAM_BOT_NAME") or context.bot.username or "Dmhaircarebot"
        visitor_url = f"https://t.me/{bot_username}?start=v_{business_id}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(visitor_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1E2229", back_color="white")
        
        # Save to byte stream to send to Telegram
        bio = io.BytesIO()
        bio.name = 'customer_qr.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        
        # Send the customer QR code photo to the admin
        await query.message.reply_photo(
            photo=bio,
            caption=f"📷 <b>Customer QR Code: {biz_config['business_name']}</b>\n"
                    f"Place this QR in your salon! Customers who scan it will chat with {biz_config['agent_name']}.\n\n"
                    f"Link: <code>{visitor_url}</code>",
            parse_mode="HTML"
        )
        return

    # Verify the sender is the registered admin for a business
    admin_biz = session.get_business_by_admin(chat_id)
    if not admin_biz:
        return
    business_id = admin_biz["business_id"]

    if data.startswith("reply_to_"):
        visitor_chat_id = data.replace("reply_to_", "")
        
        # Enable direct reply mode for the admin
        session.set_active_visitor_for_admin(business_id, visitor_chat_id)
        session.set_visitor_paused(visitor_chat_id, True, business_id)
        
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
        session.set_visitor_paused(visitor_chat_id, False, business_id)
        session.clear_active_visitor_for_admin(business_id)
        
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
    
    # 4. Segment into message bubbles (< 800 chars)
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

    # CASE 1: Message is from the Admin/Owner of a registered business
    admin_biz = session.get_business_by_admin(chat_id)
    if admin_biz:
        business_id = admin_biz["business_id"]
        # Check who the admin is currently replying to
        active_visitor_id = session.get_active_visitor_for_admin(chat_id)
        
        if active_visitor_id:
            # Check if active_visitor_id is a web session (UUID) instead of a numeric Telegram ID
            is_web_visitor = not active_visitor_id.lstrip('-').isdigit()
            
            # If the admin types /resolve, close it immediately
            if user_message.strip() == "/resolve":
                session.set_visitor_paused(active_visitor_id, False, business_id)
                session.clear_active_visitor_for_admin(business_id)
                await update.message.reply_text("✅ Chat resolved. AI bot reactivated.")
                if is_web_visitor:
                    try:
                        from src.db import get_supabase_client
                        sb = get_supabase_client()
                        sb.table("web_chat_messages").insert({
                            "session_id": active_visitor_id,
                            "sender": "system",
                            "message": "🔔 The front desk staff has resolved the chat. The automated receptionist is back online!"
                        }).execute()
                    except Exception as err:
                        logger.error(f"Failed to insert resolution msg: {err}")
                else:
                    await context.bot.send_message(
                        chat_id=active_visitor_id,
                        text="🔔 *The front desk staff has closed the chat. The automated assistant is back online to help you!*",
                        parse_mode="Markdown"
                    )
                return
            
            # Capture this message as the answer to the pending question before relaying!
            pending_question = session.get_pending_question(active_visitor_id)
            if pending_question:
                session.save_resolved_qa(business_id, pending_question, user_message)
                session.save_pending_question(active_visitor_id, None, business_id) # Clear pending
                
            if is_web_visitor:
                # Relay the admin's message to the Web Visitor via database message log
                try:
                    from src.db import get_supabase_client
                    sb = get_supabase_client()
                    sb.table("web_chat_messages").insert({
                        "session_id": active_visitor_id,
                        "sender": "staff",
                        "message": user_message
                    }).execute()
                    logger.info(f"🔄 [Admin Relay Web] Relayed message from Admin ({chat_id}) to Web Visitor ({active_visitor_id}): \"{user_message}\"")
                    await update.message.reply_text(f"🚀 Relayed message to web visitor.")
                except Exception as e:
                    logger.error(f"❌ Failed to relay message to web visitor {active_visitor_id}: {e}")
                    await update.message.reply_text(f"❌ Failed to relay message: {e}")
            else:
                # Relay the admin's message directly to the Telegram visitor
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
    
    # Check if the visitor has a linked business context
    business_id = session.get_visitor_business(chat_id)
    if not business_id:
        await update.message.reply_text(
            "👋 Welcome to Frontdesk!\n\n"
            "To get started, please click the custom chat link provided by the business you're visiting.",
            parse_mode="HTML"
        )
        return

    biz_config = session.get_business_config(business_id)
    if not biz_config:
        await update.message.reply_text(
            "⚠️ <b>Service Configuration Error</b>\n\n"
            "We couldn't load settings for this business. Please contact their staff directly.",
            parse_mode="HTML"
        )
        return

    # A. Check if the AI session is paused (Handoff is active and owner has control)
    if session.is_visitor_paused(chat_id):
        logger.info(f"Visitor {chat_id} messaged, but AI is paused. Waiting for admin.")
        return

    # Check if we have a cached answer from a previous resolved escalation!
    cached_answer = session.find_cached_answer(business_id, user_message)
    if cached_answer:
        logger.info(f"⚡ [Cache Hit] Found resolved answer for: \"{user_message}\"")
        
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

        # Parse and format response into HTML cards
        cards = format_for_telegram(cached_answer)
        
        # Determine if we should append buttons based on content keywords
        buttons = []
        response_lower = cached_answer.lower()
        website_url = biz_config.get("website_url", "")
        if website_url and any(kw in response_lower for kw in ["phone", "call", "tel", "contact", "reach us", "number", "website", "email"]):
            buttons.append(InlineKeyboardButton("🌐 Visit Website", url=website_url))
        map_url = biz_config.get("map_url", "")
        if map_url and any(kw in response_lower for kw in ["location", "located", "address", "find us", "where", "saratoga", "map"]):
            buttons.append(InlineKeyboardButton("📍 View Map", url=map_url))
        markup = InlineKeyboardMarkup([buttons]) if buttons else None

        # Edit the "Thinking..." status message with the first card
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=cards[0],
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup if len(cards) == 1 else None
        )
        
        # Send subsequent cards as new message bubbles
        for i, card in enumerate(cards[1:]):
            is_last = (i == len(cards[1:]) - 1)
            await context.bot.send_message(
                chat_id=chat_id,
                text=card,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=markup if is_last else None
            )
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
        config_run = {"configurable": {"thread_id": chat_id, "tenant_id": business_id}}
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
        
        # E. Handle Handoff Action (either classified as handoff, or RAG returned the fallback escalation message)
        fallback_msg = "I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."
        is_fallback = (fallback_msg in final_response)
        
        if intent == "handoff" or is_fallback:
            # 1. Pause the AI
            session.set_visitor_paused(chat_id, True, business_id)
            
            # Save the pending question for caching when resolved
            session.save_pending_question(chat_id, user_message, business_id)
            
            # 2. Alert the Admin with inline buttons
            keyboard = [
                [
                    InlineKeyboardButton("💬 Reply to Visitor", callback_data=f"reply_to_{chat_id}"),
                    InlineKeyboardButton("✅ Resolve Chat", callback_data=f"resolve_chat_{chat_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            admin_chat_id = biz_config.get("admin_chat_id")
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"🚨 <b>Handoff Escalation Triggered!</b>\n\n"
                         f"🏢 <b>Business:</b> <b>{biz_config['business_name']}</b>\n"
                         f"👤 <b>Visitor Chat ID:</b> <code>{chat_id}</code>\n"
                         f"💬 <b>Visitor Message:</b> \"{user_message}\"\n\n"
                         f"AI bot has been muted. Choose an option below:",
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            else:
                logger.warning(f"⚠️ Handoff triggered for {biz_config['business_name']}, but no admin is registered for this business.")
            
        # Parse and format response into HTML cards
        cards = format_for_telegram(final_response)
        
        logger.info(f"📤 [Outgoing Bot Response] Chat ID: {chat_id} | Intent: {intent} | Response: \"{final_response}\"")
        
        # Determine if we should append buttons based on content keywords
        buttons = []
        response_lower = final_response.lower()
        
        # Website button if response mentions contact/phone/call/tel/email
        website_url = biz_config.get("website_url", "")
        if website_url and any(kw in response_lower for kw in ["phone", "call", "tel", "contact", "reach us", "number", "website", "email"]):
            buttons.append(InlineKeyboardButton("🌐 Visit Website", url=website_url))
            
        # Map button if config has map URL and response mentions location/map/address
        map_url = biz_config.get("map_url", "")
        if map_url and any(kw in response_lower for kw in ["location", "located", "address", "find us", "where", "saratoga", "map"]):
            buttons.append(InlineKeyboardButton("📍 View Map", url=map_url))
            
        markup = InlineKeyboardMarkup([buttons]) if buttons else None
        
        # Edit the "Thinking..." status message with the first card
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=cards[0],
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup if len(cards) == 1 else None
        )
        
        # Send subsequent cards as new message bubbles
        for i, card in enumerate(cards[1:]):
            is_last = (i == len(cards[1:]) - 1)
            await context.bot.send_message(
                chat_id=chat_id,
                text=card,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=markup if is_last else None
            )

    except Exception as e:
        logger.error(f"Error executing agent app: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="⚠️ <i>I apologize, but I encountered an error. Please try again in a moment.</i>",
            parse_mode="HTML"
        )

async def getqr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    # 1. Authorize sender: must be a registered admin in the system
    if not session.is_authorized_admin(chat_id):
        await update.message.reply_text(
            "⚠️ <b>Access Denied</b>\nThis command is only available to registered salon administrators.",
            parse_mode="HTML"
        )
        return
        
    # 2. Check arguments
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b>\n<code>/getqr [phone_number]</code>\n\nExample: <code>/getqr +14082105851</code>",
            parse_mode="HTML"
        )
        return
        
    search_phone = context.args[0]
    search_digits = "".join(filter(str.isdigit, search_phone))
    if not search_digits:
        await update.message.reply_text("⚠️ Please enter a valid phone number with digits.", parse_mode="HTML")
        return
        
    # 3. Query matching business by phone digits match
    conn = get_pg_connection()
    matching_biz = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT business_id, business_name, flyer_url, owner_qr_url, business_phone FROM public.businesses")
            rows = cur.fetchall()
            for row in rows:
                db_phone = row[4]
                if db_phone:
                    db_digits = "".join(filter(str.isdigit, db_phone))
                    # Check if the search term matches suffix or prefix of the database record
                    if db_digits.endswith(search_digits) or search_digits.endswith(db_digits[-10:] if len(db_digits) >= 10 else db_digits):
                        matching_biz = {
                            "business_id": row[0],
                            "business_name": row[1],
                            "flyer_url": row[2],
                            "owner_qr_url": row[3],
                            "business_phone": db_phone
                        }
                        break
    finally:
        conn.close()
        
    if not matching_biz:
        await update.message.reply_text(f"🔍 No salon found matching phone: <code>{search_phone}</code>", parse_mode="HTML")
        return
        
    # 4. Reply with matching business details
    biz_name = matching_biz["business_name"]
    flyer_url = matching_biz["flyer_url"]
    owner_qr_url = matching_biz["owner_qr_url"]
    
    await update.message.reply_text(
        f"🔍 <b>Match Found: {biz_name}</b>\n"
        f"📞 Registered Phone: <code>{matching_biz['business_phone']}</code>\n\n"
        f"I am sending your Customer Flyer PDF and Owner Activation QR Code directly below...",
        parse_mode="HTML"
    )
    
    # Send Owner Activation QR Code image if populated
    if owner_qr_url:
        try:
            bot_username = os.getenv("TELEGRAM_BOT_NAME") or context.bot.username or "Dmhaircarebot"
            await update.message.reply_photo(
                photo=owner_qr_url,
                caption=f"👑 <b>Owner Activation QR</b>\nLink: <code>t.me/{bot_username}?start=a_{matching_biz['business_id']}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Failed to send owner QR image: {e}")
            
    # Send Customer Printable Flyer PDF if populated
    if flyer_url:
        try:
            await update.message.reply_document(
                document=flyer_url,
                caption=f"📄 <b>Print-Ready Customer Flyer</b>\nScan QR to chat with AI Receptionist.",
                parse_mode="HTML"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Failed to send Customer Flyer PDF: {e}")

def build_bot_app():
    """Initializes the python-telegram-bot application."""
    # Ensure config variables are set
    config.validate_config()
    
    # Initialize local SQLite database
    session.init_db()
    
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Add Command & Message handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("getqr", getqr_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return app
