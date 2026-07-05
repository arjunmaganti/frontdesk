# AI Agent Orchestration & Design Document

---

## 1. Conversation Design Overview

The virtual receptionist conversation flow uses a hybrid **LangGraph / RAG** state machine to classify visitor intents, retrieve contextual business facts from the vector store, handle small talk, and trigger human escalations.

```
                  ┌────────────────────────┐
                  │      User Message      │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │    Intent Classifier   │
                  └───────────┬────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    [ Greeting ]        [ KB Query ]        [ Handoff ]
 (Prompt: Hello cards)        │       (Mute AI & Notify Owner)
                              │
                              ▼
                    ┌───────────────────┐
                    │ pgvector Search   │
                    └─────────┬─────────┘
                              │
          ┌───────────────────┴───────────────────┐
          ▼                                       ▼
    [ Match Found ]                        [ No Match ]
(Generate RAG response)               (Trigger Handoff Fallback)
```

---

## 2. Intent Routing & State Machine

Every user message is passed to the orchestrator classifier node, which routes the request to one of three branches based on semantic classification:

### 2.1 Greeting / Conversation Start
* **Trigger**: Simple greetings, greetings combined with general small talk (e.g. *"Hello"*, *"Good morning"*, *"Who are you?"*).
* **Action**: Returns a welcoming greeting presenting the assistant's persona (e.g., *"Hello! I am Sarah, your virtual front desk assistant..."*) and lists the core capabilities of the bot.

### 2.2 Knowledge Base Query (RAG search)
* **Trigger**: Inquiries about services, pricing, business hours, addresses, contact details, or scheduling.
* **Action**:
  1. Computes the embedding of the visitor's message using `gemini-embedding-001`.
  2. Queries the `public.knowledge_chunks` table using cosine similarity (`<=>` operator) filtered by the tenant's `business_id` to retrieve the top 3 matching text chunks.
  3. Appends the retrieved facts into the system prompt context.
  4. Generates a response using `gemini-2.5-flash`.
  5. **Fallback Guard**: If no relevant facts are found, or the query matches the fallback threshold, it outputs the fallback escalation message: *"I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."*

### 2.3 Human Handoff (Escalation)
* **Trigger**: Visitor explicitly asks for support (e.g. *"let me talk to a human"*, *"I want to complain"*) OR RAG returns the fallback escalation message.
* **Action**:
  1. Sets `is_paused = true` in the `admin_relay` database table for this user.
  2. Saves the visitor's question in `pending_question`.
  3. Sends a notification to the owner's Telegram chat containing the visitor's question and options to reply or resolve.

---

## 3. Prompts & Persona Guidelines

To ensure professional, reliable, and brand-safe interactions, the agent uses a strict system prompt instruction set:

```text
You are {agent_name}, the professional AI front desk receptionist for {business_name}. 
Your goal is to answer visitor questions accurately and politely using only the provided facts.

Guidelines:
1. Speak in a helpful, friendly, and professional receptionist tone.
2. Answer queries strictly using the provided context chunks. Do not make up facts.
3. If a visitor asks about booking or scheduling, provide their online booking URL: {website_url}.
4. If the retrieved context does not contain the answer, output the exact fallback text:
   "I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."
5. Never mention technical parameters, databases, or RAG details to the user.
```

---

## 4. Short-Term Memory Checkpointing
Conversations maintain context across user interactions using thread-level memory checkpointing:
* **Session Tracking**: LangGraph references a unique `thread_id` (the visitor's Telegram `chat_id`).
* **Context Preservation**: Up to the last 10 messages are preserved in the conversation history, allowing the assistant to follow up on multi-turn conversations (e.g., Visitor: *"Where are you located?"* -> Bot: *"We are at 123 Main St."* -> Visitor: *"Is there parking nearby?"* -> Bot reads context for parking details).
