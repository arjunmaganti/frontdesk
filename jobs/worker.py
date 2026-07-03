import os
import sys
import time
import tempfile
import shutil
import logging
from dotenv import load_dotenv

# Load root .env file from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Add parent directory and agent directory to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "agent"))

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("FrontdeskWorker")

# Ensure required libraries can be imported
try:
    from src.db import get_pg_connection, get_supabase_client
    import src.config as config
    from utility.crawl import crawl_site
except ImportError as e:
    logger.error(f"Failed to import core modules. Ensure running from project root: {e}")
    sys.exit(1)

def extract_contact_details(md_dir: str, gemini_key: str) -> dict:
    """Reads crawled markdown files and runs Gemini to extract phone and address."""
    combined_content = ""
    md_files = [f for f in os.listdir(md_dir) if f.endswith(".md")]
    
    # Sort files to prioritize contact or home pages
    priority_files = []
    other_files = []
    for f in md_files:
        if any(kw in f.lower() for kw in ["contact", "about", "index"]):
            priority_files.append(f)
        else:
            other_files.append(f)
            
    for f in priority_files + other_files:
        file_path = os.path.join(md_dir, f)
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                combined_content += f"\n\n--- FILE: {f} ---\n" + file.read()
        except Exception:
            pass
            
    if len(combined_content) > 20000:
        combined_content = combined_content[:20000]
        
    if not combined_content.strip():
        return {}
        
    logger.info("🧠 Running structured Gemini extraction on crawled text...")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage
        import json
        
        model_name = os.getenv("LLM_MODEL_NAME", "gemini-flash-latest")
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=gemini_key,
            temperature=0.0
        )
        
        system_prompt = (
            "Analyze the business website scrapings below and extract their contact coordinates:\n"
            "1. The business phone number. Format it as international digits: +1XXXXXXXXXX (e.g., +14082105851). "
            "If it is a local USA number like 408-210-5851, format it as +14082105851.\n"
            "2. The physical street address of the salon/business.\n\n"
            "You MUST respond ONLY with a raw JSON object (no markdown, no backticks, no wrap, no extra text) in this exact schema:\n"
            '{\n  "phone": "+1XXXXXXXXXX",\n  "address": "Street Address, City, State ZIP"\n}'
        )
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=combined_content)
        ])
        
        # Clean the response text content safely
        content_val = response.content
        if isinstance(content_val, list):
            resp_text = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val])
        else:
            resp_text = str(content_val)
            
        resp_text = resp_text.strip()
        if resp_text.startswith("```"):
            lines = resp_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            resp_text = "\n".join(lines).strip()
            
        return json.loads(resp_text)
    except Exception as e:
        logger.warning(f"⚠️ Coordinates extraction failed: {e}")
        return {}

async def send_telegram_alert(chat_id: str, text: str):
    """Sends a direct notification to the admin via Telegram Bot API."""
    if not chat_id:
        return
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        logger.info(f"📤 Sent Telegram notification to Admin ({chat_id})")
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram alert: {e}")

def process_crawl_job(job_id: str, business_id: str, website_url: str) -> bool:
    """Executes the crawl, generates vector embeddings, and updates Supabase inside a transaction."""
    logger.info(f"🔄 Processing crawl job {job_id} for Business: '{business_id}' (URL: {website_url})")
    
    # 1. Setup temporary directory for crawl results
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # A. Execute website scraper
            crawl_site(website_url, temp_dir, max_pages=15, max_depth=2)
            
            # B. Extract coordinates (Phone & Address) using Gemini
            gemini_key = config.GEMINI_API_KEY
            coords = extract_contact_details(temp_dir, gemini_key)
            phone = coords.get("phone")
            address = coords.get("address")
            
            map_url = None
            if address:
                import urllib.parse
                map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(address)}"
            
            # C. Load markdown files and split into chunks
            from langchain_community.document_loaders import DirectoryLoader, TextLoader
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            
            loader = DirectoryLoader(temp_dir, glob="**/*.md", loader_cls=TextLoader)
            docs = loader.load()
            
            if not docs:
                raise ValueError("No pages were successfully crawled or saved as markdown.")
                
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
            chunks = text_splitter.split_documents(docs)
            logger.info(f"📝 Split crawled text into {len(chunks)} semantic chunks.")
            
            # D. Generate vector embeddings
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            embeddings_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=gemini_key)
            
            logger.info("⚡ Generating Gemini embeddings...")
            
            # E. Perform Database Transaction updates using psycopg2
            conn = get_pg_connection()
            try:
                with conn.cursor() as cur:
                    # 1. Update business contact details
                    cur.execute(
                        """
                        UPDATE public.businesses 
                        SET business_phone = COALESCE(%s, business_phone),
                            business_address = COALESCE(%s, business_address),
                            map_url = COALESCE(%s, map_url)
                        WHERE business_id = %s
                        """,
                        (phone, address, map_url, business_id)
                    )
                    
                    # 2. Delete old vectors
                    cur.execute("DELETE FROM public.knowledge_chunks WHERE business_id = %s", (business_id,))
                    
                    # 3. Batch insert new vectors
                    for chunk in chunks:
                        chunk_text = chunk.page_content
                        vector = embeddings_model.embed_query(chunk_text)
                        
                        cur.execute(
                            """
                            INSERT INTO public.knowledge_chunks (business_id, content, embedding, metadata)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (business_id, chunk_text, str(vector), None)
                        )
                    
                    # 4. Fetch admin_chat_id to alert them
                    cur.execute("SELECT admin_chat_id, business_name FROM public.businesses WHERE business_id = %s", (business_id,))
                    biz_row = cur.fetchone()
                    admin_chat_id = biz_row[0] if biz_row else None
                    business_name = biz_row[1] if biz_row else business_id
                    
                    conn.commit()
                    logger.info("💾 Transaction committed successfully. Stored new vector chunks.")
                    
            finally:
                conn.close()
                
            # F. Notify the owner via Telegram
            if admin_chat_id:
                import asyncio
                alert_text = (
                    f"🚀 <b>Crawling & Compilation Complete!</b>\n\n"
                    f"🏢 <b>Business:</b> {business_name}\n"
                    f"🌐 <b>Website:</b> <code>{website_url}</code>\n"
                    f"🔹 <b>Extracted Phone:</b> {phone or 'Not Found'}\n"
                    f"🔹 <b>Extracted Address:</b> {address or 'Not Found'}\n\n"
                    f"Your customer assistant is now fully updated and active!"
                )
                asyncio.run(send_telegram_alert(admin_chat_id, alert_text))
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to process crawl job: {e}")
            raise e

def run_worker_loop():
    """Main polling loop consuming tasks from Supabase crawl_jobs queue."""
    logger.info("🚀 Background Worker Daemon started. Listening for crawl tasks...")
    
    while True:
        conn = get_pg_connection()
        job = None
        
        try:
            with conn.cursor() as cur:
                # 1. Fetch next pending job using row-locking
                cur.execute(
                    """
                    SELECT id, business_id, website_url 
                    FROM public.crawl_jobs 
                    WHERE status = 'pending' 
                    ORDER BY created_at ASC
                    LIMIT 1 
                    FOR UPDATE SKIP LOCKED;
                    """
                )
                job = cur.fetchone()
                
                if job:
                    job_id, business_id, website_url = job
                    # Immediately mark as processing inside the lock transaction
                    cur.execute(
                        "UPDATE public.crawl_jobs SET status = 'processing', updated_at = NOW() WHERE id = %s",
                        (job_id,)
                    )
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Database error during job acquisition: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
                
        # 2. Process the job if acquired
        if job:
            job_id, business_id, website_url = job
            try:
                # Execute processing pipeline
                process_crawl_job(job_id, business_id, website_url)
                
                # Mark as completed
                conn = get_pg_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE public.crawl_jobs SET status = 'completed', updated_at = NOW() WHERE id = %s",
                            (job_id,)
                        )
                        conn.commit()
                finally:
                    conn.close()
                logger.info(f"✅ Job {job_id} successfully marked as completed.")
                
            except Exception as e:
                # Mark as failed and store error details
                conn = get_pg_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE public.crawl_jobs SET status = 'failed', error_message = %s, updated_at = NOW() WHERE id = %s",
                            (str(e), job_id)
                        )
                        # Fetch admin chat ID to send error warning
                        cur.execute("SELECT admin_chat_id, business_name FROM public.businesses WHERE business_id = %s", (business_id,))
                        biz_row = cur.fetchone()
                        admin_chat_id = biz_row[0] if biz_row else None
                        business_name = biz_row[1] if biz_row else business_id
                        
                        conn.commit()
                finally:
                    conn.close()
                    
                if admin_chat_id:
                    import asyncio
                    error_text = (
                        f"⚠️ <b>Website Crawl Failed</b>\n\n"
                        f"🏢 <b>Business:</b> {business_name}\n"
                        f"🌐 <b>Website:</b> <code>{website_url}</code>\n\n"
                        f"❌ <b>Error:</b> <code>{str(e)[:150]}</code>\n\n"
                        f"Please verify your website URL is public and try again."
                    )
                    asyncio.run(send_telegram_alert(admin_chat_id, error_text))
                
        else:
            # No jobs found, sleep before polling again
            time.sleep(5)

if __name__ == "__main__":
    try:
        run_worker_loop()
    except KeyboardInterrupt:
        logger.info("👋 Worker daemon stopped by user.")
        sys.exit(0)
