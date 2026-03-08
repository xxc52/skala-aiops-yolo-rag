### 작물 병충해 및 작물 검색? rag
### base llm : 
### vectorDB -> pgvector
### case 1 : input : audio_path // output : audio_path
### case 2 : input : audio_path + image_result // output : audio_path
### image_result = [Object] -> 클래스 처리 필요

import os
import asyncio
from typing import Optional, List, Dict, Tuple
from openai import OpenAI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.audio_processing import audio_processing

load_dotenv()

class RAG:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=self.api_key)
        self.model_name = "gpt-4o"
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.audio_processor = audio_processing()

        # add
        self.lang_map = {
            "ko": "Korean",
            "vi": "Vietnamese",
            "th": "Thai"
        }

        self.db_url = os.getenv("DB_CONFIG", "")
        # SQLAlchemy 비동기 엔진 설정 (Connection Pool 포함)
        self.engine = create_async_engine(
            self.db_url.replace("postgresql://", "postgresql+asyncpg://"),
            pool_size=10,
            max_overflow=20
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

        self.top_k = int(os.getenv("TOP_K", "3"))
        self.pdf_path = os.getenv("PDF_PATH", "./data/crop_knowledge.pdf")

    async def _get_embedding(self, text: str) -> List[float]:
        """비동기 래퍼를 통한 임베딩 생성"""
        return await asyncio.to_thread(
            lambda: self.client.embeddings.create(input=[text.replace("\n", " ")], model=self.embedding_model).data[0].embedding
        )

    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩 생성"""
        cleaned_texts = [t.replace("\n", " ") for t in texts]
        response = await asyncio.to_thread(
            lambda: self.client.embeddings.create(input=cleaned_texts, model=self.embedding_model)
        )
        return [data.embedding for data in response.data]

    async def initialize_db(self):
        """시스템 시작 시 DB 초기화 및 인덱스 생성"""
        async with self.SessionLocal() as session:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS crop_knowledge (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    embedding VECTOR(1536)
                );
            """))

            result = await session.execute(text("SELECT COUNT(*) FROM crop_knowledge;"))
            if result.scalar() == 0:
                await self._ingest_from_pdf(session)

            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS crop_hnsw_idx
                ON crop_knowledge USING hnsw (embedding vector_cosine_ops);
            """))

            # AIOps 테이블 추가
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS detection_events (
                    id          SERIAL PRIMARY KEY,
                    uuid        TEXT NOT NULL UNIQUE,
                    image_path  TEXT,
                    pest_code   TEXT,
                    confidence  FLOAT,
                    is_low_conf BOOLEAN DEFAULT FALSE,
                    review_status TEXT DEFAULT 'pending',
                    human_label TEXT,
                    created_at  TIMESTAMP DEFAULT NOW(),
                    reviewed_at TIMESTAMP
                );
            """))

            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS aiops_reports (
                    id           SERIAL PRIMARY KEY,
                    period_type  TEXT NOT NULL,
                    period_start TIMESTAMP NOT NULL,
                    period_end   TIMESTAMP NOT NULL,
                    content      TEXT NOT NULL,
                    created_at   TIMESTAMP DEFAULT NOW()
                );
            """))

            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS model_config (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """))

            await session.execute(text("""
                INSERT INTO model_config (key, value)
                VALUES ('conf_threshold', '0.4')
                ON CONFLICT (key) DO NOTHING;
            """))

            await session.commit()

    async def _ingest_from_pdf(self, session: AsyncSession):
        """비동기 인제션 로직"""
        loader = PyPDFLoader(self.pdf_path)
        docs = await asyncio.to_thread(loader.load)
        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
        chunks = [c.page_content for c in splitter.split_documents(docs)]

        embeddings = await self._get_embeddings_batch(chunks)
        for content, emb in zip(chunks, embeddings):
            await session.execute(
                text("INSERT INTO crop_knowledge (content, embedding) VALUES (:c, :e)"),
                {"c": content, "e": str(emb)}
            )
        await session.commit()

    async def _retrieve(self, query: str) -> str:
        """비동기 벡터 검색"""
        if not query or not query.strip():
            return ""
        query_vec = await self._get_embedding(query)
        async with self.SessionLocal() as session:
            # :vec 부분을 괄호로 감싸서 캐스팅과 분리하거나 
            # 혹은 cast() 함수를 사용하는 것이 안전합니다.
            result = await session.execute(text("""
                SELECT content FROM crop_knowledge 
                ORDER BY embedding <=> CAST(:vec AS vector) 
                LIMIT :k
            """), {"vec": str(query_vec), "k": self.top_k})
            
            return "\n".join([row[0] for row in result.fetchall()])

    async def compose_prompt(self, mode: int, query: str, lang: str, analysis_result: Optional[object] = None) -> List[Dict]:
        """
        이미지 분석 결과와 문헌 지식을 교차 검증하도록 튜닝된 프롬프트 구성
        """
        # 시스템 페르소나 및 제약 사항 설정
        system_instruction = (
            f"당신은 농작물 병해충 및 재배법 전문가입니다. 모든 답변은 '{lang}'로 작성하세요.\n\n"
            "응답 작성 가이드라인:\n"
            "1. 분석 우선순위: 병충해명 또는 [Context]의 문헌 정보를 대조하여 질의에 답을 생성하세요\n"
            "2. 구체적 처방: 식별된 병해충에 대한 구체적인 방제법(친환경 및 화학적 방법)과 향후 예방책을 제시하세요.\n"
            "3. 근거 제시: 답변의 근거가 [Context]의 어느 부분에 해당하는지 언급하세요.\n"
            "4. 불확실성: 제공된 정보만으로 판단이 어려울 경우, 추가로 확인이 필요한 증상을 사용자에게 요청하세요."
        )

        # 관련 컨텍스트 검색
        context = await self._retrieve(query)

        # 사용자 메시지 구성
        user_msg = "아래 정보를 바탕으로 종합 진단 및 가이드를 제공하세요.\n\n"
        
        if context.strip():
            user_msg += f"### [전문 문헌 정보 (Context)]\n{context}\n\n"
        else:
            user_msg += "### [전문 문헌 정보 (Context)]\n관련된 문헌 정보를 찾을 수 없습니다. 일반적인 지식을 바탕으로 답변하되 주의사항을 명시하세요.\n\n"

        # 클래스 받아서 추가 처리 필요
        if mode == 2 and analysis_result:
            user_msg += (
                "### [병충해 정보]\n"
                f"현재 작물의 병충해 : {analysis_result}\n\n"
            )
        
        user_msg += f"### [사용자 추가 질의]\n{query}"

        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_msg}
        ]

    async def forward(
        self,
        query: str,
        mode: int = 1,
        lang: str = "ko",
        analysis_result: Optional[object] = None,
        output_path: str = "output.mp3",
    ) -> Tuple[str, str]:

        target_lang = self.lang_map.get(lang.lower(), lang)

        # STT: 파일 형식에 따라 wav로 변환
        ext = query.rsplit(".", 1)[-1].lower()
        if ext == "webm":
            wav_path = query.replace(".webm", ".wav")
            self.audio_processor.convert_webm_to_wav(query, wav_path)
        elif ext == "mp4":
            wav_path = query.replace(".mp4", ".wav")
            self.audio_processor.convert_mp4_to_wav(query, wav_path)
        else:
            wav_path = query

        stt_text = self.audio_processor.transcribe_audio_file_local(wav_path)
        print(f"stt 결과 : {stt_text}")

        if not stt_text or not stt_text.strip():
            fallback = {
                "ko": "말씀을 인식하지 못했습니다. 더 크고 명확하게 다시 말씀해 주세요.",
                "vi": "Không nhận được giọng nói. Vui lòng nói to và rõ hơn.",
                "th": "ไม่ได้ยินเสียง กรุณาพูดให้ดังและชัดขึ้น",
            }
            fallback_text = fallback.get(lang.lower(), fallback["ko"])
            self.audio_processor.text_to_speech(fallback_text, output_path)
            return fallback_text, output_path

        messages = await self.compose_prompt(mode, stt_text, target_lang, analysis_result)

        try:
            response = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.2,
                )
            )
            response_text = response.choices[0].message.content
            self.audio_processor.text_to_speech(response_text, output_path)
            return response_text, output_path

        except Exception as e:
            error_msg = f"오류 발생: {str(e)}"
            # Re-raise so the caller (analyze endpoint) can return a proper error
            # instead of trying to serve a non-existent mp3 file.
            raise RuntimeError(error_msg) from e