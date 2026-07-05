import sys
import logging
import asyncio
import uvicorn
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Union, List, Dict
import requests
import src.config as config
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.telegram_bot.bot import build_bot_app
from src.agent.orchestrator import agent_app

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger("frontdesk-main")

# FastAPI instance
api_app = FastAPI(title="Frontdesk Expert - Chat API")

# Enable CORS for frontend accessibility
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Since this is a local development/testing environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    business_id: str
    message: str
    thread_id: str = "test_thread"

@api_app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    config_run = {"configurable": {"thread_id": req.thread_id, "tenant_id": req.business_id}}
    try:
        result = await agent_app.ainvoke(
            {"messages": [("user", req.message)]},
            config=config_run
        )
        content_val = result["messages"][-1].content
        if isinstance(content_val, list):
            reply = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val])
        else:
            reply = str(content_val)
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return {"reply": f"⚠️ Error processing request: {str(e)}"}

@api_app.get("/api/chat/history")
async def chat_history(business_id: str, thread_id: str = "test_thread"):
    config_run = {"configurable": {"thread_id": thread_id, "tenant_id": business_id}}
    try:
        state = await agent_app.aget_state(config_run)
        messages = state.values.get("messages", []) if (state and state.values) else []
        
        serialized = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                continue
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            serialized.append({
                "role": role,
                "content": msg.content
            })
        return {"history": serialized}
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return {"history": []}

# JWT Token Validation Dependency using Supabase Auth User Endpoint
async def validate_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    token = authorization.split(" ")[1]
    
    url = f"{config.SUPABASE_URL}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": config.SUPABASE_SERVICE_ROLE_KEY
    }
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return resp.json()
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")

# Proxy Endpoints for Supabase database operations
@api_app.get("/api/businesses")
async def get_businesses(_user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("businesses").select("*").order("business_name").execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching businesses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/api/crawl-jobs")
async def get_crawl_jobs(_user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("crawl_jobs").select("*").order("created_at", desc=True).limit(6).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching crawl jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/api/admin-relay")
async def get_admin_relay(_user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("admin_relay").select("*").eq("is_paused", True).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching admin relay: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/api/daily-usage")
async def get_daily_usage(_user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("daily_usage").select("*").order("usage_date", desc=False).limit(14).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching daily usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/api/knowledge-chunks")
async def get_knowledge_chunks(business_id: str, _user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("knowledge_chunks").select("id, content").eq("business_id", business_id).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching knowledge chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/api/business-load")
async def insert_business_load(data: Union[Dict, List[Dict]], _user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        rows = data if isinstance(data, list) else [data]
        resp = sb.table("business_load").insert(rows).execute()
        return {"success": True, "data": resp.data}
    except Exception as e:
        logger.error(f"Error inserting business load: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.delete("/api/businesses/{business_id}")
async def delete_business(business_id: str, _user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("businesses").delete().eq("business_id", business_id).execute()
        return {"success": True, "data": resp.data}
    except Exception as e:
        logger.error(f"Error deleting business: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.delete("/api/business-load/{business_id}")
async def delete_business_load(business_id: str, _user: dict = Depends(validate_token)):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("business_load").delete().eq("business_id", business_id).execute()
        return {"success": True, "data": resp.data}
    except Exception as e:
        logger.error(f"Error deleting business load: {e}")
        raise HTTPException(status_code=500, detail=str(e))
# =====================================================================
# Web App Receptionist Endpoints (Public/Anonymous Visitor)
# =====================================================================

class WebSessionRequest(BaseModel):
    business_id: str
    visitor_ip: str = None
    user_agent: str = None

@api_app.post("/api/webapp/session")
async def create_webapp_session(req: WebSessionRequest):
    try:
        from src.db import get_supabase_client
        import uuid
        sb = get_supabase_client()
        
        # Check if business exists
        biz = sb.table("businesses").select("business_id").eq("business_id", req.business_id).execute()
        if not biz.data:
            raise HTTPException(status_code=404, detail="Business not found")
            
        session_id = str(uuid.uuid4())
        
        # Insert into web_sessions
        sb.table("web_sessions").insert({
            "session_id": session_id,
            "business_id": req.business_id,
            "visitor_ip": req.visitor_ip,
            "user_agent": req.user_agent
        }).execute()
        
        # Insert into visitors for Telegram session compatibility
        from src.telegram_bot.session import set_visitor_business
        set_visitor_business(session_id, req.business_id)
        
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Error creating web session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class WebChatRequest(BaseModel):
    session_id: str
    message: str

@api_app.post("/api/webapp/chat")
async def webapp_chat(req: WebChatRequest):
    try:
        from src.db import get_supabase_client
        from src.telegram_bot.session import is_visitor_paused, set_visitor_paused, save_pending_question, get_business_config
        sb = get_supabase_client()
        
        # 1. Retrieve the business linked to the web session
        res = sb.table("web_sessions").select("business_id").eq("session_id", req.session_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Invalid web session ID")
        business_id = res.data[0]["business_id"]
        
        # Log user query in chat logs
        sb.table("web_chat_messages").insert({
            "session_id": req.session_id,
            "sender": "visitor",
            "message": req.message
        }).execute()
        
        # 2. Check if the session is currently paused for human override
        if is_visitor_paused(req.session_id):
            biz_config = get_business_config(business_id)
            if biz_config and biz_config.get("admin_chat_id"):
                from src.telegram_bot.bot import build_bot_app
                bot = build_bot_app().bot
                await bot.send_message(
                    chat_id=biz_config["admin_chat_id"],
                    text=f"⚠️ [Web Visitor Follow-up]:\n{req.message}\n\n(AI is paused for this visitor)"
                )
            
            support_reply = "Our staff is reviewing your message and will respond shortly."
            sb.table("web_chat_messages").insert({
                "session_id": req.session_id,
                "sender": "system",
                "message": support_reply
            }).execute()
            
            return {"reply": support_reply, "is_paused": True}
            
        # 3. Call the LangGraph agent app
        config_run = {"configurable": {"thread_id": req.session_id, "tenant_id": business_id}}
        result = await agent_app.ainvoke(
            {"messages": [("user", req.message)]},
            config=config_run
        )
        
        content_val = result["messages"][-1].content
        if isinstance(content_val, list):
            reply = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val])
        else:
            reply = str(content_val)
            
        intent = result.get("intent", "kb_query")
        
        # 4. Handle handoff logic
        fallback_msg = "I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."
        is_fallback = (fallback_msg in reply)
        
        is_paused = False
        if intent == "handoff" or is_fallback:
            set_visitor_paused(req.session_id, True, business_id)
            save_pending_question(req.session_id, req.message, business_id)
            is_paused = True
            
            biz_config = get_business_config(business_id)
            if biz_config and biz_config.get("admin_chat_id"):
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                from src.telegram_bot.bot import build_bot_app
                bot = build_bot_app().bot
                
                keyboard = [
                    [
                        InlineKeyboardButton("💬 Reply to Visitor", callback_data=f"reply_to_{req.session_id}"),
                        InlineKeyboardButton("✅ Resolve Chat", callback_data=f"resolve_chat_{req.session_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await bot.send_message(
                    chat_id=biz_config["admin_chat_id"],
                    text=(
                        f"🚨 <b>Human Escalation Alert (Web)</b>\n\n"
                        f"<b>Visitor Question:</b> {req.message}\n\n"
                        f"AI has been paused. Use the buttons below or reply in the Admin Console."
                    ),
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        
        # Log assistant response
        sb.table("web_chat_messages").insert({
            "session_id": req.session_id,
            "sender": "assistant",
            "message": reply
        }).execute()
        
        return {"reply": reply, "is_paused": is_paused}
    except Exception as e:
        logger.error(f"Error in webapp chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/api/webapp/messages")
async def get_webapp_messages(session_id: str):
    try:
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("web_chat_messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching web messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_services():
    print("---------------------------------------------")
    print("🚀 Booting Front Desk Platform...")
    print("Loading configurations and initializing Telegram Bot + Chat API...")
    
    try:
        # Build bot application
        bot_app = build_bot_app()
        print("SQLite Database initialized successfully.")
        
        # Initialize and start Telegram Bot in asyncio polling mode
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        print("Telegram Bot is running in polling mode.")
        
        # Start FastAPI / Uvicorn server
        config = uvicorn.Config(api_app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        
        print("Chat API Server is starting at http://0.0.0.0:8000")
        print("Press Ctrl+C to stop.")
        print("---------------------------------------------")
        
        await server.serve()
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Critical error during boot: {e}")
        sys.exit(1)
    finally:
        print("Shutting down services...")
        try:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
        except Exception as shutdown_err:
            logger.error(f"Error during bot shutdown: {shutdown_err}")

def main():
    asyncio.run(run_services())

if __name__ == "__main__":
    main()
