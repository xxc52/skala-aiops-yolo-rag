import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.config import settings
from app.schemas import ClassificationResult

router = APIRouter(prefix="/api")


async def _save_detection_event(rag, event_uuid: str, image_path: str | None,
                                pest_code: str | None, confidence: float | None,
                                is_low_conf: bool, review_status: str):
    """detection_events 테이블에 탐지 이벤트 저장"""
    async with rag.SessionLocal() as session:
        await session.execute(text("""
            INSERT INTO detection_events
                (uuid, image_path, pest_code, confidence, is_low_conf, review_status)
            VALUES (:uuid, :image_path, :pest_code, :confidence, :is_low_conf, :review_status)
        """), {
            "uuid": event_uuid,
            "image_path": image_path,
            "pest_code": pest_code,
            "confidence": confidence,
            "is_low_conf": is_low_conf,
            "review_status": review_status,
        })
        await session.commit()


@router.post("/analyze")
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(None),  # 이미지는 선택 사항
    audio: UploadFile = File(...),
    language: str = Form(...),  # "ko" / "vi" / "th"
):
    classifier = request.app.state.classifier
    rag = request.app.state.rag
    threshold = getattr(request.app.state, "conf_threshold", 0.4)

    # 1. 이미지 유무에 따른 시나리오 분기
    context_pest = None
    if image and image.filename:
        img_ext = Path(image.filename).suffix
        img_uuid = str(uuid.uuid4())
        img_path = settings.upload_dir / f"{img_uuid}{img_ext}"
        with open(img_path, "wb") as f:
            f.write(await image.read())

        prediction = classifier.predict(str(img_path), threshold=threshold)
        if not prediction:
            # 탐지 결과 없음 - 이미지 삭제
            background_tasks.add_task(img_path.unlink, missing_ok=True)
            return {"detected": False, "message": "병충해가 감지되지 않았습니다. 선명하게 다시 촬영해 주세요."}

        if prediction["is_low_conf"]:
            # 저신뢰도 - 이미지를 review 디렉토리에 보관
            review_path = settings.review_dir / f"{img_uuid}.jpg"
            shutil.copy2(str(img_path), str(review_path))
            background_tasks.add_task(img_path.unlink, missing_ok=True)

            background_tasks.add_task(
                lambda uid=img_uuid, rp=str(review_path), pred=prediction: None
            )
            # DB 저장 (pending)
            await _save_detection_event(
                rag=rag,
                event_uuid=img_uuid,
                image_path=str(review_path),
                pest_code=prediction["pest_code"],
                confidence=prediction["confidence"],
                is_low_conf=True,
                review_status="pending",
            )
            return {
                "detected": False,
                "message": "저화질 이미지입니다. 관리자 검수 후 반영됩니다.",
            }

        # 고신뢰도 - DB 저장 (approved)
        await _save_detection_event(
            rag=rag,
            event_uuid=img_uuid,
            image_path=str(img_path),
            pest_code=prediction["pest_code"],
            confidence=prediction["confidence"],
            is_low_conf=False,
            review_status="approved",
        )
        background_tasks.add_task(img_path.unlink, missing_ok=True)
        context_pest = prediction["pest_code"]

    # 2. 오디오 저장
    audio_ext = Path(audio.filename).suffix
    audio_path = settings.upload_dir / f"{uuid.uuid4()}{audio_ext}"
    wav_path = audio_path.with_suffix(".wav")
    mp3_path = settings.upload_dir / f"{uuid.uuid4()}.mp3"

    with open(audio_path, "wb") as f:
        f.write(await audio.read())
    background_tasks.add_task(audio_path.unlink, missing_ok=True)
    background_tasks.add_task(wav_path.unlink, missing_ok=True)
    background_tasks.add_task(mp3_path.unlink, missing_ok=True)

    # 3. RAG 풀 파이프라인 (STT → LLM → TTS)
    mode = 2 if context_pest else 1
    try:
        response_text, _ = await rag.forward(
            query=str(audio_path),
            mode=mode,
            lang=language,
            analysis_result=context_pest,
            output_path=str(mp3_path),
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )

    if not mp3_path.exists():
        return JSONResponse(
            status_code=500,
            content={"error": "TTS 파일 생성에 실패했습니다."},
        )

    # 4. MP3 binary + X-Response-Text 헤더 반환
    return FileResponse(
        mp3_path,
        media_type="audio/mpeg",
        headers={"X-Response-Text": quote(response_text)},
    )
