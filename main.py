import os
import sys
import asyncio
from fastapi import FastAPI, Request, HTTPException

# LINE SDK v3 Imports
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)

from dotenv import load_dotenv

# Import Services
from services.image_service import ImageService
from services.drive_service import DriveService
from services.openai_service import OpenAIService
from services.sheet_service import SheetService
from services.accounting_service import AccountingService

# Load environment variables
load_dotenv()

app = FastAPI()

# Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Resolve absolute path for credentials
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
credentials_filename = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if credentials_filename and not os.path.isabs(credentials_filename):
    GOOGLE_CREDENTIALS_PATH = os.path.join(BASE_DIR, credentials_filename)
else:
    GOOGLE_CREDENTIALS_PATH = credentials_filename

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

import certifi
import ssl

# Initialize Services
# Configure SSL context with certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
# Pass ssl_context if supported, or rely on certifi being global?
# ApiClient in v3 usually uses urllib3.
# The issue is urllib3 not finding certs.
# We can try to set SSL_CERT_FILE env var or configure ApiClient.
# Let's try setting environment variable first which is safer.
os.environ['SSL_CERT_FILE'] = certifi.where()

api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

image_service = ImageService()
drive_service = DriveService(GOOGLE_CREDENTIALS_PATH)
openai_service = OpenAIService(OPENAI_API_KEY)
sheet_service = SheetService(GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)
accounting_service = AccountingService(sheet_service, drive_service)

# User State for Multi-Image Handling
# user_id: {'images': [msg_id1, msg_id2], 'timer': asyncio.Task, 'reply_token': str}
user_states = {}

@app.get("/")
async def root():
    return {"status": "ok", "message": "LINE Order Bot is running (SDK v3 + OpenAI + Accounting Export)."}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get('X-Line-Signature')
    body = await request.body()
    body_decoded = body.decode('utf-8')
    
    try:
        handler.handle(body_decoded, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text.lower()
    user_id = event.source.user_id
    reply_token = event.reply_token

    if text in ["export", "ขอไฟล์เบิกเงิน", "ทำบัญชี"]:
        try:
             # Notify processing
            messaging_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text="📊 กำลังสร้างไฟล์เบิกเงินและส่งเข้า Drive... รอสักครู่ครับ")]
                )
            )
            
            # Run export in background (it might take time)
            import threading
            def run_export():
                try:
                    link = accounting_service.export_report(GOOGLE_DRIVE_FOLDER_ID)
                    if link:
                        messaging_api.push_message(
                            PushMessageRequest(
                                to=user_id,
                                messages=[TextMessage(text=f"✅ สร้างไฟล์เสร็จแล้วครับ!\nโหลดได้ที่นี่: {link}")]
                            )
                        )
                    else:
                        messaging_api.push_message(
                             PushMessageRequest(
                                 to=user_id,
                                 messages=[TextMessage(text="❌ ไม่พบข้อมูลใน Sheet หรือเกิดข้อผิดพลาดในการสร้างไฟล์")]
                             )
                         )
                except Exception as e:
                    print(f"Export Error: {e}")
                    messaging_api.push_message(
                             PushMessageRequest(
                                 to=user_id,
                                 messages=[TextMessage(text=f"เกิดข้อผิดพลาด: {str(e)}")]
                             )
                         )

            threading.Thread(target=run_export).start()
            
        except Exception as e:
            print(f"Text Handle Error: {e}")

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    user_id = event.source.user_id
    message_id = event.message.id
    reply_token = event.reply_token

    if user_id not in user_states:
        user_states[user_id] = {'images': [], 'timer': None, 'reply_token': reply_token}
    
    # Update reply token to the latest one
    user_states[user_id]['reply_token'] = reply_token
    
    # Cancel existing timer
    if user_states[user_id]['timer']:
        user_states[user_id]['timer'].cancel()
        
    user_states[user_id]['images'].append(message_id)
    
    # Start new timer (wait 2 seconds for more images)
    user_states[user_id]['timer'] = asyncio.create_task(process_images_after_delay(user_id))

async def process_images_after_delay(user_id):
    await asyncio.sleep(2.0) # Wait 2s
    
    if user_id not in user_states: return

    state = user_states.pop(user_id)
    image_ids = state['images']
    reply_token = state['reply_token']

    try:
        # Notify user processing started
        try:
            # v3 Reply Message
            messaging_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text=f"ได้รับ {len(image_ids)} รูปภาพ กำลังประมวลผล (OpenAI/v3)...")]
                )
            )
        except Exception as e:
            print(f"Reply token likely expired or invalid: {e}")

        # 1. Download Images (Need to wrap synchronous download in executor or assume fast enough)
        # Using run_in_executor to avoid blocking the event loop for network IO
        loop = asyncio.get_event_loop()
        headers = {'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
        downloaded_paths = []
        
        for msg_id in image_ids:
            # Note: image_service.download_image is sync
            path = await loop.run_in_executor(None, image_service.download_image, msg_id, headers)
            downloaded_paths.append(path)
        
        # 2. Stitch if needed
        final_image_path = downloaded_paths[0]
        if len(downloaded_paths) >= 2:
            final_image_path = f"temp_images/stitched_{image_ids[0]}.jpg"
            await loop.run_in_executor(None, image_service.stitch_images, downloaded_paths[0], downloaded_paths[1], final_image_path)
            print("Stitched images.")

        # 3. Extract Data with OpenAI
        print("Extracting data with OpenAI...")
        data = await loop.run_in_executor(None, openai_service.extract_data_from_image, final_image_path)
        
        if not data:
             # v3 Push Message error
             messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"❌ AI (OpenAI) อ่านข้อมูลไม่ได้ครับ")]
                 )
             )
             return

        print(f"Extracted Data: (Before Upload) {data}")

        # 4. Check for Duplicates
        is_duplicate = await loop.run_in_executor(None, sheet_service.check_duplicate, data.get('order_id'))
        if is_duplicate:
            print(f"Duplicate Order ID found: {data.get('order_id')}")
            messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"⚠️ Order {data.get('order_id')} ซ้ำครับ! เคยบันทึกไปแล้ว (ไม่บันทึกรูป)")]
                 )
             )
            return

        # 5. Upload to Drive (Only if not duplicate)
        print("Uploading to Drive...")
        
        # Get Next Run No for Filename
        next_run_no = await loop.run_in_executor(None, sheet_service.get_next_run_no)
        print(f"Next Run No: {next_run_no}")

        drive_link = ""
        try:
            # Use Run No as filename (e.g., "5.jpg")
            target_filename = f"{next_run_no}.jpg"
            drive_file = await loop.run_in_executor(None, drive_service.upload_file, final_image_path, GOOGLE_DRIVE_FOLDER_ID, target_filename)
             
            if drive_file:
                drive_link = drive_file.get('webViewLink', '')
                print(f"Uploaded: {drive_link}")
        except Exception as e:
            print(f"Drive Upload Failed (Non-critical): {e}")

        # Inject Drive Link
        data['image_link'] = drive_link
        
        # 6. Save to Sheets
        print("Saving to Sheets...")
        success = await loop.run_in_executor(None, sheet_service.append_data, data, next_run_no)
        
        if not success:
             messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"❌ บันทึกไม่สำเร็จ! (Sheet Error)\nโปรดตรวจสอบว่า Share Sheet ให้กับ Email Bot หรือยัง?\n(linebotgravity@gravitybotproject.iam.gserviceaccount.com)")]
                 )
             )
        else:
            # 6. Notify Success
            tracking_info = f"\nTracking: {data.get('tracking_number')}" if data.get('tracking_number') and data.get('tracking_number') != '-' else ""
            
            summary = (
                f"✅ บันทึกแล้ว! (No. {next_run_no})\n"
                f"ชื่อ: {data.get('receiver_name', '-')}\n"
                f"ที่อยู่: {data.get('location', '-')}\n"
                f"ร้าน: {data.get('shop_name', '-')}\n"
                f"ยอด: {data.get('price', '-')}\n"
                f"เหรียญ: {data.get('coins', '-')}\n"
                f"Platform: {data.get('platform', '-')}\n"
                f"Order: {data.get('order_id', '-')}"
                f"{tracking_info}"
            )
            messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=summary)]
                 )
             )

    except Exception as e:
        print(f"Error processing: {e}")
        import traceback
        traceback.print_exc()
        try:
            messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"เกิดข้อผิดพลาด: {str(e)}")]
                 )
             )
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
