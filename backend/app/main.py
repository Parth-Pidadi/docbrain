from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, extract, insights, qa, upload
from app.core.config import settings
from app.core.database import Base, engine, run_migrations

# Create all DB tables on startup (users, documents)
Base.metadata.create_all(bind=engine)
# Apply additive migrations (e.g. new columns on existing tables)
run_migrations()

app = FastAPI(
    title="DocBrain API",
    description="Upload. Extract. Ask Anything.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,  # covers *.vercel.app previews
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(upload.router,   prefix="/api/upload",   tags=["upload"])
app.include_router(extract.router,  prefix="/api/extract",  tags=["extract"])
app.include_router(qa.router,       prefix="/api/qa",       tags=["qa"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])


@app.get("/health")
def health():
    return {"status": "ok"}
