import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    BASE_DIR = BASE_DIR
    DB_PATH = BASE_DIR / 'data' / 'market.db'

    # Divar / Bojnurd
    CITY_ID = os.getenv('DIVAR_CITY_ID', '39').strip()  # Bojnurd
    CITY_NAME = os.getenv('DIVAR_CITY_NAME', 'بجنورد').strip()
    CITY_SLUG = os.getenv('DIVAR_CITY_SLUG', 'bojnurd').strip()
    CATEGORY = os.getenv('DIVAR_CATEGORY', 'apartment-sell').strip()
    SEARCH_URL = 'https://api.divar.ir/v8/postlist/w/search'
    DETAIL_URL = 'https://api.divar.ir/v8/posts-v2/web/{token}'
    PUBLIC_SEARCH_URL = f'https://divar.ir/s/{CITY_SLUG}/buy-apartment'

    # Collector limits. Intentionally conservative for personal/local use.
    MAX_LIST_PAGES = int(os.getenv('MAX_LIST_PAGES', '100'))
    LIST_DELAY_SECONDS = float(os.getenv('LIST_DELAY_SECONDS', '0.45'))
    DETAIL_WORKERS = int(os.getenv('DETAIL_WORKERS', '3'))
    DETAIL_BUDGET = int(os.getenv('DETAIL_BUDGET', '23'))
    DETAIL_WINDOW_SECONDS = float(os.getenv('DETAIL_WINDOW_SECONDS', '30'))
    DETAIL_CACHE_DAYS = int(os.getenv('DETAIL_CACHE_DAYS', '30'))
    HTTP_TIMEOUT = int(os.getenv('HTTP_TIMEOUT', '30'))

    # Analytics
    NEW_BUILD_MAX_AGE = int(os.getenv('NEW_BUILD_MAX_AGE', '3'))
    MIN_VALID_SIZE = int(os.getenv('MIN_VALID_SIZE', '30'))
    MAX_VALID_SIZE = int(os.getenv('MAX_VALID_SIZE', '500'))
    MIN_VALID_PRICE_PER_M2 = int(os.getenv('MIN_VALID_PRICE_PER_M2', '3_000_000'.replace('_','')))
    MAX_VALID_PRICE_PER_M2 = int(os.getenv('MAX_VALID_PRICE_PER_M2', '2_000_000_000'.replace('_','')))

    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', '5050'))
