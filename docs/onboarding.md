# Frontdesk Customer Onboarding & Operator Manual

This document provides step-by-step instructions on onboarding service businesses, configuring custom details, deploying marketing materials, and managing customer handoffs.

---

## 1. Prerequisites
Before starting, ensure that:
1. The **Admin Console** is live and accessible on **`http://localhost`** (or your server domain).
2. The **Telegram Bot** (`@Frontdeskexpert_test_bot` or your production bot) is online and active.
3. You have retrieved your personal **Telegram Chat ID** (using [@userinfobot](https://t.me/userinfobot) or similar) to test the owner activation step.

---

## 2. Onboarding a Business (Step-by-Step)

```
[Onboard Tab] ➡️ [Register Form / CSV] ➡️ [Playwright Crawling] ➡️ [Generate Flyer/QR]
```

### Step 2.1: Register the Profile
You can onboard a business in one of two ways inside the **Onboard Businesses** tab:

* **Method A: Manual Form**:
  1. Fill in the **Business Name** (e.g. `Silicon Valley Style Salon`). The system will automatically generate the unique ID slug `silicon-valley-style-salon`.
  2. Enter the **Website URL** containing the business policies/services (e.g. `https://example.com`).
  3. Enter the **AI Assistant Name** (e.g. `Sarah`).
  4. (Optional) Provide contact overrides under **Verified Phone**, **Verified Email**, and **Verified Address**.
     * *Note: Phone inputs are formatted to E.164 (`+14085551212`) automatically when you tab out.*
  5. Click **Register and Start Crawling**.

* **Method B: CSV Bulk Import**:
  1. Prepare a CSV file containing at least the headers: `business_name` and `website_url`.
  2. You can optionally include columns for `business_phone`, `business_email`, `business_address`, `agent_name`, and `business_id` (slug).
  3. Drag and drop the CSV file into the upload zone.
     * *Validation check: The parser automatically validates email and phone formatting. If any row contains an invalid format, the import is blocked and error locations are displayed.*

### Step 2.2: Track Ingestion
Once registered, the business is added to the background crawler queue:
1. Go to the **SaaS Dashboard** tab.
2. Under **Background Crawl Queue Status**, locate your business.
3. Track the crawl status. It will transition from `pending` ➡️ `processing` ➡️ `completed`.
4. When `completed`, go to the **Search Directory** tab. You can select the business and inspect the raw text facts crawled from the website under the **Vector Knowledge Index** inspector.

---

## 3. Activating the Business Owner Chat

Once crawling completes, the virtual receptionist assets are compiled. You must now bind the business owner's Telegram account so they can receive handoff notifications:

1. Open the **Search Directory** tab.
2. Select the business (e.g. `Silicon Valley Style Salon`).
3. Under **Marketing & PDF Assets**, locate the **Owner Activation QR Code** or copy the **Activation Link** (which starts with `https://t.me/your_bot?start=a_slug`).
4. Send this activation link/QR to the business owner.
5. When the owner clicks the link and taps **Start** on Telegram, the bot will display:
   `👑 Welcome! You are now the verified administrator for Silicon Valley Style Salon.`
   *In the background, this binds their Telegram `chat_id` as the `admin_chat_id` in the database.*

---

## 4. Deploying the Customer Assistant
Once activated, the receptionist is ready for visitors:
1. Download the generated **Customer Flyer PDF** from the **Search Directory** tab.
2. Print this flyer and display it on the storefront physical counter or entrance window.
3. When customers scan the flyer's QR code (which embeds the deep link `t.me/your_bot?start=v_slug`), it opens their Telegram app and starts the AI virtual assistant conversation!

---

## 5. Handling Escalations (Human Handoff)

When the AI receptionist meets a question it cannot answer from the website data, the human takeover sequence begins:

```
[Visitor message] ➡️ [AI Mutes] ➡️ [Telegram Alert to Owner] ➡️ [Owner Replies] ➡️ [AI Learns]
```

1. The visitor is automatically notified: *"Let me escalate this to our staff to help you directly."*
2. The owner receives an immediate Telegram alert:
   `🚨 Handoff Escalation Triggered!`
   `🏢 Business: Silicon Valley Style Salon`
   `💬 Visitor Message: "Do you offer wedding styling packages?"`
3. The owner clicks the inline button **`💬 Reply to Visitor`** and types their answer. The bot immediately forwards their response to the visitor's Telegram window.
4. Once resolved, the owner clicks **`✅ Resolve Chat`**. This unmutes the AI receptionist and caches the question/answer pair in the database (`escalations_cache`) so that if any future visitor asks the same question, the AI can answer it automatically without needing human help!
5. On the **SaaS Dashboard** tab, operators can monitor active takeovers in real-time under the **Active Handoff Takeovers** log table.
