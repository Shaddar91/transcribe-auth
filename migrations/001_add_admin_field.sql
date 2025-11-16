-- Migration: Add is_admin field to users table
-- Description: Adds admin role support to the authentication system
-- Date: 2025-11-13
-- Agent: database-specialist

-- Check if column exists before adding
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'is_admin'
    ) THEN
        ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT false NOT NULL;
        RAISE NOTICE 'Added is_admin column to users table';
    ELSE
        RAISE NOTICE 'Column is_admin already exists in users table';
    END IF;
END $$;

-- Create index on is_admin for efficient admin queries
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
