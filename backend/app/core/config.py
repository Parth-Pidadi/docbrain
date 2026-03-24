from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"

    # CORS — explicit origins
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "https://docbrainai.vercel.app",
        "https://docbrain-app.vercel.app",
        "https://trydocbrain.vercel.app",
    ]
    # Vercel preview deployments all match *.vercel.app — allow them via regex
    ALLOWED_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql://docbrain:docbrain@localhost:5432/docbrain"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "png", "jpg", "jpeg", "tiff", "webp"]

    # Embedding model (used locally when Colab is unavailable)
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # Donut model (loaded on Colab GPU)
    DONUT_MODEL: str = "naver-clova-ix/donut-base-finetuned-cord-v2"

    # Colab GPU inference server (set after running DocBrain_GPU_Server.ipynb)
    # Leave empty to use local CPU fallbacks only
    COLAB_URL: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
