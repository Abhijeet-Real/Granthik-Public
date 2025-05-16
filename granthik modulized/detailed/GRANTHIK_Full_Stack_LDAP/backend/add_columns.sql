-- Add chunk_size column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='chunk_size') THEN
        ALTER TABLE documents ADD COLUMN chunk_size INTEGER DEFAULT 1000;
    END IF;
END $$;

-- Add chunk_overlap column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='chunk_overlap') THEN
        ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER DEFAULT 200;
    END IF;
END $$;