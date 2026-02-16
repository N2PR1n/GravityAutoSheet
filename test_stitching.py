from services.image_service import ImageService
from PIL import Image, ImageDraw

def create_dummy_image(filename, color, text):
    img = Image.new('RGB', (300, 500), color=color)
    d = ImageDraw.Draw(img)
    d.text((10,10), text, fill=(255,255,255))
    img.save(filename)
    return filename

def test_stitching():
    service = ImageService()
    
    # Create dummy images
    img1 = create_dummy_image("test_img1.jpg", "red", "Receipt Part 1")
    img2 = create_dummy_image("test_img2.jpg", "blue", "Receipt Part 2")
    
    print("Created dummy images.")
    
    # Stitch
    output = "test_stitched.jpg"
    service.stitch_images("test_img1.jpg", "test_img2.jpg", output)
    
    print(f"Stitched image saved to {output}")
    
    # Verify dimensions
    stitched = Image.open(output)
    print(f"Stitched size: {stitched.size}")
    
    # Expected: 300+300 width = 600, height 500
    if stitched.size == (600, 500):
        print("PASS: Dimensions correct.")
    else:
        print(f"FAIL: Expected (600, 500), got {stitched.size}")

if __name__ == "__main__":
    test_stitching()
