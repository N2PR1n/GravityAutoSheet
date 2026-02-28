import base64
import json
from openai import OpenAI
import os

class OpenAIService:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def extract_data_from_image(self, image_path):
        """
        Sends image to OpenAI GPT-4o and extracts data as JSON.
        """
        base64_image = self.encode_image(image_path)
        
        prompt = """
    Role: คุณคือ AI Data Entry ผู้รักความเป็นระเบียบ หน้าที่คือดึงข้อมูลจากสลิปและจัด Format ให้สวยงาม สะอาดตา พร้อมลง Database ทันที

    Output Requirement: ส่งคืนเฉพาะ **Raw JSON** เท่านั้น (ห้ามมี Markdown ```json, ห้ามมีคำนำ)

    >>> 1. Location Rules (กฎการแปลงที่อยู่ให้เป็นมาตรฐาน):
    มองหา "บ้านเลขที่" ในภาพ แล้วแปลงเป็น Keyword สั้นๆ ตามนี้เท่านั้น:
    - เจอเลข "115" คู่กับ "118" (เช่น 115/118, 115-118) -> ให้ตอบว่า "บ้านฟ้า"
    - เจอเลข "90" คู่กับ "95" (เช่น 90/95, 90-95) -> ให้ตอบว่า "ฐานมั่นคง"
    - เจอเลข "33" คู่กับ "158" (เช่น 33/158, 33-158) -> ให้ตอบว่า "รุ่งเรืองเฮาส์"
    - เจอเลข "4" คู่กับ "948" (เช่น 4/948, 4-948) -> ให้ตอบว่า "ออฟฟิศ"
    - *ไม่เจอเลขข้างบน*: ให้ตอบชื่อ เขต/อำเภอ หรือ จังหวัด สั้นๆ (เช่น ลำลูกกา, ปทุมธานี)

    >>> 2. Formatting Rules (กฎการจัดรูปแบบให้สวยงาม):
    - platform: "Shopee", "Lazada", "TikTok", "Amaze", "LineMan", "Grab" (ตัวแรกพิมพ์ใหญ่เสมอ)
    - shop_name: **ตัดคำพวกนี้ออก**: "Official Store", "Mall", "LazMall", "Flagship Store", "Thailand" (ถ้าต่อท้าย) **เอาเฉพาะชื่อร้านจริงๆ** (เช่น "Xiaomi Thailand Mall" -> "Xiaomi", "LazMall Power Buy" -> "Power Buy")
    - item_name: ตัดคำโฆษณาในวงเล็บ [] หรือ () ด้านหน้าออก เอาเฉพาะชื่อสินค้าหลัก สั้นกระชับ ไม่เกิน 30 ตัวอักษร **และถ้ามีจำนวนมากกว่า 1 ให้ต่อท้ายด้วย "xจำนวน" (เช่น "AirPods4 x10")**
    - receiver_name: **ชื่อผู้รับ** (บรรทัดแรกสุดใต้คำว่า "ที่อยู่ในการจัดส่ง" หรือ "ที่อยู่")
      - **คำสั่งเด็ดขาด**: ต้องอ่านและสะกดตามตัวอักษรในภาพเป๊ะๆ 100% ห้าม AI เดาคำ หรือคิดคำขึ้นมาเอง ห้ามสะกดผิดแม้แต่สระ/พยัญชนะเดียว
      - **ระวังฟอนต์หลอกตา**: ฟอนต์ในระบบมักจะทำให้ AI สับสนชื่อคนไทยบ่อยๆ เช่น "ธิติยา" AI มักอ่านผิดเป็น "ธิชา" หรือ "ธิติมา" AI มักอ่านผิดเป็น "ธธินา" ขอให้เพ่งทีละตัวอักษรให้ดี
      - **พยัญชนะที่มักสับสน**: "ร/ว", "ช/ซ", "ต/ด" (เช่น "ริชาลลล" ไม่ใช่ "วิซาลลล")
      - ถ้าชื่อมีเบอร์โทรต่อท้าย ให้ตัดเบอร์โทรออก เอาแค่ตัวอักษรชื่อ (เช่น "ธิติมา (093xxx)" -> "ธิติมา")
    - price: **ต้องเป็น "ยอดชำระจริง" หรือ "ยอดโอน" (Net Payment / Grand Total) เท่านั้น** ให้มองหาตัวเลขที่อยู่ล่างสุด หรือท้ายสุดของบิลเสมอ
      - **กรณีพิเศษ**: ถ้า "ยอดชำระ" เป็น 0.00 และมีการใช้ "ใช้พอยท์แทนเงินสด" หรือ "Coins" จนหมด ให้ตอบ price = 0.00 (ไม่ต้องพยายามเอายอดก่อนหักมาใส่)
    - coins: ยอดส่วนลดที่เกิดจากการใช้เหรียญหรือพอยท์แทนเงินสด (เช่น "Shopee Coins", "ใช้พอยท์แทนเงินสด")
      - ถ้าเจอคำว่า "ใช้พอยท์แทนเงินสด" หรือ "Coins" ให้เอาตัวเลขจำนวนเงินที่ลดมาใส่ในช่อง coins
      - **สำคัญมาก**: ถ้าไม่มีการใช้พอยท์เป็นส่วนลดให้ตอบ 0.00 ทันที
      - **ห้ามเด็ดขาด 1**: ห้ามเอาตัวเลขจากบรรทัด "คูปอง" "คูปองส่วนลด" หรือ "ส่วนลดร้านค้า" มาใส่ในช่อง coins เด็ดขาดคูปองไม่ใช่ coins (เช่น "คูปองอเมซ - ฿750" ต้องตอบ coins: 0.00)
      - **ห้ามเด็ดขาด 2 (สำคัญมาก)**: ห้ามเอาตัวเลขจากบรรทัด **"อเมซพอยท์"** ทั้งหมดมาตอบเด็ดขาด ไม่ว่าจะเป็น "อเมซพอยท์ ที่จะได้รับ" หรือ **"อเมซพอยท์ พิเศษ"** (Amaze Points / Special Points) เพราะนั่นคือคะแนนที่จะได้ ไม่ใช่ส่วนลดที่ใช้จ่ายจริง (เช่น "อเมซพอยท์ พิเศษ (+70,000) ≈ 700.00 บาท" -> **ต้องตอบ coins: 0.00 เท่านั้น**)
    - date: รูปแบบ **"DD/MM"** เท่านั้น (ไม่ต้องใส่ปี)
    - order_id: เอาเฉพาะตัวเลขและตัวอักษร (ตัดคำว่า Order No. ออก) **อ่านและพิมพ์ให้ถูกต้องทุกตัวอักษร (เช่น อย่าสับสนตัว U กับตัว X)**
    - tracking_number: **เฉพาะของ Amaze เท่านั้น** ให้มองหาคำว่า "หมายเลขพัสดุ" (มักเป็นตัวเลข 12 หลัก)
      - **คำเตือน**: ห้ามเอา "หมายเลขอ้างอิง" (ที่ขึ้นต้นด้วย AMZ-ORD...) มาใส่ในช่องนี้เด็ดขาด
      - ถ้าเป็น Platform อื่น ให้ส่งคืนค่าว่าง "" เท่านั้น ห้ามใส่ขีด - หรือคำว่า ไม่มี

    JSON Template:
    {
      "platform": "String",
      "shop_name": "String",
      "item_name": "String",
      "price": Number,
      "coins": Number,
      "receiver_name": "String",
      "location": "String",
      "date": "DD/MM",
      "order_id": "String",
      "tracking_number": "String"
    }
    """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
            )
            
            content = response.choices[0].message.content
            
            # Clean up response text to ensure it's valid JSON
            text = content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
            
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            return None
