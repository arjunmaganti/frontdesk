# Implementation Plan - Secure Backend API Proxy with JWT Authentication & Login Page

This plan outlines migrating direct database queries from the React Admin Console (browser) behind a secure Python FastAPI proxy layer (`agent/main.py`), protected by Supabase JWT bearer token authentication, and adding a sleek, secure login interface to the Admin Console.

## User Review Required

> [!IMPORTANT]
> * The frontend console will now ONLY connect to Supabase for User Authentication. 
> * All database read/write/delete operations will run through the backend API proxy.
> * The React bundle will only require the public `VITE_SUPABASE_ANON_KEY` (completely safe to expose).
> * The highly sensitive `SUPABASE_SERVICE_ROLE_KEY` will remain strictly resident on the backend server.

---

## Proposed Changes

### 1. Backend Proxy API Service (`agent`)

We will expose REST endpoints inside [agent/main.py](file:///Users/deepakmaganti/projects/frontdesk/agent/main.py) to proxy database queries securely. We will add a dependency to validate the visitor's JWT token against the Supabase Auth server.

#### [MODIFY] [main.py](file:///Users/deepakmaganti/projects/frontdesk/agent/main.py)
* Add a security dependency `validate_token(authorization: str = Header(...))`:
  * Extracts the JWT token from the `Authorization: Bearer <token>` header.
  * Sends a quick validation request to `{SUPABASE_URL}/auth/v1/user` using the token.
  * If the response is `200 OK`, authentication is successful; otherwise, raise `401 Unauthorized`.
* Protect the following endpoints with this dependency:
  * `GET /api/businesses`
  * `GET /api/crawl-jobs`
  * `GET /api/admin-relay`
  * `GET /api/daily-usage`
  * `GET /api/knowledge-chunks`
  * `POST /api/business-load`
  * `DELETE /api/businesses/{id}`
  * `DELETE /api/business-load/{id}`

---

### 2. React Admin Console (`admin`)

We will introduce a login interface and configure the client to send JWT tokens on every database request.

#### [MODIFY] [supabase.ts](file:///Users/deepakmaganti/projects/frontdesk/admin/src/supabase.ts)
* Change the client initialization key to utilize the public `VITE_SUPABASE_ANON_KEY`.

#### [MODIFY] [App.tsx](file:///Users/deepakmaganti/projects/frontdesk/admin/src/App.tsx)
* **Login Form UI**:
  * Add a state `session` to track the active Supabase login.
  * If no active session, display a dark-themed, glassmorphic Login Page (with fields for email and password). No signup button is provided; all admin accounts are created directly via the Supabase Dashboard.
  * Use `supabase.auth.signInWithPassword` to handle login, and `supabase.auth.signOut` for log out.
* **Token Ingestion**:
  * Implement an `authenticatedFetch(url, options)` helper wrapper.
  * This helper retrieves the latest JWT access token from the active Supabase session and attaches it to the headers as `Authorization: Bearer <token>`.
* **Redirect Database Calls**:
  * Rewrite `loadData()`, `loadBusinessChunks()`, `handleSubmit()`, `handleCsvImport()`, and `executeDeleteBusiness()` to use `authenticatedFetch()` to call our backend endpoints.

---

## Verification Plan

### Automated Verification
* Run local python agent test execution to verify API endpoints return data correctly:
  * `.venv/bin/python agent/main.py`
* Verify compiler/bundle success in `admin/` using:
  * `npm run build` inside container/locally.

### Manual Verification
* **Account Setup**: Create a user account via the Supabase Dashboard (under Authentication > Users > Add User).
* **Login Test**: Open **`http://localhost`**, verify that you are redirected to the Login Page, and enter the credentials.
* **Unauthorized Access Block**: Verify that trying to access `/api/businesses` without a token (or with an invalid token) returns a `401 Unauthorized` error.
* **Success Flow**: Verify that after logging in, all dashboard analytics, queues, maps, search registries, and inline deletions function perfectly.
