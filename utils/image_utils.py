from PIL import Image, ImageOps
import io
import asyncio
from typing import List
import colorsys
from collections import Counter

async def create_thumbnail(image_content: bytes, output_path: str, size: tuple = (300, 300)):
    """Create a thumbnail from image content"""
    def _create_thumb():
        image = Image.open(io.BytesIO(image_content))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create thumbnail maintaining aspect ratio
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Create a square thumbnail with padding
        thumbnail = Image.new('RGB', size, (255, 255, 255))
        
        # Calculate position to center the image
        x = (size[0] - image.width) // 2
        y = (size[1] - image.height) // 2
        
        thumbnail.paste(image, (x, y))
        thumbnail.save(output_path, 'JPEG', quality=85)
    
    # Run in thread to avoid blocking
    await asyncio.get_event_loop().run_in_executor(None, _create_thumb)

async def create_thumbnail_bytes(image_content: bytes, size: tuple = (300, 300)) -> bytes:
    """Create a thumbnail and return as bytes"""
    def _create_thumb():
        image = Image.open(io.BytesIO(image_content))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create thumbnail maintaining aspect ratio
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Create a square thumbnail with padding
        thumbnail = Image.new('RGB', size, (255, 255, 255))
        
        # Calculate position to center the image
        x = (size[0] - image.width) // 2
        y = (size[1] - image.height) // 2
        
        thumbnail.paste(image, (x, y))
        
        # Save to bytes
        output = io.BytesIO()
        thumbnail.save(output, 'JPEG', quality=85)
        return output.getvalue()
    
    # Run in thread to avoid blocking
    return await asyncio.get_event_loop().run_in_executor(None, _create_thumb)
    await asyncio.to_thread(_create_thumb)

async def extract_colors(image_path: str, num_colors: int = 3) -> List[str]:
    """Extract dominant colors from image"""
    def _extract():
        try:
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize for faster processing
            image = image.resize((150, 150))
            
            # Get all pixels
            pixels = list(image.getdata())
            
            # Count color frequency
            color_counts = Counter(pixels)
            
            # Get most common colors
            most_common = color_counts.most_common(num_colors * 3)  # Get more to filter
            
            colors = []
            for color, count in most_common:
                # Skip very dark or very light colors
                brightness = sum(color) / 3
                if 30 < brightness < 220:
                    # Convert to hex
                    hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                    colors.append(hex_color)
                    
                    if len(colors) >= num_colors:
                        break
            
            # If we don't have enough colors, add some defaults
            while len(colors) < num_colors:
                if len(colors) == 0:
                    colors.append('#808080')  # Gray
                elif len(colors) == 1:
                    colors.append('#FFFFFF')  # White
                else:
                    colors.append('#000000')  # Black
            
            return colors[:num_colors]
            
        except Exception as e:
            print("Color extraction error: " + str(e))
            return ['#808080', '#FFFFFF', '#000000']  # Default colors
    
    return await asyncio.to_thread(_extract)
