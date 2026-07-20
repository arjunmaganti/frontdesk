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

class ParseTextRequest(BaseModel):
    text: str

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
        
        # Ensure we send empty string instead of None/null for website_url if it's missing to satisfy not-null DB constraint
        for row in rows:
            if "website_url" not in row or row["website_url"] is None:
                row["website_url"] = ""
            else:
                row["website_url"] = row["website_url"].strip()

        resp = sb.table("business_load").insert(rows).execute()
        
        # Delete crawl jobs for any inserted row that has no website_url
        for row in rows:
            if not row.get("website_url"):
                try:
                    sb.table("crawl_jobs").delete().eq("business_id", row.get("business_id")).execute()
                except Exception as del_err:
                    logger.warning(f"Failed to delete crawl job for empty website_url: {del_err}")

        return {"success": True, "data": resp.data}
    except Exception as e:
        logger.error(f"Error inserting business load: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/api/business-load/parse-text")
async def parse_text_and_ingest(req: ParseTextRequest, _user: dict = Depends(validate_token)):
    raw_text = req.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Text dump cannot be empty")
        
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage
        import json
        
        # Use gemini-2.5-flash as requested by user
        model_name = "gemini-2.5-flash"
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=config.GEMINI_API_KEY,
            temperature=0.0
        )
        
        system_prompt = (
            "Analyze the business onboarding details provided by the user and extract the following fields:\n"
            "1. business_name: The name of the business (Mandatory! If not found, return null).\n"
            "2. website_url: The official website URL of the business. Make sure it starts with http:// or https://. (Optional. Return null if not found).\n"
            "3. agent_name: The name of the AI receptionist/assistant (Optional. Default to 'Sarah' if not specified).\n"
            "4. business_phone: The business phone number. Format it as international digits: +1XXXXXXXXXX (e.g. +14082105851). (Optional. Return null if not found).\n"
            "5. business_email: The business email address. (Optional. Return null if not found).\n"
            "6. business_address: The physical street address of the business. (Optional. Return null if not found).\n\n"
            "You MUST respond ONLY with a raw JSON object (no markdown, no backticks, no wrap, no extra text) in this exact schema:\n"
            '{\n'
            '  "business_name": "Name of Business",\n'
            '  "website_url": "https://example.com",\n'
            '  "agent_name": "Kim",\n'
            '  "business_phone": "+14085551212",\n'
            '  "business_email": "contact@domain.com",\n'
            '  "business_address": "Street Address, City, State ZIP"\n'
            '}'
        )
        
        response = await asyncio.to_thread(
            llm.invoke,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=raw_text)
            ]
        )
        
        # Clean response content
        resp_text = response.content
        if isinstance(resp_text, list):
            resp_text = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in resp_text])
        else:
            resp_text = str(resp_text)
            
        resp_text = resp_text.strip()
        if resp_text.startswith("```"):
            lines = resp_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            resp_text = "\n".join(lines).strip()
            
        parsed_data = json.loads(resp_text)
        
        # Validate mandatory fields
        biz_name = parsed_data.get("business_name")
        if not biz_name or not biz_name.strip():
            raise HTTPException(status_code=400, detail="Could not extract a valid 'business_name' from the text dump.")
            
        web_url = (parsed_data.get("website_url") or "").strip()
        
        # Format the business_id slug
        import re
        slug = biz_name.strip().lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = slug.strip('-')
        
        payload = {
            "business_id": slug,
            "business_name": biz_name.strip(),
            "agent_name": (parsed_data.get("agent_name") or "Sarah").strip(),
            "website_url": web_url, # Empty string if none, satisfies DB not-null constraint
            "business_phone": parsed_data.get("business_phone") or None,
            "business_address": parsed_data.get("business_address") or None,
            "business_email": parsed_data.get("business_email") or None,
            "status": "pending"
        }
        
        # Ingest into Supabase business_load
        from src.db import get_supabase_client
        sb = get_supabase_client()
        resp = sb.table("business_load").insert(payload).execute()
        
        # If website_url is empty, delete the automatically created crawl job
        if not web_url:
            try:
                sb.table("crawl_jobs").delete().eq("business_id", slug).execute()
            except Exception as del_err:
                logger.warning(f"Failed to delete crawl job for empty website_url in parse-text: {del_err}")
                
        # Chunk raw_text and store in knowledge_chunks as manually dumped knowledge
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            from src.db import get_pg_connection
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            chunks = text_splitter.split_text(raw_text)
            
            embeddings_model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=config.GEMINI_API_KEY
            )
            
            conn = get_pg_connection()
            try:
                with conn.cursor() as cur:
                    # Delete existing custom chunks for this business
                    cur.execute(
                        "DELETE FROM public.knowledge_chunks WHERE business_id = %s AND metadata->>'source' = 'raw_markdown'",
                        (slug,)
                    )
                    
                    # Insert new chunks
                    for i, chunk_text in enumerate(chunks):
                        vector = embeddings_model.embed_query(chunk_text)
                        metadata_json = json.dumps({"source": "raw_markdown", "chunk_index": i})
                        cur.execute(
                            """
                            INSERT INTO public.knowledge_chunks (business_id, content, embedding, metadata)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (slug, chunk_text, str(vector), metadata_json)
                        )
                conn.commit()
                logger.info(f"💾 Successfully stored {len(chunks)} manual knowledge chunks for {slug}.")
            except Exception as db_err:
                logger.error(f"Error saving manual knowledge chunks for parsed business: {db_err}")
                conn.rollback()
            finally:
                conn.close()
        except Exception as chunk_err:
            logger.error(f"Error processing manual knowledge chunks for parsed business: {chunk_err}")

        return {"success": True, "data": payload}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error parsing raw text dump: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse and register: {str(e)}")

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

@api_app.get("/api/webapp/business/{business_id}")
async def get_webapp_business_config(business_id: str):
    try:
        from src.telegram_bot.session import get_business_config
        biz = get_business_config(business_id)
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")
        
        # Return only public parameters to ensure privacy
        return {
            "business_id": biz["business_id"],
            "business_name": biz["business_name"],
            "agent_name": biz["agent_name"],
            "website_url": biz.get("website_url"),
            "business_phone": biz.get("business_phone"),
            "business_address": biz.get("business_address"),
            "business_email": biz.get("business_email"),
            "map_url": biz.get("map_url")
        }
    except Exception as e:
        logger.error(f"Error fetching webapp business config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
