-- Add profile_image_url column to users table
-- This allows users to store a public image URL for their profile picture

ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_url TEXT;

-- Add a comment to document the column
COMMENT ON COLUMN users.profile_image_url IS 'Public URL to user profile image';

