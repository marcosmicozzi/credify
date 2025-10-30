# Streamlit + OAuth changed env / missing dotenv

Date: 2025-10-30

## Summary
After clicking “Sign in with Google,” the app crashed with `ModuleNotFoundError: No module named 'dotenv'`. This happened even when the app was launched from the correct conda environment (`MarcosPython10`) where `python-dotenv` is installed.

## What Happened
- The app was started from `MarcosPython10`, served on `http://localhost:8501`.
- On Google sign-in, Streamlit/OAuth restarted or spawned a new backend process.
- A background Python/Streamlit instance (often on a different port like 8502/8503) was running in the default `base` environment where `python-dotenv` was not installed.
- That process handled the OAuth callback, leading to the `dotenv` import error.

## Root Cause
1) Multiple Python/Streamlit processes were active (some orphaned), causing port hand-offs (8501 → 8502/8503).
2) The OAuth callback/subprocess inherited the wrong environment (Anaconda `base`), where `python-dotenv` wasn’t available.

## How We Fixed It
- Ensured only a single Streamlit instance was running.
- Killed stray Python/Streamlit processes via Activity Monitor (or `pkill -f streamlit`).
- Relaunched the app from the correct env:
  ```bash
  conda activate MarcosPython10
  cd /Users/kimberleybrown/Desktop/coding_all/Code_Academy_Berlin/credify
  streamlit run credify_app.py --server.port 8501
  ```
- After cleaning up, Google sign-in worked without switching environments.

## Preventive Workarounds
- Single-instance rule: before restarting, close old terminals and browser tabs; if in doubt, kill lingering processes:
  ```bash
  pkill -f streamlit
  # or, more aggressive
  pkill -f python
  ```
- Pin the port explicitly to keep behavior predictable:
  ```bash
  streamlit run credify_app.py --server.port 8501
  ```
- Always launch from the intended env (check your prompt shows `(MarcosPython10)`).
- Optional quick unblock (not ideal): install `python-dotenv` into `base` too so OAuth fallbacks don’t fail:
  ```bash
  conda activate base && pip install python-dotenv
  ```
  Note: This reduces isolation; prefer running everything from the project env.
- Optional automation: use VS Code to start login shells or add direnv/auto-activation later once stable.

## Commands Reference
```bash
# Run on a fixed port
streamlit run credify_app.py --server.port 8501

# See running streamlit processes
ps aux | grep streamlit

# Kill all streamlit processes
pkill -f streamlit

# Start from correct env
conda activate MarcosPython10
```

## Status
Resolved. Keep one active Streamlit instance and always start from `MarcosPython10` to avoid OAuth switching to a different environment.


