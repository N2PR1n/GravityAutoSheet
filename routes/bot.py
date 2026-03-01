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
    openai_service = OpenAIService(OPENAI_API_KEY)
    
    # Always check for the latest sheet name from config
    sheet_name = _config_service.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
    
    print(f"DEBUG: Bot connecting to Sheet: {sheet_name}")
    sheet_service = SheetService(creds, GOOGLE_SHEET_ID, sheet_name)
        
    accounting_service = AccountingService(sheet_service, drive_service)
    
    return image_service, drive_service, openai_service, sheet_service, accounting_service

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

    # Lazy Load Services
    image_service, drive_service, openai_service, sheet_service, _ = get_services()

    try:
        # Notify Start
        try:
            messaging_api.reply_message(
                ReplyMessageRequest(
                    replyToken=reply_token,
                    messages=[TextMessage(text=f"ได้รับ {len(image_ids)} รูปภาพ กำลังประมวลผล (OpenAI/v3)...")]
                )
            )
        except Exception as e:
            print(f"Reply token expired? {e}")

        # 1. Download
        headers = {'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'}
        downloaded_paths = []
        for msg_id in image_ids:
            path = image_service.download_image(msg_id, headers)
            downloaded_paths.append(path)
        
        # 2. Stitch
        final_image_path = downloaded_paths[0]
        if len(downloaded_paths) >= 2:
            final_image_path = f"temp_images/stitched_{image_ids[0]}.jpg"
            image_service.stitch_images(downloaded_paths[0], downloaded_paths[1], final_image_path)
            print("Stitched images.")

        # 3. OpenAI
        print("Extracting data with OpenAI...")
        data = openai_service.extract_data_from_image(final_image_path)
        
        if not data:
             messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"❌ AI (OpenAI) อ่านข้อมูลไม่ได้ครับ")]
                 )
             )
             return

        # 4. Duplicate Check
        if sheet_service.check_duplicate(data.get('order_id')):
             messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"⚠️ Order {data.get('order_id')} ซ้ำครับ! (ไม่บันทึก)")]
                 )
             )
             return

        # 5. Upload to Drive
        next_run_no = sheet_service.get_next_run_no()
        target_filename = f"{next_run_no}.jpg"
        
        drive_link = ""
        drive_error = ""
        folder_display_name = "ไม่ทราบชื่อโฟลเดอร์"
        try:
            sheet_name = _config_service.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
            folder_id = _config_service.get_folder_for_sheet(sheet_name)
            folder_display_name = drive_service.get_folder_name(folder_id)
            print(f"DEBUG: Drive Upload -> Sheet: {sheet_name}, Folder: {folder_id} ({folder_display_name}), File: {target_filename}", flush=True)
            drive_file = drive_service.upload_file(final_image_path, folder_id, target_filename)
            if drive_file:
                drive_link = drive_file.get('webViewLink', '')
            else:
                drive_error = "Upload failed (Check Service Account access)"
        except Exception as e:
            print(f"Drive Upload Error: {e}")
            drive_error = str(e)

        data['image_link'] = drive_link

        # 6. Save to Sheet
        if sheet_service.append_data(data, next_run_no):
            # Invalidate Cache
            try:
                from app import order_cache
                order_cache['data'] = None
            except:
                pass
            
            # Success
            tracking_info = f"\nTracking: {data.get('tracking_number')}" if data.get('tracking_number') and data.get('tracking_number') != '-' else ""
            
            drive_status = f"\n📁 บันทึกรูปไปที่: {folder_display_name}" if drive_link else f"\n⚠️ **เซฟรูปลง Drive ไม่สำเร็จ!**\n(โฟลเดอร์: {folder_display_name})\nสาเหตุ: {drive_error}"
            
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
                f"{drive_status}"
            )
            messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=summary)]
                 )
             )
        else:
             messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"❌ บันทึก Sheet ไม่สำเร็จ")]
                 )
             )

    except Exception as e:
        print(f"Process Error: {e}")
        try:
            messaging_api.push_message(
                 PushMessageRequest(
                     to=user_id,
                     messages=[TextMessage(text=f"เกิดข้อผิดพลาด: {str(e)}")]
                 )
             )
        except:
            pass
