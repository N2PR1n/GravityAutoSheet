import os
from PIL import Image
import requests
from io import BytesIO

class ImageService:
    def __init__(self):
        self.temp_dir = "temp_images"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def download_image(self, message_id, headers):
        """Downloads image from LINE server."""
        url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
        response = requests.get(url, headers=headers, stream=True)
        
        if response.status_code == 200:
            file_path = os.path.join(self.temp_dir, f"{message_id}.jpg")
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return file_path
        else:
            raise Exception(f"Failed to download image: {response.status_code}")

    def stitch_images(self, image_path1, image_path2, output_path):
        """Stitches two images together side-by-side (horizontal) or top-down (vertical).
           Decides based on aspect ratio or fixed strategy.
        """
        img1 = Image.open(image_path1)
        img2 = Image.open(image_path2)

        # Basic stitching strategy: Horizontal if both are tall, Vertical if both are wide?
        # For receipts, usually they are tall. Let's try stitching them side-by-side first as requested ("เย็บติดกัน (ซ้ายขวา)")
        
        # Resize text to match height
        # Get dimensions
        w1, h1 = img1.size
        w2, h2 = img2.size
        
        # Target height = max(h1, h2)
        target_h = max(h1, h2)
        
        # Resize maintaining aspect ratio
        # img1
        new_w1 = int(w1 * (target_h / h1))
        img1_resized = img1.resize((new_w1, target_h))
        
        # img2
        new_w2 = int(w2 * (target_h / h2))
        img2_resized = img2.resize((new_w2, target_h))
        
        # Create new blank image
        total_width = new_w1 + new_w2
        new_im = Image.new('RGB', (total_width, target_h))
        
        # Paste
        new_im.paste(img1_resized, (0, 0))
        new_im.paste(img2_resized, (new_w1, 0))
        
        # Save
        new_im.save(output_path)
        return output_path
