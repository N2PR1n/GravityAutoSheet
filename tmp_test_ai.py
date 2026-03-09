import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.config_service import ConfigService
from services.ai_factory import AIFactory

cfg = ConfigService()
ai_provider = cfg.get('AI_PROVIDER', 'openai')

gemini_key = os.getenv('GEMINI_API_KEY')
openai_key = os.getenv('OPENAI_API_KEY')

ai_service = AIFactory.get_service(ai_provider, openai_key, gemini_key)

print(f"Using AI Provider: {ai_provider.upper()} ({ai_service.__class__.__name__})")

# use the two latest images which are from the second prompt
images = [
    "/Users/rin_macboook/.gemini/antigravity/brain/9abe0c6d-4919-4833-8acc-6b4af8533542/media__1773048154488.png",
    "/Users/rin_macboook/.gemini/antigravity/brain/9abe0c6d-4919-4833-8acc-6b4af8533542/media__1773048158392.png"
]

import time
from services.image_service import ImageService
img_srv = ImageService()

final_image_path = os.path.join("temp_images", f"stitched_test.jpg")
os.makedirs("temp_images", exist_ok=True)
img_srv.stitch_images(images[0], images[1], final_image_path)
print(f"Stitched image saved to {final_image_path}")

data = ai_service.extract_data_from_image(final_image_path)

print("\n--- Extracted Data ---")
import json
print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n--- BOT REPLY PREVIEW ---")
tracking_info = f"\nTracking: {data.get('tracking_number')}" if data.get('tracking_number') and data.get('tracking_number') != '-' else ""
folder_info = f"\n📁 บันทึกรูปไปที่: Test Folder"
run_no = "2" # From user screenshot

summary = (
    f"✅ บันทึกแล้ว! (No. {run_no})\n"
    f"ชื่อ: {data.get('receiver_name', '-')}\n"
    f"ที่อยู่: {data.get('location', '-')}\n"
    f"ร้าน: {data.get('shop_name', '-')}\n"
    f"ยอด: {data.get('price', '-')}\n"
    f"เหรียญ: {data.get('coins', '0')}\n"
    f"Platform: {data.get('platform', '-')}\n"
    f"Order: {data.get('order_id', '-')}"
    f"{tracking_info}"
    f"{folder_info}"
)

print(summary)
