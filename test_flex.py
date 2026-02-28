import json

def create_order_flex_message(data, next_run_no, drive_warning):
    bubble = {
      "type": "bubble",
      "size": "mega",
      "header": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": f"✅ บันทึกแล้ว! (No. {next_run_no})",
            "weight": "bold",
            "size": "md",
            "color": "#1DB446"
          }
        ]
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": []
      }
    }
    
    body_contents = bubble["body"]["contents"]
    
    def add_row(title, value, copyable=True):
        if not value or value == '-': return
        
        row = {
          "type": "box",
          "layout": "horizontal",
          "contents": [
            {
              "type": "text",
              "text": f"{title}:",
              "weight": "bold",
              "color": "#aaaaaa",
              "flex": 2,
              "size": "sm"
            },
            {
              "type": "text",
              "text": str(value),
              "color": "#333333",
              "flex": 4,
              "size": "sm",
              "wrap": True
            }
          ],
          "alignItems": "center"
        }
        
        if copyable:
            row["contents"].append({
              "type": "button",
              "action": {
                "type": "clipboard",
                "label": "Copy",
                "clipboardText": str(value)
              },
              "flex": 2,
              "height": "sm",
              "style": "secondary"
            })
            
        body_contents.append(row)

    add_row("ชื่อ", data.get("receiver_name"))
    add_row("ที่อยู่", data.get("location"))
    add_row("ร้าน", data.get("shop_name"), copyable=False)
    add_row("ยอด", data.get("price"), copyable=True)
    body_contents.append({"type": "separator", "margin": "md"})
    add_row("Platform", data.get("platform"), copyable=False)
    add_row("Order", data.get("order_id"))
    if data.get("tracking_number") and data.get("tracking_number") != "-":
        add_row("Tracking", data.get("tracking_number"))
        
    if drive_warning:
        body_contents.append({
          "type": "text",
          "text": drive_warning,
          "color": "#FF334B",
          "size": "xs",
          "wrap": True,
          "margin": "md"
        })

    return {"altText": f"Order No. {next_run_no} สรุปข้อมูล", "contents": bubble}

print(json.dumps(create_order_flex_message({"receiver_name": "Shank", "location": "บ้านฟ้า", "price": "100"}, "242", ""), indent=2))
