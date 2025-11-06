# Facebook OAuth Redirect URI Setup

## Error: "URL blocked" / "Redirect URI not whitelisted"

This error occurs when the redirect URI used in the OAuth flow doesn't match what's configured in your Facebook App settings.

## Quick Fix

### Step 1: Find Your Redirect URI

The redirect URI depends on where you're running the app:

**Local Development:**
```
http://localhost:8501
```

**Streamlit Cloud Production:**
```
https://your-app-name.streamlit.app
```
(Replace `your-app-name` with your actual Streamlit Cloud app name)

### Step 2: Add to Facebook App Settings

1. Go to [Facebook Developers](https://developers.facebook.com/apps/)
2. Select your app
3. Go to **Settings → Basic**
4. Scroll down to **"Valid OAuth Redirect URIs"**
5. Click **"Add URI"**
6. Add **both**:
   - `http://localhost:8501` (for local testing)
   - `https://your-app-name.streamlit.app` (for production)
7. Click **Save Changes**

### Step 3: Verify OAuth Settings

In the same **Settings → Basic** page, ensure:
- ✅ **Client OAuth Login** is **Enabled**
- ✅ **Web OAuth Login** is **Enabled**

### Step 4: Check App Domains

Also add your domain to **App Domains**:
- For local: Leave empty or add `localhost`
- For production: Add `streamlit.app` (or your custom domain)

## Debug: Check What Redirect URI Is Being Used

Add this to your `.streamlit/secrets.toml` temporarily:

```toml
DEBUG_REDIRECT = "true"
```

Then run the app and check the sidebar - it will show what redirect URI is being detected.

## Common Issues

### Issue 1: Trailing Slash
- ❌ Wrong: `http://localhost:8501/`
- ✅ Correct: `http://localhost:8501`

### Issue 2: HTTP vs HTTPS
- Make sure you use `http://` for localhost
- Make sure you use `https://` for production

### Issue 3: Port Number
- Default Streamlit port is `8501`
- If you're using a different port, update both the code and Facebook settings

### Issue 4: Query Parameters
The redirect URI in Facebook should be the **base URL only**, without query parameters:
- ❌ Wrong: `http://localhost:8501?state=instagram_connect`
- ✅ Correct: `http://localhost:8501`

The `?state=instagram_connect` parameter is added by the code automatically.

## Testing

After adding the redirect URI:

1. **Wait 1-2 minutes** for Facebook to propagate the changes
2. **Clear your browser cache** or use incognito mode
3. Try connecting Instagram again

## Still Not Working?

1. **Check the exact error message** - it sometimes shows the URI that failed
2. **Verify in Facebook App Dashboard**:
   - Settings → Basic → Valid OAuth Redirect URIs
   - Make sure the URI matches **exactly** (case-sensitive, no trailing slash)
3. **Check App Status**:
   - Make sure your app is not in "Development Mode" if you need public access
   - Or add yourself as a test user if in Development Mode

## Example Configuration

**For Local Development:**
```
Valid OAuth Redirect URIs:
- http://localhost:8501
```

**For Production:**
```
Valid OAuth Redirect URIs:
- http://localhost:8501
- https://credify-app.streamlit.app
```

**App Domains:**
```
streamlit.app
```

