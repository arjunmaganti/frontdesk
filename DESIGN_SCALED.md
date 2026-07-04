# Scaled Multi-Tenant Platform Architecture (Supabase & Telegram-Native Onboarding)

This document describes the design and specifications for scaling the single-tenant frontdesk assistant into a multi-tenant SaaS platform running off a single bot instance.

---

## 1. Overview & Core Flow

Instead of deploying a separate bot package per business, a single shared Telegram Bot (and upcoming WhatsApp webhook) handles incoming traffic for all businesses.

* **Tenant Differentiation**: Achieved via Telegram **deep linking** parameters (e.g., `t.me/your_bot?start=v_[business_id]`).
* **Instant Onboarding**: Business owners register their salon directly inside the Telegram Bot by invoking `/register`, avoiding complex web registrations.
* **Unified Database**: Local SQLite and local FAISS files are replaced with a centralized **Supabase (PostgreSQL + pgvector)** instance to handle relational settings and semantic searches concurrently.
* **Asynchronous Jobs**: Crawler execution is decoupled from message handlers. A database-backed task queue handles scraping and vector generation in a throttled background worker thread/process.

---

## 2. Onboarding & Admin Binding Flow

Registration is designed to support mass bulk-onboarding from database staging scripts or operators.

```mermaid
sequenceDiagram
    participant Operator as Operator/Database
    participant DB as Supabase PostgreSQL
    participant Worker as Background Crawler
    participant Storage as Supabase Storage
    participant Bot as Telegram Bot
    participant Owner as Salon Owner (Admin)

    Operator->>DB: Insert business row into `business_load` (with optional contact overrides)
    Note over DB: PostgreSQL Trigger `process_business_load_row` fires
    DB->>DB: Upsert profile configuration into `businesses`
    DB->>DB: Queue task into `crawl_jobs`
    Worker->>DB: Consume pending job (Row locked: SKIP LOCKED)
    Worker->>Worker: Run Crawl4AI browser + Gemini extraction
    Worker->>DB: Write scraped data (COALESCE preserves pre-set overrides)
    Worker->>Worker: Generate 3072-dim embeddings & write vector chunks
    Worker->>Worker: Compile US Letter Marketing Flyer PDF with QR code
    Worker->>Storage: Upload flyer to public bucket `flyers` (application/pdf)
    Worker->>DB: Save flyer_url to `businesses`
    Worker->>Bot: Dispatch Telegram Success notification
    Bot->>Owner: Alert: "Crawl complete! Download PDF Flyer"
    Owner->>Bot: Admin activation link: `/start a_[business_id]`
    Bot->>DB: Save `admin_chat_id` (binds owner Telegram account)
    Bot->>Owner: Welcome Msg with clickable "Download PDF Flyer" link
```

### Steps in the Flow:
1. **Staging & Override Ingestion**: A new record is appended to the `business_load` table. It can optionally contain verified contact details (`business_phone`, `business_address`, `business_email`, `map_url`) to override website scraping.
2. **Database Trigger Execution**: A before-insert trigger (`trigger_process_business_load`) programmatically maps and registers the profile into `businesses`, and adds a pending task to `crawl_jobs`.
3. **Asynchronous Scraping**: The background worker runs Crawl4AI, queries Gemini for structured extraction, writes data back safely via `COALESCE` (never overwriting custom overrides), and generates vector chunks.
4. **Flyer Generation & Storage Upload**: The worker draws a US Letter PDF flyer containing a Telegram chat QR code, uploads it to Supabase Storage, and saves the public URL.
5. **Dynamic Ownership Binding**: The operator sends the activation QR code/link (`t.me/Dmhaircarebot?start=a_[business_id]`) to the salon owner. Clicking "Start" binds their account (`admin_chat_id`) and shows a welcome message containing their clickable PDF flyer.

---

## 3. Supabase Database Schema (Postgres + pgvector)

To support multiple businesses, we define a relational schema inside Supabase.

### A. `businesses` Table (Tenant Configurations)
Stores metadata for each business profile:
* `business_id` (TEXT, Primary Key) - The unique slug, e.g., `"dmhaircare"`.
* `business_name` (TEXT)
* `agent_name` (TEXT) - Custom persona.
* `website_url` (TEXT)
* `business_phone` (TEXT, Nullable) - Auto-extracted by crawler (or pre-set override).
* `business_address` (TEXT, Nullable) - Auto-extracted by crawler (or pre-set override).
* `business_email` (TEXT, Nullable) - Auto-extracted by crawler (or pre-set override).
* `map_url` (TEXT, Nullable) - Auto-generated from extracted address (or pre-set override).
* `business_timezone` (TEXT) - e.g., `"America/Los_Angeles"`.
* `admin_chat_id` (TEXT) - Owner's Telegram chat ID.
* `flyer_url` (TEXT) - Public URL link to the marketing PDF flyer stored in Supabase Storage.
* `created_at` (TIMESTAMPTZ)

### B. `visitors` Table (User Session Routing)
Maps customers chatting with the bot to the specific salon they visited:
* `visitor_chat_id` (TEXT, Primary Key)
* `active_business_id` (TEXT, Foreign Key -> `businesses.business_id`)

### C. `admin_relay` Table (Escalation Handoff Routing)
Manages active takeovers when a human admin is messaging a customer directly:
* `visitor_chat_id` (TEXT, Primary Key)
* `business_id` (TEXT, Foreign Key -> `businesses.business_id`)
* `is_paused` (BOOLEAN) - Mutes AI responses when human is active.
* `pending_question` (TEXT, Nullable) - Logs the visitor query to pair with the admin's reply.

### D. `knowledge_chunks` Table (Shared Vector Database)
Stores all RAG indexing data for all tenants:
* `id` (UUID, Primary Key)
* `business_id` (TEXT, Foreign Key -> `businesses.business_id`)
* `content` (TEXT) - Page text chunk.
* `embedding` (VECTOR(1536)) - Vector representations powered by `pgvector` (uses Gemini text embedding API).
* `metadata` (JSONB)
* *Index*: HNSW index on `embedding` for fast similarity searches.

### E. `escalations_cache` Table (Fuzzy Resolved Q&A Cache)
* `id` (BIGINT, Primary Key)
* `business_id` (TEXT, Foreign Key -> `businesses.business_id`)
* `question` (TEXT)
* `answer` (TEXT)
* `timestamp` (TIMESTAMPTZ)
* *Constraint*: Unique index on `(business_id, question)`

---

## 4. Asynchronous Crawler Queue & Background Worker

To handle long-running crawlers safely, we run a persistent task queue using Supabase.

### A. `crawl_jobs` Queue Table
* `id` (UUID, Primary Key)
* `business_id` (TEXT, Foreign Key -> `businesses.business_id`)
* `website_url` (TEXT)
* `status` (TEXT) - `'pending'`, `'processing'`, `'completed'`, `'failed'`.
* `error_message` (TEXT, Nullable)
* `created_at` / `updated_at` (TIMESTAMPTZ)

### B. The Background Worker (`worker.py`)
A separate, lightweight Python daemon process runs on the VPS to handle execution queues:

1. **Job Selection (Row Locking)**:
   The worker queries the queue using database locks to prevent race conditions:
   ```sql
   SELECT * FROM crawl_jobs 
   WHERE status = 'pending' 
   LIMIT 1 
   FOR UPDATE SKIP LOCKED;
   ```
 2. **Crawl & Scraping**:
    Updates status to `'processing'` and runs the Crawl4AI scraper on `website_url`.
 3. **Information Extraction**:
    Runs a structured Gemini model extraction on the crawled pages to identify contact details (phone, address, email).
 4. **Non-Destructive Overrides (COALESCE)**:
    Performs a SQL update on `businesses` using `COALESCE`. Pre-configured owner coordinates (phone/email/address/map) are preferred and preserved; the crawler only writes back newly scraped values if the fields in the database are currently NULL.
 5. **Vector Generation**:
    Generates Gemini embeddings for the new markdown page chunks and stores them in `knowledge_chunks`.
 6. **Printable Flyer Compilation**:
    Dynamically draws a high-fidelity US Letter marketing flyer using `reportlab` containing custom step-by-step instructions and a generated QR code linking to the customer chat deep link (`t.me/Dmhaircarebot?start=v_[business_id]`).
 7. **Supabase Storage Upload**:
    Uploads the PDF flyer to the public `flyers` storage bucket in Supabase (specifying `content-type: application/pdf`), gets the public URL, and saves it in `businesses.flyer_url`.
 8. **Callback Notification**:
    Changes job status to `'completed'` and (if `admin_chat_id` is set) sends a Telegram alert directly to the owner with their registered details and a clickable download link for their printable marketing flyer.

### C. Bulk Onboarding via Database Ingestion (`business_load` Table)
To support bulk registration of businesses outside Telegram (e.g., uploading a CSV sheet of salons directly to the Supabase dashboard):
1. **Staging Queue**: Business profiles are uploaded directly to the `business_load` table with a status of `'pending'`.
2. **Ingestion Loop**:
   * The background worker periodically scans for pending rows:
     `SELECT * FROM business_load WHERE status = 'pending'`
   * For each record, the worker:
     1. Creates the business profile entry in the `businesses` table.
     2. Automatically inserts a crawl job into the `crawl_jobs` table (which handles crawling, coordinates extraction, and vector index generation).
     3. Marks the row in `business_load` as `'completed'` and sets `processed_at = now()`.
3. **Dynamic Admin Binding**: If the `admin_chat_id` was left empty during the bulk upload, the business owner can activate their bot panel later by typing `/start a_[business_id]` to claim ownership.

---

## 5. Owner Management Command (`/settings`)

Once registered, an admin can send `/settings` to the Telegram bot to control their tenant configurations:
* **`🔄 Recrawl Website`**: Creates a new task inside `crawl_jobs` to refresh policies and vectors from their site.
* **`👤 Change Agent Name`**: Update the AI chatbot persona name.
* **`⚙️ Update Timezone`**: Change local timezone settings.
* **`📊 View Stats`**: Display monthly chat metrics.
