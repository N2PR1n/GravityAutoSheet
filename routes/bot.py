from flask import Blueprint, request, abort, current_app
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
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
import os
import threading
import time
import certifi
from services.image_service import ImageService
from services.drive_service import DriveService
from services.openai_service import OpenAIService
from services.sheet_service import SheetService
from services.accounting_service import AccountingService
from services.config_service import ConfigService

# Blueprint Setup
bot_bp = Blueprint('bot', __name__)

# Config
import json

# Config
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_CREDENTIALS_SOURCE = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

# Ensure certs
os.environ['SSL_CERT_FILE'] = certifi.where()

# Helper to load creds
def get_credentials():
    import services.auth_service as auth_service
    return auth_service.get_google_credentials()

# LINE SDK
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

_config_service = ConfigService()

def get_services():
    # Load Creds
    creds = get_credentials()
    
    # Init Services fresh per call for thread safety in background threads/timers
    image_service = ImageService()
    drive_service = DriveService(creds)
    
    # AI Service Factory
    from services.ai_factory import AIFactory
    ai_provider = _config_service.get('AI_PROVIDER', 'openai')
    
    gemini_key = os.getenv('GEMINI_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    ai_service = AIFactory.get_service(ai_provider, openai_key, gemini_key)
    
    # Always check for the latest sheet name from config
    sheet_name = _config_service.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
    
    print(f"DEBUG: Bot connecting to Sheet: {sheet_name} | AI: {ai_provider}")
    sheet_service = SheetService(creds, GOOGLE_SHEET_ID, sheet_name)
        
    accounting_service = AccountingService(sheet_service, drive_service)
    
    return image_service, drive_service, ai_service, sheet_service, accounting_service

# State for Image Batching
# user_id: {'images': [], 'timer': threading.Timer, 'reply_token': str}
user_states = {}
user_states_lock = threading.Lock()

@bot_bp.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature')

    # get request body as text
    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        current_app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text.lower()
    user_id = event.source.user_id
    reply_token = event.reply_token

    if text in ["export", "ขอไฟล์เบิกเงิน", "ทำบัญชี"]:
        try:
            # Lazy Load Services
            _, _, _, _, accounting_service = get_services()
            
            # Notify processing
            messaging_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text="📊 กำลังสร้างไฟล์เบิกเงินและส่งเข้า Drive... รอสักครู่ครับ")]
                )
            )
            
            # Run export in background thread
            def run_export():
                try:
                    sheet_name = _config_service.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
                    folder_id = _config_service.get_folder_for_sheet(sheet_name)
                    link = accounting_service.export_report(folder_id)
                    if link:
                        msg = f"✅ สร้างไฟล์เสร็จแล้วครับ!\nโหลดได้ที่นี่: {link}"
                    else:
                        msg = "❌ ไม่พบข้อมูลใน Sheet หรือเกิดข้อผิดพลาดในการสร้างไฟล์"
                    
                    messaging_api.push_message(
                        PushMessageRequest(
                            to=user_id,
                            messages=[TextMessage(text=msg)]
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

    elif text in ["status", "เช็คชีท", "ชีทไหน", "เช็ค"]:
        try:
            # Lazy Load Services
            _, drive_service, _, _, _ = get_services()
            
            sheet_name = _config_service.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
            folder_id = _config_service.get_folder_for_sheet(sheet_name)
            
            # Fetch Folder Info
            folder_name = drive_service.get_folder_name(folder_id)
            
            status_msg = (
                f"🤖 สถานะบอทปัจจุบัน:\n"
                f"📁 ชีทที่ใช้งาน: {sheet_name}\n"
                f"📂 โฟลเดอร์: {folder_name}\n"
                f"🆔 ID: {folder_id[:5]}...{folder_id[-5:]}\n\n"
                f"💡 หากต้องการเปลี่ยนชีท ให้ไปที่หน้าเว็บแล้วเลือกใหม่นะครับ"
            )
            
            messaging_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text=status_msg)]
                )
            )
        except Exception as e:
            print(f"Status Check Error: {e}")
            messaging_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text=f"เกิดข้อผิดพลาดในการเช็คสถานะ: {str(e)}")]
                )
            )

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    user_id = event.source.user_id
    message_id = event.message.id
    reply_token = event.reply_token

    with user_states_lock:
        if user_id not in user_states:
            user_states[user_id] = {'images': [], 'timer': None, 'reply_token': reply_token}
        
        # Update reply token
        user_states[user_id]['reply_token'] = reply_token
        
        # Add image
        user_states[user_id]['images'].append(message_id)
        
        # Cancel old timer
        if user_states[user_id]['timer']:
            user_states[user_id]['timer'].cancel()
        
        # Start new timer (2.0s)
        timer = threading.Timer(2.0, process_images_thread, args=[user_id])
        user_states[user_id]['timer'] = timer
        timer.start()

def process_images_thread(user_id):
    # Retrieve and clear state
    with user_states_lock:
        if user_id not in user_states:
            return
        state = user_states.pop(user_id)
    
    image_ids = state['images']
    reply_token = state['reply_token']

    # Initial Progress Notification
    # We cannot reply immediately if we want to reply at the end (can only reply once per token)
    # Since push messages quota is exhausted (429 Too Many Requests), we must omit the "processing" message
    # and use the reply_token ONLY for the final result.
    print(f"DEBUG: Processing {len(image_ids)} images for user {user_id}")

    final_messages = []

    try:
        # 1. Initialize Services inside try-block
        print("DEBUG: [1] Initializing services...", flush=True)
        image_service, drive_service, ai_service, sheet_service, _ = get_services()
        print("DEBUG: [2] Services initialized successfully", flush=True)
        
        # 2. Download Images
        print(f"DEBUG: [3] Downloading {len(image_ids)} images...", flush=True)
        headers = {'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
        downloaded_paths = []
        for msg_id in image_ids:
            path = image_service.download_image(msg_id, headers)
            if path:
                downloaded_paths.append(path)
        
        if not downloaded_paths:
            raise Exception("ดาวน์โหลดรูปภาพไม่สำเร็จ")
        print(f"DEBUG: [4] Downloaded {len(downloaded_paths)} images", flush=True)

        # 3. Stitch or Select Image
        final_image_path = downloaded_paths[0]
        if len(downloaded_paths) >= 2:
            print(f"DEBUG: [5] Stitching {len(downloaded_paths)} images...", flush=True)
            final_image_path = os.path.join("temp_images", f"stitched_{int(time.time())}_{user_id[:5]}.jpg")
            os.makedirs("temp_images", exist_ok=True)
            image_service.stitch_images(downloaded_paths[0], downloaded_paths[1], final_image_path)
            print("DEBUG: [6] Stitching complete", flush=True)
            
        # 4. AI Extraction
        print(f"DEBUG: [7] Extracting data with {ai_service.__class__.__name__}...", flush=True)
        data = ai_service.extract_data_from_image(final_image_path)
        print(f"DEBUG: [8] AI Extraction complete. Data: {data}", flush=True)
        
        if not data:
             raise Exception("AI ไม่สามารถสกัดข้อมูลจากรูปภาพได้")

        # 5. Duplicate Check
        order_id = data.get('order_id')
        if not order_id:
            raise Exception("ไม่พบเลขออเดอร์ในรูปภาพ")
            
        if sheet_service.check_duplicate(order_id):
             final_messages.append(TextMessage(text=f"⚠️ พบเลขออเดอร์ {order_id} ซ้ำในระบบแล้วค่ะ (ไม่บันทึก)"))
             
             # Send via reply_message
             messaging_api.reply_message(
                 ReplyMessageRequest(
                      replyToken=reply_token,
                      messages=final_messages
                 )
             )
             return

        # 6. Drive Upload
        next_run_no = sheet_service.get_next_run_no()
        target_filename = f"{next_run_no}.jpg"
        
        drive_link = ""
        try:
            sheet_name = cfg.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
            folder_id = cfg.get_folder_for_sheet(sheet_name)
            folder_display_name = drive_service.get_folder_name(folder_id)
            print(f"DEBUG: Uploading to Drive -> {target_filename} in {folder_display_name}")
            
            drive_file = drive_service.upload_file(final_image_path, folder_id, target_filename)
            if drive_file:
                drive_link = drive_file.get('webViewLink', '')
        except Exception as e:
            print(f"DEBUG: Drive Upload Error: {e}")
            # Don't fail the whole process if only upload fails
        
        data['image_link'] = drive_link

        # 7. Save to Sheet
        print(f"DEBUG: Saving to Sheet: {order_id}")
        if sheet_service.append_data(data, next_run_no):
            # Success Summary
            tracking_info = f"\nTracking: {data.get('tracking_number')}" if data.get('tracking_number') and data.get('tracking_number') != '-' else ""
            
            # Using the format requested by user
            folder_info = f"\n📁 บันทึกรูปไปที่: {folder_display_name}" if drive_link else "\n⚠️ บันทึกรูปไม่สำเร็จ โปรดตรวจสอบว่าแชร์โฟลเดอร์ให้ Bot Service Account หรือยัง"
            
            summary = (
                f"✅ บันทึกแล้ว! (No. {next_run_no})\n"
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
            final_messages.append(TextMessage(text=summary))
            
            # Send Final Result via Reply Message
            messaging_api.reply_message(
                 ReplyMessageRequest(
                      replyToken=reply_token,
                      messages=final_messages
                 )
             )
        else:
             raise Exception("ไม่สามารถบันทึกข้อมูลลง Google Sheet ได้")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ CRITICAL ERROR in process_images_thread: {e}\n{error_detail}")
        
        error_msg = f"❌ เกิดข้อผิดพลาดในการประมวลผล:\n{str(e)}"
        final_messages.append(TextMessage(text=error_msg))
        try:
            messaging_api.reply_message(
                 ReplyMessageRequest(
                      replyToken=reply_token,
                      messages=final_messages
                 )
             )
        except Exception as reply_err:
            print(f"DEBUG: Failed to send error message via reply: {reply_err}")
    finally:
        # Cleanup temp files
        try:
            if 'downloaded_paths' in locals():
                for p in downloaded_paths:
                    if os.path.exists(p): os.remove(p)
            if 'final_image_path' in locals() and final_image_path not in (downloaded_paths if 'downloaded_paths' in locals() else []):
                if os.path.exists(final_image_path): os.remove(final_image_path)
        except:
            pass
