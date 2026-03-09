import json
import google.generativeai as genai
from PIL import Image
from .ai_base_service import AIBaseService

class GeminiService(AIBaseService):
    def __init__(self, api_key):
        super().__init__(api_key)
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-flash-latest')
        # Debug: confirm model name
        print(f"DEBUG: Gemini initialized with model: gemini-flash-latest")

    def extract_data_from_image(self, image_path):
        """
        Sends image to Gemini 1.5 Flash and extracts data as JSON.
        """
        prompt = self.get_prompt()
        
        try:
            # Open image using PIL
            img = Image.open(image_path)
            
            # Call Gemini
            # Gemini 1.5 Flash supports image objects directly
            response = self.model.generate_content([prompt, img])
            
            text = response.text.strip()
            
            # Clean up response text to ensure it's valid JSON
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            data = json.loads(text.strip())
            if data and 'shop_name' in data:
                data['shop_name'] = self.map_shop_name(data['shop_name'])
            return data
            
        except Exception as e:
            print(f"Error calling Gemini: {e}")
            return None
