-- Create the images table first
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_path TEXT NOT NULL,
    thumbnail_path TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Create the image_metadata table
CREATE TABLE IF NOT EXISTS image_metadata (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    description TEXT,
    tags TEXT[],
    colors VARCHAR(7)[],
    ai_processing_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE images ENABLE ROW LEVEL SECURITY;
ALTER TABLE image_metadata ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (to avoid conflicts)
DROP POLICY IF EXISTS "Users can only see own images" ON images;
DROP POLICY IF EXISTS "Users can insert own images" ON images;
DROP POLICY IF EXISTS "Users can update own images" ON images;
DROP POLICY IF EXISTS "Users can delete own images" ON images;

DROP POLICY IF EXISTS "Users can only see own metadata" ON image_metadata;
DROP POLICY IF EXISTS "Users can insert own metadata" ON image_metadata;
DROP POLICY IF EXISTS "Users can update own metadata" ON image_metadata;
DROP POLICY IF EXISTS "Users can delete own metadata" ON image_metadata;

-- RLS Policies for images table
CREATE POLICY "Users can only see own images" ON images
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own images" ON images
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own images" ON images
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own images" ON images
    FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for image_metadata table
CREATE POLICY "Users can only see own metadata" ON image_metadata
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own metadata" ON image_metadata
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own metadata" ON image_metadata
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own metadata" ON image_metadata
    FOR DELETE USING (auth.uid() = user_id);

-- Drop existing indexes if they exist
DROP INDEX IF EXISTS idx_image_metadata_tags;
DROP INDEX IF EXISTS idx_image_metadata_description;
DROP INDEX IF EXISTS idx_image_metadata_colors;
DROP INDEX IF EXISTS idx_images_user_id;
DROP INDEX IF EXISTS idx_image_metadata_user_id;

-- Add indexes for better search performance
CREATE INDEX idx_image_metadata_tags ON image_metadata USING GIN(tags);
CREATE INDEX idx_image_metadata_description ON image_metadata USING GIN(to_tsvector('english', description));
CREATE INDEX idx_image_metadata_colors ON image_metadata USING GIN(colors);
CREATE INDEX idx_images_user_id ON images(user_id);
CREATE INDEX idx_image_metadata_user_id ON image_metadata(user_id);

-- Drop existing function if it exists
DROP FUNCTION IF EXISTS search_images(TEXT, UUID);

-- Add full-text search function
CREATE OR REPLACE FUNCTION search_images(search_term TEXT, user_uuid UUID)
RETURNS TABLE (
    image_id INTEGER,
    filename VARCHAR(255),
    original_path TEXT,
    thumbnail_path TEXT,
    description TEXT,
    tags TEXT[],
    colors VARCHAR(7)[],
    uploaded_at TIMESTAMP,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.id,
        i.filename,
        i.original_path,
        i.thumbnail_path,
        m.description,
        m.tags,
        m.colors,
        i.uploaded_at,
        ts_rank(
            to_tsvector('english', COALESCE(m.description, '') || ' ' || COALESCE(array_to_string(m.tags, ' '), '')), 
            plainto_tsquery('english', search_term)
        ) as rank
    FROM images i
    JOIN image_metadata m ON i.id = m.image_id
    WHERE i.user_id = user_uuid 
    AND (
        to_tsvector('english', COALESCE(m.description, '') || ' ' || COALESCE(array_to_string(m.tags, ' '), '')) @@ plainto_tsquery('english', search_term)
        OR m.tags && string_to_array(search_term, ' ')
    )
    ORDER BY rank DESC, i.uploaded_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
