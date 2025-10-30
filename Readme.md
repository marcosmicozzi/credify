## Credify

Streamlit app that lets creators claim credits on YouTube projects and aggregates performance metrics via Supabase and the YouTube Data API.

### Features
- **Single entry app**: Multi‑page Streamlit app in `credify_app.py` (Dashboard, Claim Credits, Explore, Settings).
- **Authentication**: Login flow via `auth.py` helpers.
- **Dashboard**: Personal metrics and credited projects (batch metrics queries).
- **Claim Credits**: Claim roles on a YouTube video URL with role taxonomy.
- **Metrics**: Fetches and stores YouTube statistics; summary metrics per user.

### Project structure
- `credify_app.py`: Main multi‑page Streamlit app (single entry)
- `auth.py`: Auth helpers (login UI, logout controls)
- `update_user_metrics.py`: Aggregates metrics per user
- `add_to_supabase.py`: Standalone ingestion helper (optional)
- `test_supabase.py`, `test_youtube_fetch.py`: Manual demo scripts
- Legacy (removed): `dashboard.py`, `claim_role.py`

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
pip install -r requirements.txt
```

3) Configure secrets for Streamlit (do not commit)
Create `.streamlit/secrets.toml` at the repo root:
```toml
SUPABASE_URL = "https://YOUR-PROJECT.ref.supabase.co"
SUPABASE_ANON_KEY = "YOUR-ANON-KEY"
YOUTUBE_API_KEY = "YOUR-YOUTUBE-API-KEY"
# Optional: enable demo login button
DEMO_MODE = "true"
```

Ensure `.streamlit/` is listed in `.gitignore` (it is). Keep this file local and untracked.

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

### Secrets handling
- Keep `.streamlit/secrets.toml` local and untracked (already ignored by `.gitignore`).
- If secrets were never committed or pushed, they are not exposed.
- If secrets were ever committed/pushed, immediately rotate them with your provider and purge them from git history (see next section).

### If secrets were committed: rotation and repo history purge
1) Rotate keys with providers
   - Supabase: create a new anon key and revoke the old one.
   - YouTube Data API: regenerate the API key and restrict it as needed.

2) Remove tracked secrets file and commit
```bash
git rm --cached .streamlit/secrets.toml
echo "# keep local only" >> .streamlit/secrets.toml
git commit -m "Remove tracked secrets file"
```

3) Purge from history (choose one tool)
- Using git-filter-repo (recommended):
```bash
pip install git-filter-repo
git filter-repo --path .streamlit/secrets.toml --invert-paths
```
- Using BFG Repo-Cleaner:
```bash
java -jar bfg.jar --delete-files secrets.toml
git reflog expire --expire=now --all && git gc --prune=now --aggressive
```

4) Force-push rewritten history (shared repos only if you understand the impact)
```bash
git push --force
```

5) Recreate/redeploy any environments with new keys

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
- Missing or wrong secrets: ensure `.streamlit/secrets.toml` exists locally with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `YOUTUBE_API_KEY` and restart the app.
- 401/403 from Supabase: verify anon key, RLS policies, and table names.
- YouTube API errors: confirm the API key is enabled for the YouTube Data API and not rate‑limited.
- Import errors: confirm virtualenv is active and dependencies installed.

### License
MIT (or your preferred license). Update this section as needed.

### Notes on configuration

- The app now reads all credentials from `st.secrets`; `.env` files are not required.
- For local development, prefer `.streamlit/secrets.toml` so Streamlit’s sharing/deployments map cleanly.




