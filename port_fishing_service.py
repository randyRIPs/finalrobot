from flask import jsonify
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore


PORT_ALIASES = {
    "基隆": "基隆港",
    "基隆港": "基隆港",

    "台中": "臺中港",
    "臺中": "臺中港",
    "台中港": "臺中港",
    "臺中港": "臺中港",
    "北堤": "臺中港",
    "台中北堤": "臺中港",
    "臺中北堤": "臺中港",
    "北防波堤": "臺中港",

    "高雄": "高雄港",
    "高雄港": "高雄港",

    "安平": "安平港",
    "安平港": "安平港",

    "布袋": "布袋港",
    "布袋港": "布袋港",

    "花蓮": "花蓮港",
    "花蓮港": "花蓮港",
}


def get_db():
    if not firebase_admin._apps:
        if os.environ.get("serviceAccountKey"):
            firebase_json = json.loads(os.environ["serviceAccountKey"])
            cred = credentials.Certificate(firebase_json)
        else:
            cred = credentials.Certificate("serviceAccountKey.json")

        firebase_admin.initialize_app(cred)

    return firestore.client()


def extract_port_keyword(text):
    text = str(text).strip()

    for alias in PORT_ALIASES:
        if alias in text:
            return alias

    return text


def query_port_fishing(keyword):
    db = get_db()

    keyword = str(keyword).strip().replace("台", "臺")
    keyword = extract_port_keyword(keyword)

    alias_doc = db.collection("port_fishing_aliases").document(keyword).get()

    if alias_doc.exists:
        port_name = alias_doc.to_dict().get("port_name")
    else:
        port_name = PORT_ALIASES.get(keyword, keyword)

    docs = db.collection("port_fishing_spots") \
        .where("port_name", "==", port_name) \
        .stream()

    results = [doc.to_dict() for doc in docs]

    if not results:
        return f"查不到「{keyword}」的商港垂釣資訊。"

    reply = f"{port_name} 商港垂釣資訊：\n\n"

    for item in results:
        spot_name = item.get("spot_name", "")
        status = item.get("status", "未明確")
        checked_at = item.get("checked_at") or item.get("updated_at", "")
        note = item.get("note", "")

        reply += f"釣點：{spot_name}\n"
        reply += f"狀態：{status}\n"

        if checked_at:
            reply += f"查詢時間：{checked_at}\n"

        if note:
            short_note = str(note).replace("\n", " ")
            if len(short_note) > 120:
                short_note = short_note[:120] + "..."
            reply += f"備註：{short_note}\n"

        reply += "\n"

    reply += "資料來源：臺灣港務公司商港垂釣預約系統"
    return reply


def handle_port_fishing(req, query_result):
    text = query_result.get("queryText", "")
    parameters = query_result.get("parameters", {})

    keyword = (
        parameters.get("port")
        or parameters.get("location")
        or parameters.get("geo-city")
        or text
    )

    if isinstance(keyword, list):
        keyword = keyword[0] if keyword else ""

    if isinstance(keyword, dict):
        keyword = (
            keyword.get("city")
            or keyword.get("admin-area")
            or keyword.get("subadmin-area")
            or text
        )

    reply = query_port_fishing(keyword)

    return jsonify({
        "fulfillmentText": reply
    })
