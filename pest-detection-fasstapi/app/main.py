from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analyze
from app.services.classifier_service import PestClassifier
from app.services.rag import RAG


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.classifier = PestClassifier(settings.model_path)
    print(f"모델 로드 완료: {settings.model_path}")
    print(f"클래스 목록: {app.state.classifier.class_names}")

    rag = RAG()
    await rag.initialize_db()
    app.state.rag = rag
    print("RAG 초기화 완료")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Response-Text"],
)

app.include_router(analyze.router)

# python -m uvicorn app.main:app --reload --port 8080
