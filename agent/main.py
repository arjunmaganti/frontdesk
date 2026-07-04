import sys
import logging
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
