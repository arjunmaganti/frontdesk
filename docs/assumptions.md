# AI Agent Default Assumptions

This document lists the baseline assumptions and default behaviors configured for the Frontdesk AI receptionist when specific data is missing or incomplete in the crawled business records.

---

## 1. Core Operating Assumptions

The agent utilizes the following system-wide assumptions to maintain smooth, automated conversations without returning errors or empty responses:

| Category | Missing Data | Default Assumption / Action | Rationale |
| :--- | :--- | :--- | :--- |
| **Hours** | No operating hours specified or scraped | **Open daily (Monday – Sunday) from 9:00 AM to 5:00 PM** | Provides a standard, expected business schedule instead of failing or giving vague answers. |
| **Pricing** | No service price list provided | **State that rates depend on the service scope, and request contact details** | Prevents the agent from hallucinating arbitrary pricing while capturing leads. |
| **Booking** | No online booking link set | **Prompt the visitor to leave their name, phone, and preferred time** | Handled via direct handoff so the operator can schedule manually. |
| **Location** | Missing street address | **Direct user to email or call for full directions** | Avoids guessing geographic locations or addresses. |
| **Timezone** | No business timezone set | **Assume the timezone of the business address (fallback to Eastern Time, US & Canada)** | Ensures scheduled follow-ups and notifications align with local operations. |

---

## 2. Conversation & Tone Guidelines

> [!NOTE]
> When the knowledge base lacks information, the agent's primary directive is to capture client intent and route it to human staff rather than declaring ignorance repeatedly.

* **Message Length**: Responses are optimized for mobile chat (SMS, Telegram, WhatsApp) and must not exceed **3 sentences** unless listing specific options.
* **Knowledge Boundaries**: The agent must never declare that it is a LangGraph model, uses vector search, or database queries. It behaves strictly as a human assistant.
* **Handoff Triggers**: When a query cannot be answered by the knowledge base, the bot returns:
  > *"I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."*
  This automatically pauses the bot and alerts the owner.
