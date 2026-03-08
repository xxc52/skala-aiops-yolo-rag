import io
import json

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import text

from app.config import settings
from app.constants import PEST_NAME_MAP
from app.services.report_service import generate_report

router = APIRouter(prefix="/api/manager")


# ─────────────────────────────────────────
# 검수 큐
# ─────────────────────────────────────────

@router.get("/images")
async def list_pending_images(request: Request):
    """review_status='pending' 이미지 목록 반환"""
    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        result = await session.execute(text("""
            SELECT uuid, image_path, confidence, pest_code, created_at
            FROM detection_events
            WHERE review_status = 'pending'
            ORDER BY created_at DESC
        """))
        rows = result.fetchall()

    images = [
        {
            "uuid": r[0],
            "imageUrl": f"/api/manager/image/{r[0]}",
            "confidenceScore": r[2],
            "pest_code": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]
    return {"images": images}


@router.get("/image/{img_uuid}")
async def get_image(img_uuid: str):
    """review 디렉토리에서 이미지 파일 서빙"""
    img_path = settings.review_dir / f"{img_uuid}.jpg"
    if not img_path.exists():
        return JSONResponse(status_code=404, content={"error": "이미지를 찾을 수 없습니다."})
    return FileResponse(str(img_path), media_type="image/jpeg")


@router.post("/update")
async def update_labels(request: Request):
    """관리자 검수 결과 일괄 업데이트"""
    body = await request.json()
    updates = body.get("updates", [])

    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        for item in updates:
            await session.execute(text("""
                UPDATE detection_events
                SET human_label = :label,
                    review_status = 'relabeled',
                    reviewed_at = NOW()
                WHERE uuid = :uuid
            """), {"label": item["category"], "uuid": item["uuid"]})
        await session.commit()

    return {"updatedCount": len(updates)}


@router.get("/export")
async def export_dataset(request: Request):
    """재라벨링 완료 데이터를 JSONL로 export"""
    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        result = await session.execute(text("""
            SELECT image_path, human_label, confidence, created_at
            FROM detection_events
            WHERE review_status = 'relabeled'
            ORDER BY created_at DESC
        """))
        rows = result.fetchall()

    lines = []
    for r in rows:
        lines.append(json.dumps({
            "image_path": r[0],
            "label": r[1],
            "confidence": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
        }, ensure_ascii=False))

    content = "\n".join(lines)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/jsonl",
        headers={"Content-Disposition": "attachment; filename=finetune_dataset.jsonl"},
    )


# ─────────────────────────────────────────
# 병해충 클래스 목록
# ─────────────────────────────────────────

@router.get("/classes")
async def get_classes(request: Request):
    """YOLO 모델 클래스 목록 + 한글명 반환"""
    classifier = request.app.state.classifier
    model_classes = classifier.class_names  # {0: "1", 1: "3", ...}
    classes = [
        {"code": code, "name": PEST_NAME_MAP.get(code, code)}
        for code in model_classes.values()
    ]
    # 코드 오름차순 정렬 (정상=999는 마지막)
    classes.sort(key=lambda x: int(x["code"]) if x["code"].isdigit() else 9999)
    return {"classes": classes}


# ─────────────────────────────────────────
# AI 운영 보고서
# ─────────────────────────────────────────

@router.get("/report")
async def get_report(request: Request, type: str = "weekly"):
    """최근 보고서 조회, 없으면 생성"""
    if type not in ("weekly", "monthly"):
        return JSONResponse(status_code=400, content={"error": "type은 weekly 또는 monthly여야 합니다."})

    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        result = await session.execute(text("""
            SELECT content, period_start, period_end, created_at
            FROM aiops_reports
            WHERE period_type = :pt
            ORDER BY created_at DESC
            LIMIT 1
        """), {"pt": type})
        row = result.fetchone()

    if row:
        return {
            "content": row[0],
            "period_start": row[1].isoformat(),
            "period_end": row[2].isoformat(),
            "created_at": row[3].isoformat(),
        }

    # 없으면 생성
    threshold = getattr(request.app.state, "conf_threshold", 0.4)
    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        return await generate_report(session, rag.client, type, threshold)


@router.post("/report/generate")
async def force_generate_report(request: Request):
    """보고서 강제 생성"""
    body = await request.json()
    period_type = body.get("type", "weekly")
    if period_type not in ("weekly", "monthly"):
        return JSONResponse(status_code=400, content={"error": "type은 weekly 또는 monthly여야 합니다."})

    threshold = getattr(request.app.state, "conf_threshold", 0.4)
    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        return await generate_report(session, rag.client, period_type, threshold)


# ─────────────────────────────────────────
# 모델 운영 설정
# ─────────────────────────────────────────

@router.get("/config")
async def get_config(request: Request):
    """현재 신뢰도 임계값 반환"""
    threshold = getattr(request.app.state, "conf_threshold", 0.4)
    return {"conf_threshold": threshold}


@router.post("/config")
async def update_config(request: Request):
    """신뢰도 임계값 변경"""
    body = await request.json()
    new_threshold = float(body.get("conf_threshold", 0.4))
    if not (0.0 < new_threshold < 1.0):
        return JSONResponse(status_code=400, content={"error": "임계값은 0~1 사이여야 합니다."})

    rag = request.app.state.rag
    async with rag.SessionLocal() as session:
        await session.execute(text("""
            UPDATE model_config SET value = :val WHERE key = 'conf_threshold'
        """), {"val": str(new_threshold)})
        await session.commit()

    request.app.state.conf_threshold = new_threshold
    return {"updated": True, "conf_threshold": new_threshold}
