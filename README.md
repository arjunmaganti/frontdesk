# Frontdesk: Multi-Tenant AI Virtual Receptionist Platform

Frontdesk is a plug-and-play **B2B SaaS Multi-Tenant AI Receptionist Platform** designed to bring digital front desks to physical local service storefronts (salons, mechanics, clinics, cafes, etc.) instantly. 

The platform crawls a storefront's website to auto-generate a custom AI receptionist on messaging channels (starting with Telegram), provides beautiful printable marketing flyers/QR codes, and integrates a hybrid human-in-the-loop escalation system for business owners.

---

## 📖 Platform Documentation Index

To explore the architecture, product specifications, or operational guides, refer to the dedicated documentation files inside the `docs/` directory:

1. **[VC Product Pitch](docs/pitch.md)**: Product vision, market opportunities, core value propositions, and unit economics designed for investors and stakeholders.
2. **[Product Requirement Document (PRD)](docs/prd.md)**: System scopes, user personas, detailed functional specs (forms, CSV uploads, auto-slugs, validations), and requirements.
3. **[System Architecture Guide](docs/architecture.md)**: High-level microservices diagram, Supabase/PostgreSQL pgvector database schemas, ingestion pipelines, and continuous deployment configurations.
4. **[AI Agent Design Specs](docs/agent_design.md)**: Core LangGraph/LangChain orchestrator state machine, intent classifier rules, vector RAG search parameters, prompts, and thread memory checkpointing.
5. **[Customer Onboarding Manual](docs/onboarding.md)**: Step-by-step instructions on onboarding client profiles, bulk-uploading CSV records, activating business owners, printing flyers, and resolving Telegram human escalations.
6. **[AI Agent Default Assumptions](agent/assumptions.md)**: System-wide assumptions and fallback behaviors (such as defaulting business hours to 9 AM - 5 PM) when specific storefront data is missing.

---

## 🚀 Quick Start (Local Development)

### 1. Populate Local Configuration
Copy the sample environment template and fill in your Supabase, Gemini, and Telegram staging credentials:
```bash
cp .env.example .env
# Edit the .env file with your local keys
```

### 2. Start the Multi-Tenant Stack
Frontdesk is fully containerized. To spin up the React Admin Console, the FastAPI Telegram Service, and the Background Scraper Worker:
```bash
docker compose up -d --build
```
* **Admin Console Interface**: Live on **[http://localhost](http://localhost)**.
* **Agent Bot Engine**: Accessible on port **`8000`** (and polling Telegram API).
* **Crawler Daemon**: Running as a background task worker.

To tear down the containers:
```bash
docker compose down
```
