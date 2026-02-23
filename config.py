import os
from dotenv import load_dotenv

load_dotenv()

SHOPLIVE_ACCESS_KEY = os.environ["SHOPLIVE_ACCESS_KEY"]
SHOPLIVE_SECRET_KEY = os.environ["SHOPLIVE_SECRET_KEY"]

SHOPLIVE_API_BASE = "https://private.shopliveapi.com/v2"

# HTTP リクエストタイムアウト（秒）
REQUEST_TIMEOUT = 10

# ライブ前後のバッファ（分）
SCHEDULE_BUFFER_MINUTES = 5
# scheduledEndAtがnullの場合のデフォルト配信時間（分）
DEFAULT_LIVE_DURATION_MINUTES = 60

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STOCK_STATUS_FILE = os.path.join(OUTPUT_DIR, "stock_status.json")
SCHEDULE_FILE = os.path.join(BASE_DIR, "schedule.json")
