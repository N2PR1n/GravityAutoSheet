from services.openai_service import OpenAIService
import os
from dotenv import load_dotenv

def test_openai_integration():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or "YOUR_OPENAI_KEY" in api_key:
        print("SKIPPING TEST: OPENAI_API_KEY not set in .env")
        return

    service = OpenAIService(api_key)
    
    # Use a dummy image (re-use stitched image from previous test if exists, or create one)
    test_image = "test_stitched.jpg"
    if not os.path.exists(test_image):
        print(f"Test image {test_image} not found. Run test_stitching.py first.")
        return

    print(f"Sending {test_image} to OpenAI...")
    try:
        data = service.extract_data_from_image(test_image)
        print("Response from OpenAI:")
        print(data)
        
        if data and isinstance(data, dict):
            print("PASS: Received valid JSON response.")
        else:
            print("FAIL: Invalid response format.")
            
    except Exception as e:
        print(f"FAIL: Error calling OpenAI: {e}")

if __name__ == "__main__":
    test_openai_integration()
