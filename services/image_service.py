import os
from PIL import Image
import requests
from io import BytesIO

class ImageService:
    def __init__(self):
        # Use absolute path for temp directory
        self.temp_dir = os.path.join(os.getcwd(), "temp_images")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)

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
        """Stitches two images together side-by-side (horizontal).
           Optimized: Resizes to a reasonable height first to save memory.
        """
        try:
            img1 = Image.open(image_path1)
            img2 = Image.open(image_path2)

            # Target height for processing (e.g., 2000px is enough for OCR)
            max_h = 2000
            
            # Resize img1
            w1, h1 = img1.size
            if h1 > max_h:
                new_w1 = int(w1 * (max_h / h1))
                img1 = img1.resize((new_w1, max_h), Image.LANCZOS)
                w1, h1 = new_w1, max_h
            
            # Resize img2 to match img1 height
            w2, h2 = img2.size
            if h2 != h1:
                new_w2 = int(w2 * (h1 / h2))
                img2 = img2.resize((new_w2, h1), Image.LANCZOS)
                w2, h2 = new_w2, h1
            
            # Create new blank image
            total_width = w1 + w2
            new_im = Image.new('RGB', (total_width, h1))
            
            # Paste
            new_im.paste(img1, (0, 0))
            new_im.paste(img2, (w1, 0))
            
            # Save with optimization
            new_im.save(output_path, "JPEG", quality=85, optimize=True)
            return output_path
        except Exception as e:
            print(f"DEBUG: Stitch Error: {e}")
            # Fallback: copy first image instead of failing completely if stitch fails
            import shutil
            shutil.copy2(image_path1, output_path)
            return output_path
