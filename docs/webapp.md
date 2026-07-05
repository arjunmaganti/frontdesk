# Web App Chat Interface (Mobile-Friendly) - Design Document

---

## 1. Product Concept & Overview

Currently, storefront visitors access the AI virtual receptionist by scanning a QR code that redirects them to Telegram. While this is highly effective, it introduces friction for visitors who do not have the Telegram app installed or prefer a zero-install browser experience.

The **Frontdesk Web App** provides a clean, mobile-first, browser-based chat interface. When a user scans the business onboarding QR code, they are directed to a web application that offers a real-time, responsive receptionist chat matching the Telegram bot feature set.

```
                      ┌────────────────────────┐
                      │    Visitor Scans QR    │
                      └───────────┬────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       [ iOS/Android App ]               [ Mobile Browser ]
      Redirects to Telegram              Opens Web App URL
              │                                   │
              ▼                                   ▼
      Telegram Bot Chat                   Web App RAG Chat
```

---

## 2. Architecture & Service Boundaries

The Web App runs as a separate microservice with its own dedicated Docker image (`frontdesk-webapp`), communicating with the existing FastAPI backend.

```
┌────────────────────────┐      HTTP / SSE
│    React Web Client    ├───────────────────────┐
│ (Mobile Browser View)  │                       │
└────────────────────────┘                       ▼
                                       ┌───────────────────┐
                                       │  FastAPI Backend  │
                                       │    (agent API)    │
                                       └─────────┬─────────┘
                                                 │
                                                 ▼
                                       ┌───────────────────┐
                                       │    PostgreSQL     │
                                       │ (Supabase vector) │
                                       └───────────────────┘
```

### 2.1 Component Specifications:
1. **Frontend Interface (`webapp`)**:
   * Built with **Vite, React, and TypeScript**.
   * Served via a highly optimized **Nginx** container.
   * Completely static assets, running securely in the visitor's browser.
2. **Backend Extensions (`agent/main.py`)**:
   * We will leverage the existing `/api/chat` and `/api/chat/history` REST endpoints.
   * Add a new WebSocket or **Server-Sent Events (SSE)** endpoint to handle real-time operator overrides/handoff replies.

---

## 3. UI/UX & Mobile Layout Design

The Web App interface is designed to resemble premium native messaging applications:

* **Mobile-First Layout**: Centered single-column chat frame optimized for iOS/Android WebView.
* **Aesthetics**: Glassmorphic UI with a sleek dark mode dashboard, matching the Admin Console palette (`#06090e` base, `#00D2FF` primary highlights).
* **Typing Indicator**: Animated dots showing when the AI or operator is preparing a reply.
* **Persisted Session**: Automatically generates a unique anonymous `visitor_uuid` stored in browser `localStorage` to keep chat history intact even if the page is refreshed.

---

## 4. Feature Parity (Telegram Matching)

To provide an identical experience to the Telegram bot, the Web App supports:

### 4.1 RAG & Contextual Responding
* Visitor queries are routed to the orchestrator LangGraph state machine.
* The orchestrator performs pgvector cosine searches on storefront data chunks.
* The agent returns brand-safe, factual, and tz-aware answers.

### 4.2 Timezone-Aware Operating Hours & Reopening
* Handles questions like *"Are you open right now?"* by evaluating the storefront location's timezone local time against operating hours.
* Formulates closed messages dynamically (e.g. *"We'll be happy to assist you tomorrow Sunday at 9:00 AM, looking forward seeing you.."*).

### 4.3 Human Handoff & Operator Relay
* **Trigger**: If the visitor asks to speak with a human or the AI triggers the fallback rule, the chat session state is updated to `is_paused = true`.
* **Alerting**: The system alerts the store owner on Telegram as usual, including the visitor's question and a link to the Admin Console.
* **Relay Bridge**: When the owner replies via Telegram or the Admin Console:
  1. The backend inserts the message into the database.
  2. The backend sends a Server-Sent Event (SSE) to the visitor's browser.
  3. The React chat interface updates in real-time, displaying the staff reply.

---

## 5. Database Schema Extensions

To support anonymous web chat sessions alongside Telegram user IDs, the database will accommodate:

```sql
-- Extend admin_relay to support web visitors
ALTER TABLE public.admin_relay 
  ALTER COLUMN visitor_chat_id TYPE VARCHAR(255); -- Accepts either Telegram chat IDs or Web Session UUIDs

-- Create a session table for anonymous web users
CREATE TABLE public.web_sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id VARCHAR(255) REFERENCES public.businesses(business_id) ON DELETE CASCADE,
  visitor_ip VARCHAR(45),
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
```

---

## 6. Docker Containerization (`Dockerfile.webapp`)

We will introduce a new Docker configuration inside the `webapp` subdirectory:

```dockerfile
# webapp/Dockerfile
FROM node:22-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

This service will be registered in `docker-compose.yml` on port `8080:80` for easy deployment and testing.
