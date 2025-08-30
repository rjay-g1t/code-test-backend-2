-- Enable Row Level Security
ALTER TABLE images ENABLE ROW LEVEL SECURITY;
ALTER TABLE image_metadata ENABLE ROW LEVEL SECURITY;

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

-- Add indexes for better search performance
CREATE INDEX idx_image_metadata_tags ON image_metadata USING GIN(tags);
CREATE INDEX idx_image_metadata_description ON image_metadata USING GIN(to_tsvector('english', description));
CREATE INDEX idx_image_metadata_colors ON image_metadata USING GIN(colors);
CREATE INDEX idx_images_user_id ON images(user_id);
CREATE INDEX idx_image_metadata_user_id ON image_metadata(user_id);

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
        ts_rank(to_tsvector('english', m.description || ' ' || array_to_string(m.tags, ' ')), plainto_tsquery('english', search_term)) as rank
    FROM images i
    JOIN image_metadata m ON i.id = m.image_id
    WHERE i.user_id = user_uuid 
    AND (
        to_tsvector('english', m.description || ' ' || array_to_string(m.tags, ' ')) @@ plainto_tsquery('english', search_term)
        OR m.tags && string_to_array(search_term, ' ')
    )
    ORDER BY rank DESC, i.uploaded_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
