import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mukolend-bordeaux-silk-silver-dust-key-2026')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', str(BASE_DIR / 'mukolend.db'))
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No strict expiration for smoother hackathon demo testing
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CURRENCY_CODE = 'USD'
    CURRENCY_SYMBOL = '$'

class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = str(BASE_DIR / 'mukolend_test.db')
    WTF_CSRF_ENABLED = False
