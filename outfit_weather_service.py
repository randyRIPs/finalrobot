from flask import jsonify
import os
import json
import urllib.parse
import urllib.request


CITY_LIST = [
    "台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市",
    "基隆市", "新竹市", "嘉義市",
    "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣",
    "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣",
    "澎湖縣", "金門縣", "連江縣"
]

OUTFIT_INTENTS = [
    "今日天氣查詢",
    "天氣查詢",
    "穿搭建議",
    "帶傘提醒",
    "活動建議",
    "weather.query",
    "outfit.suggest",
    "umbrella.check",
    "activity.suggest",
]

CITY_ALIASES = {
    "臺北": "台北市",
    "台北": "台北市",
    "新北": "新北市",
    "桃園": "桃園市",
    "臺中": "台中市",
    "台中": "台中市",
    "臺南": "台南市",
    "台南": "台南市",
    "高雄": "高雄市",
    "基隆": "基隆市",
    "新竹": "新竹市",
    "嘉義": "嘉義市",
    "苗栗": "苗栗縣",
    "彰化": "彰化縣",
    "南投": "南投縣",
    "雲林": "雲林縣",
    "屏東": "屏東縣",
    "宜蘭": "宜蘭縣",
    "花蓮": "花蓮縣",
    "臺東": "台東縣",
    "台東": "台東縣",
    "澎湖": "澎湖縣",
    "金門": "金門縣",
    "連江": "連江縣",
    "馬祖": "連江縣",
}

CWA_CITY_NAMES = {
    "台北市": "臺北市",
    "台中市": "臺中市",
    "台南市": "臺南市",
    "台東縣": "臺東縣",
}


def normalize_dialogflow_city(value):
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return (
            value.get("city")
            or value.get("admin-area")
            or value.get("subadmin-area")
            or ""
        )

    if isinstance(value, list) and value:
        return normalize_dialogflow_city(value[0])

    return ""


def extract_city_from_text(text, default_city="台中市"):
    text = str(text)

    for city in CITY_LIST:
        if city in text:
            return city

    for alias, city in CITY_ALIASES.items():
        if alias in text:
            return city

    return default_city


def detect_outfit_intent(intent_name, text):
    text = str(text).strip()
    name = str(intent_name).strip().lower()

    if any(word in text for word in ["傘", "下雨", "雨"]):
        return "umbrella"

    if any(word in text for word in ["穿", "外套", "短袖", "長袖", "衣服", "穿搭"]):
        return "outfit"

    if any(word in text for word in ["跑步", "運動", "騎車", "曬衣", "出門玩", "活動"]):
        return "activity"

    mapping = {
        "今日天氣查詢": "weather",
        "天氣查詢": "weather",
        "weather.query": "weather",
        "穿搭建議": "outfit",
        "outfit.suggest": "outfit",
        "帶傘提醒": "umbrella",
        "umbrella.check": "umbrella",
        "活動建議": "activity",
        "activity.suggest": "activity",
    }

    for key, value in mapping.items():
        if key.lower() == name:
            return value

    return "weather"


def get_general_weather(city):
    api_key = os.environ.get("CWA_API_KEY", "")

    if not api_key:
        return {
            "city": city,
            "weather": "多雲午後短暫陣雨",
            "min_temp": 25,
            "max_temp": 31,
            "rain_probability": 60,
        }

    api_city = CWA_CITY_NAMES.get(city, city)
    query = urllib.parse.urlencode({
        "Authorization": api_key,
        "locationName": api_city,
    })
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?{query}"

    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        locations = payload.get("records", {}).get("location", [])
        if not locations:
            raise Exception("CWA no location data")

        elements = {
            item["elementName"]: item["time"][0]["parameter"]
            for item in locations[0].get("weatherElement", [])
        }

        return {
            "city": city,
            "weather": elements.get("Wx", {}).get("parameterName", "未知"),
            "min_temp": int(elements.get("MinT", {}).get("parameterName", 0)),
            "max_temp": int(elements.get("MaxT", {}).get("parameterName", 0)),
            "rain_probability": int(elements.get("PoP", {}).get("parameterName", 0)),
        }

    except Exception as error:
        print(f"一般天氣查詢失敗：{error}", flush=True)
        return {
            "city": city,
            "weather": "多雲午後短暫陣雨",
            "min_temp": 25,
            "max_temp": 31,
            "rain_probability": 60,
        }


def outfit_advice(weather):
    average_temp = round((weather["min_temp"] + weather["max_temp"]) / 2)

    if average_temp >= 30:
        base = "建議穿短袖、薄材質衣物，外出注意防曬與補水。"
    elif average_temp >= 24:
        base = "建議穿短袖或薄長袖，怕冷的話可以帶一件薄外套。"
    elif average_temp >= 18:
        base = "建議穿長袖或短袖加薄外套，早晚溫差要注意。"
    elif average_temp >= 15:
        base = "建議穿長袖加外套，騎車或晚上外出要再保暖一點。"
    else:
        base = "建議穿厚外套或保暖衣物，出門前可以加圍巾。"

    if weather["rain_probability"] >= 60:
        base += " 降雨機率偏高，鞋子建議選好走、防滑或不怕濕的款式。"

    return base


def umbrella_advice(weather):
    if weather["rain_probability"] >= 60:
        return "建議帶傘，今天下雨機率偏高。"

    if weather["rain_probability"] >= 30:
        return "可以帶摺疊傘，今天有機會下雨。"

    return "下雨機率不高，通常可以不用帶傘。"


def activity_advice(weather):
    if weather["rain_probability"] >= 60:
        return "今天較不適合長時間戶外活動，建議改成室內行程。"

    if weather["max_temp"] >= 32:
        return "可以活動，但天氣偏熱，建議避開中午並多補水。"

    return "今天整體適合外出活動，記得依體感調整衣物。"


def build_outfit_reply(intent, weather):
    summary = (
        f"{weather['city']}今日天氣：{weather['weather']}，"
        f"溫度約 {weather['min_temp']}-{weather['max_temp']} 度，"
        f"降雨機率 {weather['rain_probability']}%。"
    )

    if intent == "umbrella":
        return f"{summary}\n{umbrella_advice(weather)}"

    if intent == "outfit":
        return f"{summary}\n{outfit_advice(weather)}\n{umbrella_advice(weather)}"

    if intent == "activity":
        return f"{summary}\n{activity_advice(weather)}\n{umbrella_advice(weather)}"

    return f"{summary}\n{outfit_advice(weather)}"


def handle_outfit_bot(req, query_result):
    text = query_result.get("queryText", "")
    parameters = query_result.get("parameters", {})
    intent_name = query_result.get("intent", {}).get("displayName", "")

    city = normalize_dialogflow_city(
        parameters.get("city")
        or parameters.get("geo-city")
        or parameters.get("location")
    )

    if not city:
        city = extract_city_from_text(text, os.environ.get("DEFAULT_CITY", "台中市"))

    intent = detect_outfit_intent(intent_name, text)
    weather = get_general_weather(city)
    reply = build_outfit_reply(intent, weather)

    return jsonify({
        "fulfillmentText": reply
    })
