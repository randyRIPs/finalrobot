from flask import jsonify

from weather_service import (
    handle_weather_forecast,
    handle_weather_date_select,
)

from outfit_weather_service import (
    handle_outfit_bot,
    OUTFIT_INTENTS,
)

from port_fishing_service import handle_port_fishing


def handle_dialogflow(req):
    query_result = req.get("queryResult", {})

    intent_name = (
        query_result
        .get("intent", {})
        .get("displayName", "")
    )

    # 海邊天氣潮汐
    if intent_name == "WeatherForecast":
        return handle_weather_forecast(req, query_result)

    if intent_name == "WeatherDateSelect":
        return handle_weather_date_select(req, query_result)

    # 一般天氣 / 穿搭 / 帶傘 / 活動建議
    if intent_name in OUTFIT_INTENTS:
        return handle_outfit_bot(req, query_result)

    # 商港垂釣查詢
    if intent_name in ["商港垂釣查詢", "portFishing", "PortFishing"]:
        return handle_port_fishing(req, query_result)

    return jsonify({
        "fulfillmentText": "我目前可以查詢縣市海邊天氣與潮汐，也可以查一般天氣、穿搭、帶傘建議與商港垂釣資訊。"
    })
