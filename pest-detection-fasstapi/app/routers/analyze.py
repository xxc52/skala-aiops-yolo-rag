import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.repositories.detection_log import save_detection_log
from app.schemas import ClassificationResult

router = APIRouter(prefix="/api")


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

    # 1. 이미지 유무에 따른 시나리오 분기
    context_pest = None
    if image and image.filename:
        img_ext = Path(image.filename).suffix
        img_path = settings.upload_dir / f"{uuid.uuid4()}{img_ext}"
        with open(img_path, "wb") as f:
            f.write(await image.read())
        background_tasks.add_task(img_path.unlink, missing_ok=True)

        prediction = classifier.predict(str(img_path))
        if not prediction:
            return {"detected": False, "message": "병충해가 감지되지 않았습니다. 선명하게 다시 촬영해 주세요."}

        context_pest = prediction.get("pest_code")
        save_detection_log(ClassificationResult(
            img_path=str(img_path),
            pest_code=prediction["pest_code"],
            confidence=prediction["confidence"],
        ))

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
    response_text, _ = await rag.forward(
        query=str(audio_path),
        mode=mode,
        lang=language,
        analysis_result=context_pest,
        output_path=str(mp3_path),
    )

    # 4. MP3 binary + X-Response-Text 헤더 반환
    return FileResponse(
        mp3_path,
        media_type="audio/mpeg",
        headers={"X-Response-Text": quote(response_text)},
    )
