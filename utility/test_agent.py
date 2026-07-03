#!/usr/bin/env python3
import os
import sys
import shutil
import asyncio
import argparse
from dotenv import load_dotenv

# Ensure core directory is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../core")))

def setup_test_environment(src_dir):
    """Sets up the local environment to simulate running the bot for a specific client."""
    src_dir = os.path.abspath(src_dir)
    src_env = os.path.join(src_dir, ".env")
    src_index = os.path.join(src_dir, "index")
    
    if not os.path.exists(src_env):
        print(f"Error: A configuration file (.env) must exist in the source directory: {src_env}")
        sys.exit(1)
        
    if not os.path.exists(src_index) or not os.listdir(src_index):
        print(f"Error: Compiled vector index not found in {src_index}. Please run build first:")
        print(f"       python3 utility/build.py --src {src_dir} --out dist/test.zip")
        sys.exit(1)

    # 1. Load keys into active environment
    load_dotenv(src_env, override=True)
    print(f"Loaded config from {src_env}")
    
    # Verify Gemini Key is present
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Error: GEMINI_API_KEY (or GOOGLE_API_KEY) is not set in the client's .env file.")
        sys.exit(1)

    # 2. Copy the index files to the local root ./index directory so core can find them
    local_index = "index"
    if os.path.exists(local_index):
        shutil.rmtree(local_index)
    shutil.copytree(src_index, local_index)
    print("Staged compiled search index files locally.")

async def run_simulation_loop():
    """Runs a simulated chat loop in the terminal."""
    import src.config as config
    import src.telegram_bot.session as session
    from src.agent.orchestrator import agent_app
    
    # 1. Initialize test database
    session.init_db()
    print("Initialized SQLite checkpointer database.")
    print("---------------------------------------------------------")
    print("🌟 Welcome to the Front Desk Bot Local Simulation Loop 🌟")
    print("Type your message below to test the agent's response.")
    print("Type 'exit' to quit.")
    print(f"Daily Cap: {config.DAILY_MESSAGE_CAP} messages | Rate Limit: {config.USER_RATE_LIMIT} messages per {config.USER_RATE_WINDOW}s")
    print("---------------------------------------------------------")

    visitor_chat_id = "test_user_123"

    while True:
        try:
            user_input = input("\n👤 Visitor: ").strip()
            if not user_input:
                continue
            if user_input.lower() == "exit":
                break
                
            # Simulate visitor checks
            # 1. User Spam Rate Limit
            if session.check_rate_limit(visitor_chat_id):
                print("🤖 Bot Guardrail: ⚠️ [Blocked by Spam Rate Limiter]")
                continue
                
            # 2. Daily Cap Limit
            if session.check_daily_cap():
                print("🤖 Bot Guardrail: ⚠️ [Blocked by Daily Cap Limit]")
                print("🤖 Bot Response: Our automated assistant has reached its daily limit. Please call the desk directly.")
                continue
                
            # Increment daily usage count
            session.increment_daily_usage()
            
            # 3. Call the Agent Graph
            print("🤖 Bot is thinking...")
            config_run = {"configurable": {"thread_id": visitor_chat_id, "tenant_id": "standalone"}}
            result = await agent_app.ainvoke(
                {"messages": [("user", user_input)]},
                config=config_run
            )
            
            # Print agent outputs
            content_val = result["messages"][-1].content
            if isinstance(content_val, list):
                final_response = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val])
            else:
                final_response = str(content_val)
            intent = result.get("intent", "unknown")
            print(f"🤖 Bot classified intent: [{intent}]")
            print(f"🤖 Bot: {final_response}")
            
            # Handle handoff simulation notification
            if intent == "handoff":
                print("🚨 [Handoff Alert triggered to Admin! AI session muted.]")
                print("Type '/resolve' to unmute the bot and continue simulation.")
                session.set_visitor_paused(visitor_chat_id, True)
                
                # Loop for admin reply
                while session.is_visitor_paused(visitor_chat_id):
                    admin_input = input("\n👑 Admin Reply: ").strip()
                    if admin_input == "/resolve":
                        session.set_visitor_paused(visitor_chat_id, False)
                        print("✅ Admin resolved chat. AI bot reactivated.")
                    else:
                        # Relay message
                        print(f"🤖 (Relayed to Visitor): {admin_input}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    # Clean up index directory
    if os.path.exists("index"):
        shutil.rmtree("index")
    # Clean up database
    if os.path.exists("state.db"):
        os.remove("state.db")
    print("\nCleaned up staged files. Exited simulation.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Front Desk Bot Simulation CLI")
    parser.add_argument("--src", required=True, help="Path to the tenant workspace containing .env and markdown files")
    args = parser.parse_args()
    
    setup_test_environment(args.src)
    asyncio.run(run_simulation_loop())
