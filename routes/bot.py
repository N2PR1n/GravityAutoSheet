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
print(f"DEBUG: Initializing LINE SDK (Token first 10 chars: {str(LINE_CHANNEL_ACCESS_TOKEN)[:10]})")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("WARNING: LINE Credentials missing from environment variables! Bot features will be disabled.")
    configuration = None
    api_client = None
    messaging_api = None
    handler = None
else:
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    api_client = ApiClient(configuration)
    messaging_api = MessagingApi(api_client)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    print("DEBUG: LINE SDK initialized successfully")



# Config Service Singleton
_config_service_instance = None
def get_config():
    global _config_service_instance
    if _config_service_instance is None:
        _config_service_instance = ConfigService()
    return _config_service_instance

class ServiceProvider:
    def __init__(self, creds=None):
        self._creds = creds
        self._image_service = None
        self._drive_service = None
        self._ai_service = None
        self._sheet_service = None
        self._accounting_service = None
        self._cfg = None

    @property
    def creds(self):
        if self._creds is None:
            self._creds = get_credentials()
        return self._creds

    @property
    def config(self):
        if self._cfg is None:
            self._cfg = get_config()
        return self._cfg

    @property
    def image_service(self):
        if self._image_service is None:
            self._image_service = ImageService()
        return self._image_service

    @property
    def drive_service(self):
        if self._drive_service is None:
            self._drive_service = DriveService(self.creds)
        return self._drive_service

    @property
    def ai_service(self):
        if self._ai_service is None:
            from services.ai_factory import AIFactory
            ai_provider = self.config.get('AI_PROVIDER', 'openai')
            gemini_key = os.getenv('GEMINI_API_KEY')
            openai_key = os.getenv('OPENAI_API_KEY')
            self._ai_service = AIFactory.get_service(ai_provider, openai_key, gemini_key)
        return self._ai_service

    @property
    def sheet_service(self):
        if self._sheet_service is None:
            sheet_name = self.config.get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
            print(f"DEBUG: Lazy connecting to Sheet: {sheet_name}")
            self._sheet_service = SheetService(self.creds, GOOGLE_SHEET_ID, sheet_name)
        return self._sheet_service

    @property
    def accounting_service(self):
        if self._accounting_service is None:
            self._accounting_service = AccountingService(self.sheet_service, self.drive_service)
        return self._accounting_service

def get_service_provider():
    return ServiceProvider()

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
        if handler:
            handler.handle(body, signature)
        else:
            current_app.logger.warning("Webhook received but handler is not initialized")
    except InvalidSignatureError:
        current_app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

if handler:
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event):
        text = event.message.text.lower()
        user_id = event.source.user_id
        reply_token = event.reply_token

        if text in ["export", "ขอไฟล์เบิกเงิน", "ทำบัญชี"]:
            try:
                # Lazy Load Services
                provider = get_service_provider()
                accounting_service = provider.accounting_service
                
                # Notify processing
                if messaging_api:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            replyToken=reply_token,
                            messages=[TextMessage(text="📊 กำลังสร้างไฟล์เบิกเงินและส่งเข้า Drive... รอสักครู่ครับ")]
                        )
                    )
                
                # Run export in background thread
                def run_export():
                    try:
                        sheet_name = get_config().get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
                        folder_id = get_config().get_folder_for_sheet(sheet_name)
                        link = accounting_service.export_report(folder_id)
                        if link:
                            msg = f"✅ สร้างไฟล์เสร็จแล้วครับ!\nโหลดได้ที่นี่: {link}"
                        else:
                            msg = "❌ ไม่พบข้อมูลใน Sheet หรือเกิดข้อผิดพลาดในการสร้างไฟล์"
                        
                        if messaging_api:
                            messaging_api.push_message(
                                PushMessageRequest(
                                    to=user_id,
                                    messages=[TextMessage(text=msg)]
                                )
                            )
                    except Exception as e:
                        print(f"Export Error: {e}")
                        if messaging_api:
                            messaging_api.push_message(
                                PushMessageRequest(
                                    to=user_id,
                                    messages=[TextMessage(text=f"เกิดข้อผิดพลาด: {str(e)}")]
                                )
                            )

                threading.Thread(target=run_export).start()
            except Exception as e:
                print(f"Text Handle Error: {e}")

        elif text in ["status", "เช็กชีท", "ชีทไหน", "เช็ก"]:
            try:
                # Lazy Load Services
                provider = get_service_provider()
                drive_service = provider.drive_service
                
                sheet_name = get_config().get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
                folder_id = get_config().get_folder_for_sheet(sheet_name)
                
                # Fetch Folder Info
                folder_name = drive_service.get_folder_name(folder_id)
                
                status_msg = (
                    f"🤖 สถานะบอทปัจจุบัน:\n"
                    f"📁 ชีทที่ใช้งาน: {sheet_name}\n"
                    f"📂 โฟลเดอร์: {folder_name}\n"
                    f"🆔 ID: {folder_id[:5]}...{folder_id[-5:]}\n\n"
                    f"💡 หากต้องการเปลี่ยนชีท ให้ไปที่หน้าเว็บแล้วเลือกใหม่นะครับ"
                )
                
                if messaging_api:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            replyToken=reply_token,
                            messages=[TextMessage(text=status_msg)]
                        )
                    )
            except Exception as e:
                print(f"Status Check Error: {e}")
                if messaging_api:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            replyToken=reply_token,
                            messages=[TextMessage(text=f"เกิดข้อผิดพลาดในการเช็คสถานะ: {str(e)}")]
                        )
                    )

if handler:
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
            
            # Start new timer (1.0s) — รอ batch รูปหลายรูป แต่ให้สั้นพอเพื่อ process ได้ทันใน 30 วินาที
            timer = threading.Timer(1.0, process_images_thread, args=[user_id])
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

    # ไม่ส่งข้อความ "กำลังประมวลผล" เพราะ reply token ใช้ได้แค่ครั้งเดียว
    # เก็บ token ไว้ใช้กับผลลัพธ์สุดท้าย (reply_message = ฟรี ไม่เสีย quota)
    print(f"DEBUG: Processing {len(image_ids)} image(s) for user {user_id}")

    final_messages = []

    try:
        # 1. Initialize Services inside try-block (Lazy)
        print("DEBUG: [1] Initializing service provider...", flush=True)
        provider = get_service_provider()
        image_service = provider.image_service
        drive_service = provider.drive_service
        ai_service = provider.ai_service
        sheet_service = provider.sheet_service
        print("DEBUG: [2] Service references obtained", flush=True)
        
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
            
        # 4. AI Extraction (with auto-retry if failed)
        print(f"DEBUG: [7] Extracting data with {ai_service.__class__.__name__}...", flush=True)
        data = ai_service.extract_with_retry(final_image_path)
        print(f"DEBUG: [8] AI Extraction complete. Data: {data}", flush=True)
        
        if not data:
             raise Exception("AI ไม่สามารถสกัดข้อมูลจากรูปภาพได้")

        # 5. Duplicate Check & Update Logic
        order_id = data.get('order_id')
        if not order_id:
            raise Exception("ไม่พบเลขออเดอร์ในรูปภาพ")
            
        is_duplicate = sheet_service.check_duplicate(order_id)
        existing_run_no = None
        target_row_idx = None

        if is_duplicate:
            print(f"DEBUG: Duplicate order {order_id} found. Fetching row info for update.")
            target_row_idx, existing_row_data = sheet_service.find_row_by_order_id(order_id)
            if existing_row_data and len(existing_row_data) >= 4:
                try:
                    existing_run_no = int(existing_row_data[3]) # Column D index 3
                except:
                    existing_run_no = None

        # 6. Drive Upload
        # Use existing Run No if updating, otherwise get new one
        next_run_no = existing_run_no if existing_run_no else sheet_service.get_next_run_no()
        target_filename = f"{next_run_no}.jpg"
        
        drive_link = ""
        drive_error_msg = ""
        folder_display_name = "Unknown"
        
        try:
            sheet_name = get_config().get('ACTIVE_SHEET_NAME', GOOGLE_SHEET_NAME)
            folder_id = get_config().get_folder_for_sheet(sheet_name)
            folder_display_name = drive_service.get_folder_name(folder_id)
            
            drive_file = drive_service.upload_file(final_image_path, folder_id, target_filename)
            if drive_file:
                drive_link = drive_file.get('webViewLink', '')
            else:
                drive_error_msg = "Google Drive API returned None (Unknown Error)"
        except Exception as e:
            drive_error_msg = str(e)
            print(f"DEBUG: Drive Upload Error: {e}")
        
        data['image_link'] = drive_link

        # 7. Save or Update Sheet Data
        success = False
        if is_duplicate and target_row_idx:
            print(f"DEBUG: Updating existing row {target_row_idx} for order {order_id}")
            success = sheet_service.update_existing_data(target_row_idx, data, next_run_no)
            status_prefix = "✅ อัปเดตแล้ว!"
        else:
            print(f"DEBUG: Appending new row for order {order_id}")
            success = sheet_service.append_data(data, next_run_no)
            status_prefix = "✅ บันทึกแล้ว!"

        if success:
            # Success Summary
            tracking_info = f"\nTracking: {data.get('tracking_number')}" if data.get('tracking_number') and data.get('tracking_number') != '-' else ""
            
            if drive_link:
                folder_info = f"\n📁 บันทึกรูปไปที่: {folder_display_name}"
            else:
                folder_info = f"\n⚠️ บันทึกรูปไม่สำเร็จ\nสาเหตุ: {drive_error_msg[:100]}\nโปรดตรวจสอบว่าโฟลเดอร์ถูกต้องและ Token ยังใช้งานได้อยู่นะคะ"
            
            summary = (
                f"{status_prefix} (No. {next_run_no})\n"
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
            if messaging_api:
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
        if messaging_api:
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
