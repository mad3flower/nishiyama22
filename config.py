from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = "nishiyama-dev-key"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'nishiyama.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
