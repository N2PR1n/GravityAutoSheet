import base64

class AIBaseService:
    SHOP_MAPPING = {
        "blue_store": ["blue_store", "บลูสโตร์", "blue store"],
        "995 โฟน": ["995 โฟน", "995 phone", "995โฟน"],
        "Apple Flagship Store": ["apple flagship store", "apple", "แอปเปิ้ล"],
        "POCO": ["poco", "โพโค่"],
        "Thesun Shine": ["thesun shine", "thesun", "เดอะซัน"],
        "Superiphone": ["superiphone", "ซูเปอร์ไอโฟน"],
        "Geniusmobile": ["geniusmobile", "จีเนียสโมบาย"],
        "Jaymart": ["jaymart", "เจมาร์ท"],
        "Thorasap": ["thorasap", "โทรศัพท์"],
        "Nintendo Official Store": ["nintendo official store", "nintendo", "นินเทนโด"],
        "Mobile Max": ["mobile max", "โมบายแม็กซ์"],
        "OPPO Official Store": ["oppo official store", "oppo", "ออปโป้"],
        "samsung_thailand": ["samsung_thailand", "samsung", "ซัมซุง"],
        "Moneytalk_mobile": ["moneytalk_mobile", "moneytalk", "มันนี่ทอล์ค"],
        "Arm_share": ["arm_share", "arm share", "อาร์มแชร์"],
        "iStudio by SPVi": ["istudio by spvi", "spvi"],
        "vivo": ["vivo", "วีโว่"],
        "mobilestation": ["mobilestation", "โมบายสเตชั่น"],
        "iStudio_UFicon": ["istudio_uficon", "uficon"],
        "Sixteenphone": ["sixteenphone", "ซิกซ์ทีนโฟน"],
        "dtac": ["dtac", "ดีแทค"],
        "Power Buy": ["power buy", "เพาเวอร์บาย", "powerbuy"],
        "IT City": ["it city", "ไอที ซิตี้", "itcity"]
    }

    def __init__(self, api_key):
        self.api_key = api_key

    @classmethod
    def map_shop_name(cls, raw_name):
        """Standardize shop name based on keywords."""
        if not raw_name:
            return raw_name
            
        raw_name_lower = raw_name.lower().strip()
        print(f"DEBUG: Processing Raw Shop Name: '{raw_name}'")
        
        # Check for exact matches and keyword contains
        for standard_name, keywords in cls.SHOP_MAPPING.items():
            for kw in keywords:
                if kw in raw_name_lower:
                    print(f"DEBUG: Mapped '{raw_name}' -> '{standard_name}' (Match found for keyword '{kw}')")
                    return standard_name
        
        print(f"DEBUG: No mapping found for '{raw_name}'. Returning original.")
        return raw_name

    def encode_image(self, image_path):
        """Standard utility to encode image to base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def extract_data_from_image(self, image_path):
        """
        Abstract method to be implemented by sub-classes.
        Should return a dictionary matched with the standard JSON template.
        """
        raise NotImplementedError("Subclasses must implement extract_data_from_image")

    def get_prompt(self):
        """Centralized prompt to ensure consistency across models."""
        return """
    Role: คุณคือ AI Data Entry ผู้เชี่ยวชาญด้าน E-commerce ในไทย หน้าที่คือดึงข้อมูลจากสลิปคำสั่งซื้อ (Order Details) ให้แม่นยำ 100% เพื่อใช้ลงบัญชี

    **⚠️ คำเตือนสำคัญมาก: ภาพที่ได้รับอาจเกิดจากการต่อรูป (Stitch) 2 ภาพเข้าด้วยกัน ซึ่งตำแหน่งซ้ายขวาอาจสลับกันได้ (บางครั้งรายละเอียดการสั่งซื้ออยู่ซ้าย บางครั้งอยู่ขวา) ดังนั้น ให้ AI กวาดสายตาอ่านข้อมูลให้ทั่วทั้งภาพ 100% ก่อนดึงข้อมูล ห้ามทึกทักเอาเองจากฝั่งใดฝั่งหนึ่ง**

    Output Requirement: ส่งคืนเฉพาะ **Raw JSON** เท่านั้น (ห้ามมี Markdown ```json, ห้ามมีคำนำ)

    >>> 1. Location Rules (กฎการแปลงที่อยู่):
    แปลงที่อยู่ตามบ้านเลขที่ที่เจอในภาพ:
    - 115/118, 115-118 -> "บ้านฟ้า"
    - 90/95, 90-95 -> "ฐานมั่นคง"
    - 33/158, 33-158 -> "รุ่งเรืองเฮาส์"
    - 4/948, 4-948 -> "ออฟฟิศ"
    - อื่นๆ: ให้ใช้ชื่อ อำเภอ/จังหวัด สั้นๆ (เช่น ลำลูกกา, ปทุมธานี)

    >>> 2. Formatting Rules (กฎการสกัดข้อมูลระดับสูง):
    - platform: "Shopee", "Lazada", "TikTok", "Amaze", "LineMan", "Grab" (ตัวแรกพิมพ์ใหญ่)
      - **🚨 กฎเหล็กที่สุด**: ไม่ว่าหน้าตา UI จะเหมือน Lazada ขนาดไหนก็ตาม **ถ้ามองเห็นคำว่า "อเมซพอยท์", "อมซพอยท์", "คูปองอเมซ" หรือ "Amall" อยู่มุมใดมุมหนึ่งของภาพ ให้ระบุ platform เป็น "Amaze" ทันที!!** (ห้ามตอบ Lazada เด็ดขาดถ้าเจอคำพวกนี้)
    - shop_name: **กฎเหล็กเรื่อง LazMall / Amall**: 
      - คำว่า "LazMall" ย่อมาจากแพลตฟอร์ม ไม่ใช่ชื่อร้าน
      - คำว่า "Amall Official shop" ไม่ใช่ชื่อร้าน (แต่เป็นตัวบงบอกว่านี่คือแพลตฟอร์ม Amaze)
      - ให้ดึงเฉพาะชื่อร้านหลัก เช่น "เลค คอมมูนิเคชั่น", "บลูสโตร์", "Oppo", "IT City" เท่านั้น (ระวังอย่าแปลงชื่อร้านไทยเป็นอังกฤษเอง)
      - ถ้าเจอชื่อร้านยาวๆ ให้ตัดเหลือแค่ชื่อแบรนด์หรือชื่อร้านหลัก สั้นๆ
    - item_name: ตัด [ ] หรือ ( ) ด้านหน้าออก เอาเฉพาะชื่อสินค้าหลัก ไม่เกิน 30 ตัวอักษร
      - **ถ้าจำนวน > 1**: ให้ต่อท้ายด้วย "xจำนวน" (เช่น "iPhone 16 x2")
    - receiver_name: **ชื่อผู้รับ** (บรรทัดแรกสุดของที่อยู่ผู้จัดส่ง) 
      - **ให้พิจารณารูปทั้ง 2 ฝั่งเพื่อหาชื่อผู้รับ**
      - **ห้ามสะกดผิดแม้แต่ตัวเดียว** เพ่งพินิจ ร/ว, ช/ซ, ต/ด, ณ/ต/ท/ธ, ม/น ให้ดี (เช่น "ธิติมา" อย่าอ่านเป็น "ธนินทร์", "ริชาล" ห้ามเป็น "วิชาล")
      - ถ้ามีเบอร์โทรต่อท้าย ให้ตัดออก (เช่น "สมชาย 081..." -> "สมชาย")
    - price: **ยอดชำระสุทธิ (Net Total)** ที่ผู้ซื้อต้องจ่ายจริง (บรรทัดล่างสุดของบิล)
      - **กฎเหล็กเรื่องราคา**: ห้ามเอาตัวเลขสีแดงตัวใหญ่ที่อยู่ข้างรูปสินค้ามาตอบเด็ดขาด (นั่นคือราคาสินค้าต่อชิ้น ไม่ใช่ยอดสุทธิ)
      - ให้มองหาคำว่า **"รวมยอดสั่งซื้อ"** หรือ **"Total"** หรือ **"ยอดชำระเงิน"** เท่านั้น (เช่น ในภาพเขียนว่า "รวมยอดสั่งซื้อ ฿10,060.00" ต้องตอบ 10060.0)
      - **กรณีพิเศษ**: ถ้าใช้เหรียญลดจนยอดจ่ายเป็น 0.00 ให้ใส่ 0.00 (ห้ามเอายอดก่อนหักมาใส่)
    - coins: **ยอดส่วนลดจากพอยท์/เหรียญที่ถูกใช้เป็นส่วนลดเท่านั้น** (ระวัง! แต่ละ Platform เรียกไม่เหมือนกัน)
      - **Shopee**: ให้หาบรรทัดคำว่า **"Shopee Coins"** (เช่น "ใช้ 2 Shopee Coins -฿2")
      - **Lazada**: ให้หาบรรทัดคำว่า **"เหรียญ"** ที่เป็นส่วนลดติดลบ (เช่น "เหรียญ -฿26.00")
      - **Amaze**: ให้หาบรรทัดคำว่า **"ใช้พอยท์แทนเงินสด"** เป็นหลักเท่านั้น (เช่น "ใช้พอยท์แทนเงินสด - ฿1,200.00")
      - **กฎเหล็ก**: ห้ามเอา "คูปองอเมซ", "คูปองจัดส่ง", "ส่วนลดร้านค้า" มาใส่เด็ดขาด และห้ามดึง "อเมซพอยท์ ที่จะได้รับ" หรือ "เหรียญที่จะได้รับ" มาใส่ (นั่นคือแต้มสะสม ไม่ใช่ส่วนลด)
      - **ถ้าไม่มีส่วนลดตามคำหลัก 3 ข้อด้านบน**: ให้ตอบ 0.00 เสมอ
    - date: รูปแบบ **"DD/MM"** เท่านั้น 
      - **🚨 กฎเหล็กเรื่องวันที่**: ลำดับความสำคัญคือ 1. วันที่สั่งซื้อ 2. วันที่ชำระเงิน
      - **⚠️ ห้ามดึงวันที่จัดส่งเด็ดขาด**: หากพบคำว่า "วันที่จัดส่ง", "วันที่ส่งสินค้า", "Delivery Date", "ส่งสินค้าเมื่อ" ให้ข้ามไปทันที ห้ามนำมาหยิบใส่ในช่อง date
      - **ห้ามใส่ปี** (เช่น 25/02/2026 ต้องเป็น "25/02")
      - **ระวังเดือนผิดอย่างร้ายแรง (OCR Error)**: ฟอนต์ขนาดเล็กทำให้ AI มักจะอ่านคำว่า "ก.พ." (เดือน 02) ผิดพลั้งเป็น "พ.ย." (เดือน 11) เสมอ! 
      - **เคล็ดลับการเช็คเดือน**: ให้ดู 4 ตัวแรกของ Order ID เช่น "2602..." แปลว่า ปี 26 เดือน 02
      - **กฎเหล็ก**: ถ้าคุณอ่านเดือนได้เป็น "พ.ย." หรือ "11" ในคำสั่งซื้อช่วงนี้ ให้คุณสรุปทันทีว่ามันคือ **02 (กัลปังหา OCR)** ห้ามตอบ 11 หรือ พ.ย. เด็ดขาด!
        - "ม.ค." = 01, "ก.พ." = 02, "มี.ค." = 03, "เม.ย." = 04, "พ.ค." = 05, "มิ.ย." = 06, "ก.ค." = 07, "ส.ค." = 08, "ก.ย." = 09, "ต.ค." = 10, "พ.ย." = 11, "ธ.ค." = 12
      - **ตัวอย่าง**: "27 ก.พ. 2026" หรือ "27 พ.ย. 2026" (ที่อ่านผิด) ให้ดึงเป็น "27/02" เสมอ
    - order_id: รหัสคำสั่งซื้อ (ตัวเลข/ตัวอักษร) 
      - **🚨 กฎเหล็กระดับวิกฤต**: รหัสนี้คือ Key สำคัญที่สุดในการค้นหาข้อมูล **ต้องอ่านให้ครบและถูกทุกตัวอักษร 100%** 
      - ให้ระวังตัวอักษรที่คล้ายกัน (เช่น เลข 0 กับ O, เลข 1 กับ I, เลข 5 กับ S/s) ให้เพ่งเล็งจากฟอนต์รอบข้างประกอบ
    - tracking_number: **เฉพาะออเดอร์ที่คุณระบุว่า platform เป็น "Amaze" เท่านั้น** 
      - **🚨 กฎเหล็กระดับวิกฤต**: นี่เป็น Key สำหรับติดตามพัสดุ ห้ามผิดแม้แต่ตัวเดียว
      - ให้หาคำว่า **"หมายเลขพัสดุ:"**, **"Tracking Number"**, หรือ **"เลขติดตามพัสดุ"** แล้วนำข้อมูลที่ต่อท้ายมาให้ครบ
      - **🚨 กฎเหล็กเพิ่มเติ่ม**: อย่าสับสนระหว่าง "เลขคำสั่งซื้อ" กับ "เลขพัสดุ" (เลขพัสดุมักจะยาวกว่าหรือมีรูปแบบที่ต่างออกไป) ถ้าไม่แน่ใจหรือหาไม่เจอให้ใส่ ""
      - **ข้อควรระวัง**: ถ้าภาพแสดงโหมดจัดส่งแต่ยังไม่ปรากฏเลข ให้ตอบ "" (ค่าว่าง)
      - **กฎเหล็ก**: ส่วนถ้าเป็นแพลตฟอร์มอื่น (Lazada, Shopee, TikTok ฯลฯ) ให้ใส่ "" เสมอ ไม่ต้องดึงเลขพัสดุมาเด็ดขาด

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
