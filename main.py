import os

from dotenv import load_dotenv
from fastapi import FastAPI

# .env 파일 읽기
load_dotenv()

app = FastAPI()

# 환경변수 읽기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@app.get("/")
def root():
    return {
        "message": "Hello FastAPI World from main.py!!"
    }

@app.get("/config")
def config():
    return {
        "gemini_key": GEMINI_API_KEY,
        "supabase_url": SUPABASE_URL,
        "supabase_key": SUPABASE_KEY
    }