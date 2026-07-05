# Frontdesk Product Requirements Document (PRD)

---

## 1. Product Overview & Goals
Frontdesk is a multi-tenant SaaS platform that generates customized AI assistants for local service businesses. It enables storefronts to deploy a virtual receptionist chatbot via messaging applications (specifically Telegram) to automate client FAQs, routing, and directions, with a seamless handoff to human staff when needed.

### Key Goals:
1. **Frictionless Onboarding**: Enable operators to set up an AI receptionist for any business simply by inputting its URL.
2. **Hybrid Customer Support**: Keep human staff in control via automatic AI-mute and real-time Telegram escalations.
3. **Continuous Learning**: Improve AI performance dynamically by caching human resolutions for future customer queries.
4. **Physical-to-Digital Bridge**: Provide owners with instantly printable, high-fidelity marketing assets (QRs, flyers).

---

## 2. User Roles & Personas
* **Operator**: The system administrator or reseller who configures tenant profiles, runs crawls, monitors crawler logs, and resolves system issues via the Admin Console.
* **Business Owner**: The manager or receptionist of the storefront. They receive escalations, reply to blocked user threads via Telegram, and print physical QR materials.
* **Visitor**: The business's end-customer who scans the QR code or clicks a link to ask questions, view hours, get locations, or book appointments.

---

## 3. Functional Requirements

### 3.1 Multi-Tenant Onboarding & CSV Bulk Processing
* **Onboarding Form**: The operator console must have inputs for Business Name, Website URL, AI Assistant Name, and optional contact overrides (Phone, Email, Address).
* **Automatic Slug Generator**: When typing a business name, the console must auto-generate a unique URL-friendly slug ID (lowercase, alphanumeric, space-to-hyphen).
* **Auto-Formatting Phone Input**: Phone input must auto-clean formatting (parentheses, spaces, hyphens) and format US numbers to E.164 (`+1XXXXXXXXXX`) on blur (`onBlur`).
* **CSV Bulk Upload**: Supports importing multiple businesses at once. The parser must validate phone and email fields, block the import if errors are found, and print row/column error notifications.
* **Database Trigger Generation**: If the slug or map URL is empty, a PostgreSQL trigger function (`BEFORE INSERT`) must auto-compute them database-side.

### 3.2 AI Agent & Deep Linking
* **Deep Link Routing**: A single Telegram bot token must handle distinct tenants:
  * `t.me/bot?start=v_[business_id]` routes to a **Visitor conversation**.
  * `t.me/bot?start=a_[business_id]` routes to an **Owner activation**.
* **Intent Routing**: The LLM must classify visitor messages:
  * *Greeting*: Small talk.
  * *KB Query*: Execute pgvector search in the business’s knowledge base.
  * *Handoff*: Trigger escalation if they request human support or RAG fails.

### 3.3 Hybrid Escalation & Handoff
* **Mute/Pause Action**: On handoff trigger, the visitor’s chat session is marked `is_paused = true`. The AI stops responding to further visitor messages.
* **Alert Prompt**: The registered admin receives a Telegram notification containing the visitor's question with inline options: `[💬 Reply to Visitor]` and `[✅ Resolve Chat]`.
* **Relay Chatting**: When the owner selects `[💬 Reply to Visitor]` and responds, the bot forwards their text directly to the visitor.
* **Resolution & Caching**: When selecting `[✅ Resolve Chat]`, the AI is unmuted, and the owner’s answer is saved to `escalations_cache` so the AI learns from it.

### 3.4 Background Crawler Worker
* **Scraper Engine**: Playwright crawls the target site up to 15 pages deep, converting content to markdown.
* **AI Extraction**: Uses the LLM (`gemini-2.5-flash`) to parse markdown, extract contact coordinates (phone, address, email), and save them to the business metadata.
* **Vector Vectorization**: Splits markdown text into 1,000-character chunks and calls the Gemini embedding API to insert vector data (`vector(3072)`) into `knowledge_chunks`.

### 3.5 PDF Flyer & Asset Generation
* **Branded Flyers**: Automatically generates a US Letter PDF flyer containing the salon name, AI receptionist name, contact numbers, instructions, and a visitor QR code.
* **QR Centering**: The QR code must be centered within the card box container on the flyer with clean, balanced padding and no text overlaps.
* **Storage Upload**: Uploads flyers and QR images to Supabase Storage and records public URLs in the database.

---

## 4. Technical Non-Functional Requirements
* **Response Latency**: AI chat responses must compile and send in under **2.5 seconds**.
* **Scalability**: Database schema must handle up to **10,000 active tenants** without degradation.
* **Resiliency**: The bot must queue failed messages and retry when connection drops.
