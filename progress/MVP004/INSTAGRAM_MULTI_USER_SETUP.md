# Instagram Multi-User Setup Guide

## Overview

The Instagram integration now supports **multi-user authentication**. Each user can connect their own Instagram Business account and see only their own insights, not a shared account.

## Architecture Changes

### Before (Single User)
- Instagram tokens stored in `.streamlit/secrets.toml`
- All users saw the same account's data
- Not scalable

### After (Multi-User)
- Instagram tokens stored in `user_tokens` table (per user)
- Each user connects their own account via OAuth
- Users see only their own insights
- Production-ready and scalable

## Setup Instructions

### 1. Facebook App Configuration

1. **Create Facebook App**
   - Go to [Facebook Developers](https://developers.facebook.com/apps/)
   - Click "Create App"
   - Choose "Business" type
   - Fill in app details

2. **Add Instagram Graph API Product**
   - In your app dashboard, go to "Add Products"
   - Add "Instagram Graph API"
   - Follow setup wizard

3. **Configure OAuth Settings** ⚠️ **CRITICAL STEP**
   - Go to **Settings → Basic**
   - Scroll down to **"Valid OAuth Redirect URIs"**
   - Click **"Add URI"**
   - Add **both**:
     - Local: `http://localhost:8501` (no trailing slash)
     - Production: `https://your-app.streamlit.app` (your actual Streamlit Cloud URL)
   - **Important**: The URI must match **exactly** - no trailing slash, correct protocol (http for local, https for production)
   - Also ensure:
     - ✅ **Client OAuth Login** is **Enabled**
     - ✅ **Web OAuth Login** is **Enabled**
   - Save changes
   
   **💡 Tip**: The Settings page shows the exact redirect URI being used in an expandable section. Use that exact value!

4. **Get App Credentials**
   - **App ID**: Found in Settings → Basic
   - **App Secret**: Found in Settings → Basic (click "Show")

### 2. Add to Secrets

Add to `.streamlit/secrets.toml`:

```toml
FACEBOOK_APP_ID = "your_facebook_app_id"
FACEBOOK_APP_SECRET = "your_facebook_app_secret"
```

**Note**: The old `IG_LONG_TOKEN` and `IG_ACCOUNT_ID` are now deprecated. They're kept for backward compatibility but won't be used in production.

### 3. Database Setup

Ensure `user_tokens` table exists (from your schema):

```sql
CREATE TABLE IF NOT EXISTS user_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    u_id UUID REFERENCES users(u_id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'instagram', 'tiktok', 'vimeo')),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    account_id TEXT,
    account_username TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (u_id, platform)
);
```

### 4. User Flow

1. **User logs in** to Credify (existing auth)
2. **Goes to Settings → Connections**
3. **Clicks "Connect Instagram"**
4. **Authorizes** via Facebook OAuth
5. **Token stored** in `user_tokens` table
6. **Can view insights** for their account only

## How It Works

### OAuth Flow

```
1. User clicks "Connect Instagram"
   ↓
2. Redirected to Facebook OAuth
   ↓
3. User authorizes app
   ↓
4. Redirected back with code
   ↓
5. Exchange code for short-lived token
   ↓
6. Exchange for long-lived token (60 days)
   ↓
7. Get Instagram Business Account ID
   ↓
8. Store in user_tokens table
```

### Token Storage

Tokens are stored in `user_tokens` table:
- `u_id`: Links to user
- `platform`: "instagram"
- `access_token`: Long-lived token
- `account_id`: Instagram Business Account ID
- `expires_at`: Token expiry timestamp

### Data Fetching

When fetching insights:
1. Get user's token from `user_tokens` table
2. Use that token to fetch their account's insights
3. Store insights with `u_id` and `account_id`
4. Display only that user's data

## Migration from Single-User

### For Existing Users

If you have existing data from the single-account setup:

1. **Option 1**: Keep legacy data, new users use OAuth
   - Old data remains in `instagram_insights` with `u_id = NULL` or shared `u_id`
   - New users connect via OAuth and get their own data

2. **Option 2**: Migrate existing data
   - Assign existing insights to specific users
   - Update `u_id` and `account_id` in `instagram_insights` table

### For Development

During development, you can still use secrets for testing:

```toml
# For testing only - not used in production
IG_LONG_TOKEN = "test_token"
IG_ACCOUNT_ID = "test_account_id"
```

But the app will prioritize per-user tokens from the database.

## Troubleshooting

### "Facebook App credentials not configured"
- Ensure `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` are in secrets
- Verify App ID and Secret are correct

### "Could not find Instagram Business Account"
- User's Facebook Page must have an Instagram Business account connected
- Go to Facebook Page → Settings → Instagram to connect

### "OAuth redirect URI mismatch"
- Ensure redirect URI in Facebook App matches exactly
- Check both local and production URLs are added

### "Token has expired"
- Long-lived tokens expire after 60 days
- User needs to reconnect in Settings → Connections
- Future: Automatic token refresh (coming soon)

## Security Notes

- **Tokens stored securely** in Supabase with RLS policies
- **Users can only access** their own tokens
- **OAuth flow** uses secure HTTPS redirects
- **App Secret** should never be exposed to frontend

## Next Steps

- [ ] Set up Facebook App
- [ ] Add credentials to secrets
- [ ] Test OAuth flow with one user
- [ ] Verify insights fetch correctly
- [ ] Test with multiple users
- [ ] Remove legacy secrets (optional)

## API Permissions Required

The OAuth flow requests these permissions:
- `instagram_basic`: Basic Instagram account info
- `instagram_manage_insights`: Access to insights/metrics
- `pages_read_engagement`: Read page engagement data
- `pages_show_list`: List connected Facebook Pages

These are automatically requested during OAuth authorization.

