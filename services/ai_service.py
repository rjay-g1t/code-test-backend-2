import openai
import os
import base64
from typing import Dict, List
from models.schemas import AIAnalysisResult
from dotenv import load_dotenv

load_dotenv()

class AIService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def analyze_image(self, image_path: str) -> Dict:
        """Analyze image using OpenAI Vision API"""
        try:
            # Read and encode image
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Updated to current model
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this image and provide:
1. A single descriptive sentence about what you see
2. 5-10 relevant tags/keywords (single words, comma-separated)

Format your response as JSON:
{
  "description": "A single sentence describing the image",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64," + base64_image
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            # Parse response
            content = response.choices[0].message.content
            import json
            
            # Try to extract JSON from response
            try:
                # Find JSON in the response
                start = content.find('{')
                end = content.rfind('}') + 1
                json_str = content[start:end]
                result = json.loads(json_str)
                
                return {
                    "description": result.get("description", "An image"),
                    "tags": result.get("tags", [])
                }
            except:
                # Fallback parsing
                lines = content.strip().split('\n')
                description = "An interesting image"
                tags = ["image", "photo"]
                
                for line in lines:
                    if "description" in line.lower():
                        description = line.split(':', 1)[-1].strip().strip('"')
                    elif "tags" in line.lower() or "keywords" in line.lower():
                        tag_part = line.split(':', 1)[-1].strip()
                        tags = [tag.strip().strip('"') for tag in tag_part.split(',')]
                
                return {
                    "description": description,
                    "tags": tags[:10]  # Limit to 10 tags
                }
        
        except Exception as e:
            print("AI analysis error: " + str(e))
            # Return default values on error
            return {
                "description": "An image that couldn't be analyzed",
                "tags": ["image", "photo", "unknown"]
            }
