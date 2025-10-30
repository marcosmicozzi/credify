## Credify

Streamlit app that lets creators claim credits on YouTube projects and aggregates performance metrics via Supabase and the YouTube Data API.

### Features
- **Authentication**: Lightweight login flow integrated into Streamlit (`auth.py`).
- **Dashboard**: Personal metrics and credited projects.
- **Claim Credits**: Claim roles on a YouTube video by URL with role taxonomy.
- **Metrics**: Fetches and stores YouTube statistics; summary metrics per user.

### Project structure
- `credify_app.py`: Main multi‑page Streamlit app (Dashboard, Claim Credits, Explore, Settings)
- `auth.py`: Auth helpers (login UI, logout controls)
- `dashboard.py`: Legacy/alternate view
- `add_to_supabase.py`: Standalone ingestion helper
- `claim_role.py`: Standalone claim flow (older script)
- `update_user_metrics.py`: Aggregates metrics per user
- `test_supabase.py`, `test_youtube_fetch.py`: Manual demo scripts

### Prerequisites
- Python 3.10+
- Pipenv or venv (recommended)
- A Supabase project with RLS enabled
- YouTube Data API key

### Quick start
1) Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies
```bash
pip install streamlit supabase python supabase==2.* requests pandas
```

3) Configure secrets for Streamlit
Create `.streamlit/secrets.toml` at the repo root:
```toml
SUPABASE_URL = "https://YOUR-PROJECT.ref.supabase.co"
SUPABASE_ANON_KEY = "YOUR-ANON-KEY"
YOUTUBE_API_KEY = "YOUR-YOUTUBE-API-KEY"
```

4) Run the app
```bash
streamlit run credify_app.py
```

### Supabase setup
Tables expected (high‑level):
- `users` (u_id, u_email, u_name, u_bio, ...)
- `projects` (p_id [YouTube id], p_title, p_link, p_platform, ...)
- `user_projects` (u_id, p_id, u_role)
- `metrics` (p_id, view_count, like_count, comment_count, created_at)
- `latest_metrics` (materialized/latest metrics per project)
- `user_metrics` (aggregated totals per user)
- `roles` (role_name, category)

Security and RLS:
- Use only the Supabase anon key in the client.
- Enable RLS on all tables; add policies so users can read public project data and only access their own user records and user‑project links.

### Usage notes
- The Streamlit app reads secrets via `st.secrets[...]` and initializes one Supabase client per process.
- Claiming a role by YouTube URL will create the `projects` row (if missing), insert an initial `metrics` snapshot, upsert the `users` record, and link via `user_projects`.
- The Dashboard reads `user_metrics` and `latest_metrics` for a quick overview.

### Development guidelines
- Python style: prefer clear names, add type hints to function signatures where helpful, prefer guard clauses, avoid broad try/except. Add timeouts to network calls.
- Streamlit auth: gate pages with `if "user" not in st.session_state: show_login(); st.stop()` and provide a `logout_button()`.
- Supabase queries: check `.data` before indexing; prefer `upsert(..., on_conflict=...)` for idempotent writes; batch where possible.
- Security: never use service role keys in the app; validate and normalize inputs (emails to lowercase, URLs sanitized); avoid unsafe HTML from external/user content.

### Scripts
- `update_user_metrics.py`: recompute and store per‑user aggregates.
- `add_to_supabase.py`: one‑off ingestion helper.
- `test_supabase.py`, `test_youtube_fetch.py`: manual checks for local setup.

### Troubleshooting
- Missing or wrong secrets: ensure `.streamlit/secrets.toml` exists with correct keys and the app restarted.
- 401/403 from Supabase: verify anon key, RLS policies, and table names.
- YouTube API errors: confirm the API key is enabled for the YouTube Data API and not rate‑limited.
- Import errors: confirm virtualenv is active and dependencies installed.

### License
MIT (or your preferred license). Update this section as needed.

# IMPORTANT ENVIRONMENT SETUP

> **Before installing packages or running this app, always run:**
>
>     conda activate MarcosPython10

This ensures all required dependencies are available and prevents confusing errors during development or Google sign-in.

# Environment Variables Setup (Recommended)

Instead of using `.streamlit/secrets.toml`, you can store your Supabase credentials as environment variables for improved security.

## Option 1: Using a `.env` File (Recommended for local/dev)

1. **Install python-dotenv** (if not already):
   ```bash
   pip install python-dotenv
   ```
2. **Create a file named `.env` in your project root:**
   ```env
   SUPABASE_URL="https://your-project.supabase.co"
   SUPABASE_KEY="your_supabase_anon_key"
   ```
   - **DO NOT** commit `.env` to git. Add it to your `.gitignore`.

3. **Load .env in your code:**
   ```python
   from dotenv import load_dotenv
   load_dotenv()  # load env vars before using them

   import os
   SUPABASE_URL = os.getenv("SUPABASE_URL")
   SUPABASE_KEY = os.getenv("SUPABASE_KEY")
   ```


## Option 2: Exporting in Your Shell

1. **Export in your terminal:**
   ```bash
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_KEY="your_supabase_anon_key"
   ```
2. Then run your app in the same shell session.

## In Your App Imports
No matter the method, use this in your Streamlit app:
```python
import os
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
```
--
**Benefits:** Keeps secrets out of your repo. Cursor/tooling can still launch and use your app — without seeing your secrets.




