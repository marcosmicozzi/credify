# Streamlit MCP Integration Note

**Date:** 2025-01-27

## Context
Per workspace rule (`.cursor/rules/streamlit-mcp.mdc`), all Streamlit actions should use MCP integration wrappers when available.

## Current Status
No Streamlit MCP wrapper functions are currently available in this codebase. All Streamlit usage (`st.*` calls) is implemented using direct Streamlit API calls.

## Exception Rationale
- The codebase uses standard Streamlit patterns (`st.set_page_config`, `st.session_state`, `st.markdown`, etc.)
- Streamlit MCP integration tools are not configured or available in the development environment
- Auth helpers are centralized in `auth.py` for maintainability
- This exception is documented here for future reference

## Future Action
If Streamlit MCP wrappers become available, refactor the following files to use them:
- `credify_app.py` - Main app (page config, session state, UI components)
- `auth.py` - Authentication flows
- `scripts/test_youtube_fetch.py` - Test utilities

## Files Using Direct Streamlit Calls
- `credify_app.py`
- `auth.py`
- `test_youtube_fetch.py`

