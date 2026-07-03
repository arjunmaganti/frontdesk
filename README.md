# Front Desk Telegram Bot (Python & LangGraph - Standalone Packaging Architecture)

This repository provides a multi-tenant compiler and standalone runtime engine for deploying front desk receptionist bots on Telegram. The bot answers visitor questions based on local Markdown policy files and supports automated human handoff when complex or sensitive issues arise.

---

## 1. Core Repository Structure

```text
frontdesk/
├── requirements.txt            # Python package dependencies
├── README.md                   # This file
├── DESIGN.md                   # Detailed architecture design document
├── core/                       # Shared bot runtime logic
│   ├── main.py                 # Bot runner (executes flat from unzipped deployable)
│   └── src/                    # Bot module code (agent, search loaders, config, and bot handlers)
└── utility/                    # Shared CLI tooling
    ├── build.py                # Workspace initializer & vector compiler / packager
    └── test_agent.py           # CLI-based local chat simulator
```

---

## 2. Quick Start (Local Development)

### Step 1: Install Dependencies
Create a virtual environment and install the required Python libraries:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Initialize a Client Workspace
Use the compiler script to initialize a new business workspace folder (e.g. `/Users/username/desktop/haircuts_config/`):
```bash
python3 utility/build.py --init /Users/username/desktop/haircuts_config/
```
This generates a template folder containing:
* `.env`: Configuration keys (Telegram token, Owner ID, Daily Cap, OpenAI API key).
* `visitor_policy.md` / `faq.md`: Sample Markdown documents.

### Step 2.5: Auto-Generate Markdown via Crawling (Optional)
If the business already has a public website, you can crawl it to auto-generate your Markdown policy files instead of writing them manually:
```bash
.venv/bin/python utility/crawl.py --url https://example-salon.com --out /Users/username/desktop/haircuts_config/
```
This recursively downloads body text blocks and filters out noise like headers and footers.

### Step 3: Populate Configs & Data
1. Open the generated `/Users/username/desktop/haircuts_config/.env` and paste your API keys.
2. Edit or add any custom Markdown (`.md`) files inside the folder representing your client's business hours, policies, or procedures.

### Step 4: Build and Package
Compile the client's documents and build the standalone ZIP deployment package:
```bash
python3 utility/build.py --src /Users/username/desktop/haircuts_config/ --out dist/deploy_haircuts.zip
```
This writes the standalone, deploy-ready **`dist/deploy_haircuts.zip`** file.

---

## 3. Local Verification (CLI Simulator)

To test the bot's RAG queries, rate limiters, daily budget caps, and handoff flows locally in your terminal before deploying:
```bash
python3 utility/test_agent.py --src /Users/username/desktop/haircuts_config/
```
Type queries directly into the terminal prompt. You can simulate visitor inputs and the admin `/resolve` handoff commands in real-time.

---

## 4. Production Deployment

To run a client bot 24/7 on a production VPS:

1. Upload the generated `dist/deploy_<tenant_id>.zip` to the VPS.
2. Extract the archive:
   ```bash
   unzip deploy_<tenant_id>.zip -d /home/ubuntu/frontdesk/
   cd /home/ubuntu/frontdesk/
   ```
3. Install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Set up a **`systemd`** watchdog service to manage the bot process:
   ```bash
   sudo nano /etc/systemd/system/frontdesk.service
   ```
   Add the configuration:
   ```ini
   [Unit]
   Description=Front Desk Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/frontdesk
   ExecStart=/home/ubuntu/frontdesk/.venv/bin/python main.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
5. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable frontdesk.service
   sudo systemctl start frontdesk.service
   ```

The bot will now run in the background, writing conversation backups to the local SQLite database `./state.db`.
