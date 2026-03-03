import json
from openai import OpenAI
from .ai_base_service import AIBaseService

class OpenAIService(AIBaseService):
    def __init__(self, api_key):
        super().__init__(api_key)
        self.client = OpenAI(api_key=api_key)

    def extract_data_from_image(self, image_path):
        """
        Sends image to OpenAI GPT-4o and extracts data as JSON.
        """
        base64_image = self.encode_image(image_path)
        prompt = self.get_prompt()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
            )
            
            content = response.choices[0].message.content
            
            # Clean up response text to ensure it's valid JSON
            text = content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
            
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            return None
