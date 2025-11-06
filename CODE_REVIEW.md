# Code Review: `get_redirect_url()` Simplification

**Date:** 2025-01-27  
**Files Changed:** `auth.py`  
**Reviewer:** Auto (AI Code Reviewer)

## Overview

This change simplifies the `get_redirect_url()` function in `auth.py` by removing extensive debug logging and fallback logic. However, a critical issue exists: a duplicate function definition in `credify_app.py` that shadows the import and uses different logic.

## Summary of Changes

### `auth.py`
- **Simplified `get_redirect_url()` function** (lines 140-153):
  - Removed extensive debug mode logging and sidebar output
  - Removed `OAUTH_REDIRECT_URL` secret check (was highest priority in old version)
  - Removed multiple environment variable fallback checks
  - Simplified to check `STREAMLIT_SHARING_BASE_URL` first, then defaults to localhost
  - Cleaner, more maintainable code structure
- **Added debug logging in `show_login()`** (lines 550-557):
  - Conditional debug output when `DEBUG_REDIRECT` secret is enabled
  - Shows environment detection details

---

## Review Checklist

### ⚠️ Functionality

- [ ] **Intended behavior works and matches requirements**
  - **CRITICAL ISSUE:** Duplicate function in `credify_app.py` (line 2439) shadows the import and uses different logic
  - **ISSUE:** Removed `OAUTH_REDIRECT_URL` secret support in `auth.py`, but `credify_app.py` version still uses it
  - The two implementations will behave differently, causing inconsistent OAuth redirect URLs
  - Localhost detection logic appears correct

- [x] **Edge cases handled gracefully**
  - Handles missing environment variables
  - Falls back to localhost when uncertain (appropriate for local dev)

- [x] **Error handling is appropriate and informative**
  - Debug mode provides helpful troubleshooting information
  - No error handling needed for simple environment variable checks

### 🔴 Code Quality

- [ ] **Code structure is clear and maintainable**
  - **CRITICAL:** Code duplication violates DRY principle
  - Function is cleaner but conflicts with duplicate implementation
  - Import shadowing creates confusion about which function is actually used

- [ ] **No unnecessary duplication or dead code**
  - **CRITICAL:** Duplicate `get_redirect_url()` function exists in `credify_app.py` (line 2439)
  - The duplicate shadows the import from `auth.py` (line 10)
  - Two different implementations may diverge over time
  - Maintenance burden - changes need to be made in two places

- [ ] **Tests/documentation updated as needed**
  - No tests for redirect URL detection
  - Docstring is clear but could mention the removal of `OAUTH_REDIRECT_URL` support

### ✅ Security & Safety

- [x] **No obvious security vulnerabilities introduced**
  - Redirect URL logic is safe
  - No sensitive data exposure
  - Debug output is properly gated behind secret flag

- [x] **Inputs validated and outputs sanitized**
  - Environment variables checked appropriately
  - URL sanitization with `.rstrip("/")` maintained
  - `.strip()` used to handle whitespace

- [x] **Sensitive data handled correctly**
  - No sensitive data in redirect URLs
  - Debug mode properly secured behind secret

---

## Detailed Findings

### 🔴 Critical Issues

#### 1. Duplicate Function Definition with Import Shadowing

**Location:** `credify_app.py:10` (import) and `credify_app.py:2439` (definition)

**Issue:** `get_redirect_url()` is imported from `auth.py` on line 10, but then redefined locally on line 2439. The local definition shadows the import, meaning the imported function is never actually used.

**Impact:**
- Code duplication violates DRY principle
- Two different implementations with different behavior:
  - `auth.py` version: Simple, checks `STREAMLIT_SHARING_BASE_URL`, defaults to localhost
  - `credify_app.py` version: Checks `OAUTH_REDIRECT_URL` secret first, then env vars, then defaults to localhost
- Inconsistent OAuth redirect URLs depending on which code path is used
- Maintenance burden - changes need to be made in two places
- Risk of bugs when implementations diverge

**Current Code in `credify_app.py`:**
```2439:2461:credify_app.py
def get_redirect_url() -> str:
    """Get OAuth redirect URL (reused from auth.py logic)."""
    # Try secrets first
    custom_redirect = st.secrets.get("OAUTH_REDIRECT_URL", None)
    if custom_redirect and str(custom_redirect).strip():
        return str(custom_redirect).strip().rstrip("/")
    
    # Check environment variables
    streamlit_url = (
        os.getenv("STREAMLIT_SHARING_BASE_URL") or 
        os.getenv("STREAMLIT_SERVER_URL") or
        os.getenv("STREAMLIT_CLOUD_BASE_URL")
    )
    if streamlit_url:
        return streamlit_url.rstrip("/")
    
    # Check hostname
    hostname = os.getenv("HOSTNAME", "")
    if hostname and "streamlit.app" in hostname.lower():
        return f"https://{hostname}".rstrip("/")
    
    # Default to localhost
    return "http://localhost:8501"
```

**Usage in `credify_app.py`:**
- Line 2473: `redirect_uri = get_redirect_url()` (Instagram OAuth callback)
- Line 2733: `redirect_uri = get_redirect_url()` (Instagram OAuth setup)

**Recommendation:**
1. **Remove the duplicate function from `credify_app.py`** (lines 2439-2461)
2. **Update `auth.py` to support `OAUTH_REDIRECT_URL` secret** if it's needed for Instagram OAuth
3. **Test Instagram OAuth flow** to ensure it works with the unified function
4. **Verify all OAuth flows** (Google and Instagram) work correctly

**Alternative Approach:**
If Instagram OAuth requires different behavior, consider:
- Creating a separate function `get_instagram_redirect_url()` with Instagram-specific logic
- Or adding an optional parameter to `get_redirect_url()` to handle different OAuth providers

#### 2. Inconsistent Behavior Between Implementations

**Issue:** The two implementations have different priority orders:

**`auth.py` version:**
1. `STREAMLIT_SHARING_BASE_URL` env var
2. Default to localhost

**`credify_app.py` version:**
1. `OAUTH_REDIRECT_URL` secret (highest priority)
2. `STREAMLIT_SHARING_BASE_URL` env var
3. `STREAMLIT_SERVER_URL` env var
4. `STREAMLIT_CLOUD_BASE_URL` env var
5. `HOSTNAME` with "streamlit.app" check
6. Default to localhost

**Impact:**
- Google OAuth (uses `auth.py` version) won't respect `OAUTH_REDIRECT_URL` secret
- Instagram OAuth (uses `credify_app.py` version) will respect `OAUTH_REDIRECT_URL` secret
- Inconsistent behavior may confuse users and cause OAuth configuration issues

**Recommendation:**
- Unify the implementations with a consistent priority order
- If `OAUTH_REDIRECT_URL` secret is needed, add it back to `auth.py` version
- Document the priority order clearly

### 🟡 Major Issues

#### 3. Removed OAUTH_REDIRECT_URL Secret Support

**Location:** Removed from `auth.py` (was in previous version)

**Issue:** The previous implementation checked for `OAUTH_REDIRECT_URL` in secrets as the highest priority. This has been removed from `auth.py`, but the duplicate in `credify_app.py` still uses it.

**Impact:**
- Users who set `OAUTH_REDIRECT_URL` in secrets will have it ignored for Google OAuth
- Instagram OAuth will still respect it (due to duplicate function)
- Less flexible configuration for Google OAuth
- Inconsistent behavior between OAuth providers

**Evidence:** The `secrets.toml` file shows `OAUTH_REDIRECT_URL` is still configured:
```11:11:.streamlit/secrets.toml
OAUTH_REDIRECT_URL="https://credifyapp.streamlit.app"
```

**Recommendation:**
- Restore `OAUTH_REDIRECT_URL` secret support in `auth.py` if it's still needed
- Or document that environment variables must be used instead
- Check if any deployment configurations rely on this secret

### 🟢 Minor Issues & Suggestions

#### 4. Docstring Could Be More Descriptive

**Location:** `auth.py:141-143`

**Current:**
```140:143:auth.py
def get_redirect_url() -> str:
    """
    Dynamically resolve the correct redirect URL depending on the environment.
    Returns localhost redirect in dev mode, Streamlit Cloud URL in production.
    """
```

**Recommendation:** Add more detail about:
- What environment variables are checked
- What the priority order is
- When each URL is returned

**Example:**
```python
def get_redirect_url() -> str:
    """Dynamically resolve the correct OAuth redirect URL based on environment.
    
    Checks environment variables in this order:
    1. STREAMLIT_SHARING_BASE_URL (production indicator)
    2. STREAMLIT_SERVER_PORT (localhost indicator)
    
    Returns:
        str: Redirect URL for OAuth callbacks
            - Production URL if STREAMLIT_SHARING_BASE_URL is set
            - Localhost URL (http://localhost:{port}) if running locally
            - Defaults to http://localhost:8501 if uncertain
    """
```

#### 5. Consider Adding OAUTH_REDIRECT_URL Support Back

**Recommendation:** If the secret-based configuration is useful (as evidenced by its presence in `secrets.toml`), consider adding it back with proper priority:

```python
def get_redirect_url() -> str:
    """Dynamically resolve the correct redirect URL depending on the environment."""
    # 1. Check explicit secret configuration (highest priority)
    custom_redirect = st.secrets.get("OAUTH_REDIRECT_URL")
    if custom_redirect and str(custom_redirect).strip():
        return str(custom_redirect).strip().rstrip("/")
    
    # 2. Check for Streamlit Cloud (production)
    sharing_url = os.getenv("STREAMLIT_SHARING_BASE_URL", "").strip()
    if sharing_url:
        return sharing_url.rstrip("/")
    
    # 3. Default to localhost
    port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
    return f"http://localhost:{port}"
```

---

## Architecture & Design

### ⚠️ Considerations

1. **Code Duplication:**
   - The duplicate function in `credify_app.py` is a critical architectural issue
   - Violates single source of truth principle
   - Creates maintenance burden and risk of bugs

2. **Simplification Trade-offs:**
   - **Pro:** Cleaner, more maintainable code in `auth.py`
   - **Con:** Removed useful configuration option (`OAUTH_REDIRECT_URL`)
   - **Con:** Created inconsistency with duplicate implementation

3. **OAuth Provider Consistency:**
   - Google OAuth and Instagram OAuth should use the same redirect URL logic
   - Currently they use different implementations with different behavior
   - This may cause configuration issues

---

## Security Assessment

### ✅ Security Practices Followed

1. **No sensitive data exposure** - Debug output is properly gated
2. **URL sanitization** maintained with `.rstrip("/")` and `.strip()`
3. **No injection vulnerabilities** in redirect URL construction

### ⚠️ Security Considerations

1. **Configuration Consistency:** Inconsistent redirect URL logic between OAuth providers could lead to misconfiguration
2. **Secret Handling:** If `OAUTH_REDIRECT_URL` secret is removed, ensure no deployments rely on it

---

## Testing Recommendations

### Missing Test Coverage

1. **Environment Detection:**
   - Test with `STREAMLIT_SHARING_BASE_URL` set
   - Test with `STREAMLIT_SERVER_PORT` set
   - Test with no environment variables (should use default)

2. **Integration:**
   - Test Google OAuth flow with detected redirect URL
   - Test Instagram OAuth flow with detected redirect URL
   - Verify both use the same redirect URL logic
   - Verify redirect URL matches what's configured in OAuth providers

3. **Secret Configuration:**
   - If `OAUTH_REDIRECT_URL` support is restored, test with secret set
   - Verify priority order (secret > env var > default)

### Suggested Test Cases

```python
# Example test structure (not implemented)
def test_get_redirect_url_production():
    """Test redirect URL detection on Streamlit Cloud."""
    with patch.dict(os.environ, {"STREAMLIT_SHARING_BASE_URL": "https://app.streamlit.app"}):
        assert get_redirect_url() == "https://app.streamlit.app"

def test_get_redirect_url_localhost():
    """Test redirect URL detection on localhost."""
    with patch.dict(os.environ, {"STREAMLIT_SERVER_PORT": "8501"}, clear=True):
        assert get_redirect_url() == "http://localhost:8501"

def test_get_redirect_url_default():
    """Test default behavior when no environment variables set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_redirect_url() == "http://localhost:8501"
```

---

## Action Items

### 🔴 Must Fix (Before Merge)

1. **Remove duplicate `get_redirect_url()` from `credify_app.py`** (lines 2439-2461)
   - Use the imported function from `auth.py` instead
   - Test Instagram OAuth flow to ensure it works

2. **Unify redirect URL logic**
   - Decide if `OAUTH_REDIRECT_URL` secret support is needed
   - If yes, add it back to `auth.py` with proper priority
   - If no, ensure `credify_app.py` doesn't need it

3. **Test all OAuth flows**
   - Verify Google OAuth works with unified function
   - Verify Instagram OAuth works with unified function
   - Ensure redirect URLs are consistent

### 🟡 Should Fix (Recommended)

4. **Improve docstring** - Add more detail about behavior, priority order, and defaults

5. **Add logging** - Consider using Python logging instead of conditional debug prints

6. **Document configuration** - Update deployment docs if secret-based config was removed

### 🟢 Nice to Have

7. **Add tests** - Unit tests for redirect URL detection

8. **Consolidate logic** - Ensure `is_localhost()` and `get_redirect_url()` use consistent detection

---

## Overall Assessment

**Status:** 🔴 **BLOCKED - CRITICAL ISSUES MUST BE FIXED**

The simplification is a good direction, but critical architectural issues need to be addressed:

### Critical Blockers
- **Duplicate function definition** must be removed - this is a fundamental code quality issue
- **Inconsistent behavior** between OAuth providers must be resolved
- **Import shadowing** creates confusion and maintenance burden

### Strengths
- Cleaner, more maintainable code structure in `auth.py`
- Removed excessive debug logging
- Simplified logic flow
- Proper debug mode gating

### Areas for Improvement
- Address code duplication immediately
- Unify OAuth redirect URL logic across all providers
- Consider restoring `OAUTH_REDIRECT_URL` secret support if needed
- Add comprehensive tests

---

## Reviewer Notes

The intent to simplify the function is good, but the implementation has created a critical architectural issue:

1. **Code Duplication:** The duplicate function in `credify_app.py` shadows the import and uses different logic. This violates DRY and creates maintenance burden.

2. **Inconsistent Behavior:** Google OAuth and Instagram OAuth will use different redirect URL logic, which may cause configuration issues and confusion.

3. **Missing Feature:** The removal of `OAUTH_REDIRECT_URL` secret support may break existing configurations, especially since it's still present in `secrets.toml`.

**Recommendation:** 
1. Remove the duplicate function from `credify_app.py`
2. Decide on the desired behavior (with or without `OAUTH_REDIRECT_URL` secret support)
3. Implement unified logic in `auth.py`
4. Test all OAuth flows thoroughly
5. Only then merge the changes

The simplification is good, but these blockers must be fixed first to maintain code quality and consistency.

---

## Comparison with Previous Implementation

### What Was Removed
- `OAUTH_REDIRECT_URL` secret check (was highest priority)
- Extensive debug mode logging with sidebar output
- Multiple environment variable fallback checks (`STREAMLIT_SERVER_URL`, `STREAMLIT_CLOUD_BASE_URL`, `PRODUCTION_URL`, `BASE_URL`)
- `HOSTNAME` with "streamlit.app" domain check
- Detailed error reporting and diagnostics

### What Was Added
- Simpler environment detection logic
- Conditional debug logging in `show_login()` function
- Cleaner code structure

### What Stayed the Same
- Basic `STREAMLIT_SHARING_BASE_URL` check
- Localhost detection with `STREAMLIT_SERVER_PORT`
- URL sanitization with `.rstrip("/")`
- Default to localhost behavior
