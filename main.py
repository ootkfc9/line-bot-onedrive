import os
from urllib.parse import parse_qs
from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexContainer,
    FlexMessage,
    ImageMessage,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, PostbackEvent, TextMessageContent

app = FastAPI()

# ---------------------------------------------------------
# ข้อมูล Credentials & Config ของคุณ
# ---------------------------------------------------------
CHANNEL_ACCESS_TOKEN = os.getenv(
    "LINE_CHANNEL_ACCESS_TOKEN",
    "5Z9iR9QcC/g+xasB3HLL1vXC3su1PDltfSI8UAmzGCWH0CL8XlthnNSzB5oLpy4x2n1me4DnCCQ2JVFd4bSc6NPAt0KP3rgBrrpqvcubPNshX6V4/ZX/p7PFlAa15yYD1jt0rvLGpWR5BMntkfN0nwdB04t89/1O/w1cDnyilFU=",
)
CHANNEL_SECRET = os.getenv(
    "LINE_CHANNEL_SECRET", "9177da3ba74b69d333f00c0ef9cfef55"
)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# รายชื่อ Admin หลัก (ฝัง User ID ของคุณไว้เรียบร้อย)
ADMIN_USER_IDS = ["U856d8d37529018e25cbf191e8b04262c"]

# ฐานข้อมูลผู้ใช้ที่มีสิทธิ์ (เริ่มต้นใส่สิทธิ์ให้แอดมินคุณเป็นคนแรก)
ALLOWED_USERS = {"U856d8d37529018e25cbf191e8b04262c": "Admin Main"}

# ฐานข้อมูลเอกสารตัวอย่าง (สามารถเพิ่ม-ลดได้ในระบบ)
DOCUMENTS_DB = {
    "ระยอง-แบบก่อสร้าง": {
        "type": "link",
        "title": "แบบก่อสร้าง ไซต์ระยอง (OneDrive)",
        "url": "https://1drv.ms/b/example",
    },
    "ระยอง-รูปหน้างาน": {
        "type": "image",
        "original": "https://images.unsplash.com/photo-1541888946425-d0fbb186a5b7?w=1000",
        "preview": "https://images.unsplash.com/photo-1541888946425-d0fbb186a5b7?w=240",
    },
}

# โครงสร้าง Admin Control Panel Flex Message
ADMIN_FLEX_JSON = {
    "type": "bubble",
    "size": "medium",
    "header": {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": "🛡️ ADMIN CONTROLS",
                "weight": "bold",
                "color": "#FFFFFF",
                "size": "sm",
            },
            {
                "type": "text",
                "text": "ระบบจัดการสิทธิ์ผู้ใช้งาน",
                "weight": "bold",
                "color": "#FFFFFF",
                "size": "lg",
            },
        ],
        "backgroundColor": "#1DB446",
    },
    "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": "กรุณาเลือกรายการที่ต้องการดำเนินการ:",
                "size": "xs",
                "color": "#888888",
                "margin": "md",
            },
            {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": "➕ เพิ่มสิทธิ์ใช้งาน",
                    "data": "action=add_admin",
                },
                "style": "primary",
                "color": "#28A745",
                "margin": "md",
            },
            {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": "➖ ลบสิทธิ์ใช้งาน",
                    "data": "action=remove_admin",
                },
                "style": "primary",
                "color": "#DC3545",
                "margin": "md",
            },
            {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": "📋 เช็กลิสต์รายการทั้งหมด",
                    "data": "action=list_all",
                },
                "style": "secondary",
                "margin": "md",
            },
        ],
    },
}


# ---------------------------------------------------------
# Webhook Route
# ---------------------------------------------------------
@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"


# ---------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text.strip()
    lower_text = text.lower()
    source_type = event.source.type

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 1. เช็ก ID ตัวเอง (ใช้ได้ทุกคน)
        if lower_text in ["myid", "เช็ค id", "id"]:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=user_id)],
                )
            )
            return

        # 2. คำสั่ง Admin (ต้องใช้ในแชตส่วนตัว 1:1 เท่านั้น)
        if source_type == "user" and user_id in ADMIN_USER_IDS:

            # 2.1 เปิด Admin Panel
            if lower_text == "admin":
                flex_msg = FlexMessage(
                    alt_text="Admin Control Panel",
                    contents=FlexContainer.from_dict(ADMIN_FLEX_JSON),
                )
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token, messages=[flex_msg]
                    )
                )
                return

            # 2.2 เพิ่มสิทธิ์: add [USER_ID] [NAME]
            if lower_text.startswith("add "):
                args = text.split(maxsplit=2)
                if len(args) >= 2:
                    new_user_id = args[1]
                    name = args[2] if len(args) > 2 else "ไม่ระบุชื่อ"
                    ALLOWED_USERS[new_user_id] = name
                    reply_text = (
                        f"✅ เพิ่มสิทธิ์ให้ '{name}' ({new_user_id}) เรียบร้อยแล้ว"
                    )
                else:
                    reply_text = "❌ รูปแบบไม่ถูกต้อง! กรุณาพิมพ์: add [USER_ID] [ชื่อผู้ใช้งาน]"

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)],
                    )
                )
                return

            # 2.3 ลบสิทธิ์: ลบ [USER_ID หรือ ชื่อ]
            if lower_text.startswith("ลบ "):
                target = text.split(maxsplit=1)[1]
                target_key = None

                for u_id, name in ALLOWED_USERS.items():
                    if u_id == target or name == target:
                        target_key = u_id
                        break

                if target_key:
                    removed_name = ALLOWED_USERS.pop(target_key)
                    reply_text = (
                        f"🗑️ ลบสิทธิ์ของ '{removed_name}' ออกจากระบบเรียบร้อยแล้ว"
                    )
                else:
                    reply_text = f"⚠️ ไม่พบผู้ใช้งานที่ตรงกับ '{target}'"

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)],
                    )
                )
                return

            # 2.4 เช็กสิทธิ์รายชื่อทั้งหมด
            if lower_text in ["เช็คสิทธิ์", "รายชื่อ"]:
                msg_lines = ["📋 รายชื่อผู้มีสิทธิ์ใช้งานระบบ:"]
                for i, (u_id, name) in enumerate(ALLOWED_USERS.items(), 1):
                    msg_lines.append(f"{i}. {name} ({u_id})")
                reply_text = "\n".join(msg_lines)

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)],
                    )
                )
                return

        # 3. ค้นหาเอกสาร (สำหรับผู้มีสิทธิ์)
        if user_id in ALLOWED_USERS:
            if "-" in text:
                parts = [p.strip() for p in text.split("-", 1)]
                search_key = f"{parts[0]}-{parts[1]}"

                if search_key in DOCUMENTS_DB:
                    doc = DOCUMENTS_DB[search_key]
                    if doc["type"] == "image":
                        msg = ImageMessage(
                            original_content_url=doc["original"],
                            preview_image_url=doc["preview"],
                        )
                    else:
                        msg = TextMessage(
                            text=f"📄 {doc['title']}\n🔗 ลิงก์เปิดดู: {doc['url']}"
                        )

                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token, messages=[msg]
                        )
                    )
                    return


@handler.add(PostbackEvent)
def handle_postback(event: PostbackEvent):
    user_id = event.source.user_id
    reply_token = event.reply_token

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if user_id not in ADMIN_USER_IDS:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        TextMessage(
                            text="⚠️ คุณไม่มีสิทธิ์ใช้งานฟังก์ชันนี้ (Admin Only)"
                        )
                    ],
                )
            )
            return

        postback_data = event.postback.data
        parsed_data = parse_qs(postback_data)
        action = parsed_data.get("action", [None])[0]

        if action == "add_admin":
            reply_text = (
                "➕ **ขั้นตอนการเพิ่มสิทธิ์**\n\n"
                "กรุณาพิมพ์คำสั่งในรูปแบบ:\n"
                "`add [LINE_USER_ID] [ชื่อผู้ใช้งาน]`\n\n"
                "ตัวอย่าง:\n"
                "`add U1234567890abcdef ช่างตั้ม`"
            )
        elif action == "remove_admin":
            reply_text = (
                "➖ **ขั้นตอนการลบสิทธิ์**\n\n"
                "กรุณาพิมพ์คำสั่งในรูปแบบ:\n"
                "`ลบ [LINE_USER_ID]` หรือ `ลบ [ชื่อผู้ใช้งาน]`\n\n"
                "ตัวอย่าง:\n"
                "`ลบ U1234567890abcdef` หรือ `ลบ ช่างตั้ม`"
            )
        elif action == "list_all":
            msg_lines = ["📋 รายชื่อผู้มีสิทธิ์ใช้งานระบบ:"]
            for i, (u_id, name) in enumerate(ALLOWED_USERS.items(), 1):
                msg_lines.append(f"{i}. {name} ({u_id})")
            reply_text = "\n".join(msg_lines)
        else:
            reply_text = "⚠️ ไม่พบคำสั่ง"

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token, messages=[TextMessage(text=reply_text)]
            )
        )
