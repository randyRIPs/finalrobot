import json
import urllib.parse
import urllib.request

from .advice import WeatherInfo


MOCK_WEATHER = WeatherInfo(
    city="台中市",
    weather="多雲午後短暫陣雨",
    min_temp=25,
    max_temp=31,
    rain_probability=60,
    comfort="悶熱",
)


API_CITY_NAMES = {
    "台北市": "臺北市",
    "台中市": "臺中市",
    "台南市": "臺南市",
    "台東縣": "臺東縣",
}


class WeatherApi:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _mock_forecast(self, city: str) -> WeatherInfo:
        return WeatherInfo(
            city=city,
            weather=MOCK_WEATHER.weather,
            min_temp=MOCK_WEATHER.min_temp,
            max_temp=MOCK_WEATHER.max_temp,
            rain_probability=MOCK_WEATHER.rain_probability,
            comfort=MOCK_WEATHER.comfort,
        )

    def get_forecast(self, city: str) -> WeatherInfo:
        if not self.api_key:
            return self._mock_forecast(city)

        api_city = API_CITY_NAMES.get(city, city)
        query = urllib.parse.urlencode(
            {
                "Authorization": self.api_key,
                "locationName": api_city,
            }
        )
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?{query}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            print(f"CWA API request failed: {error}", flush=True)
            return self._mock_forecast(city)

        locations = payload.get("records", {}).get("location", [])
        if not locations:
            print(f"CWA API returned no weather data for {api_city}", flush=True)
            return self._mock_forecast(city)

        elements = {item["elementName"]: item["time"][0]["parameter"] for item in locations[0]["weatherElement"]}
        return WeatherInfo(
            city=city,
            weather=elements.get("Wx", {}).get("parameterName", "未知"),
            min_temp=int(elements.get("MinT", {}).get("parameterName", 0)),
            max_temp=int(elements.get("MaxT", {}).get("parameterName", 0)),
            rain_probability=int(elements.get("PoP", {}).get("parameterName", 0)),
            comfort=elements.get("CI", {}).get("parameterName", ""),
        )
