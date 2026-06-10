import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


class Config:
    line_channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
    cwa_api_key = os.getenv("CWA_API_KEY", "")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    default_city = os.getenv("DEFAULT_CITY", "台中市")
    google_application_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
