"""
탐지 이력 저장 레이어.
추후 DB 연동 시 save_detection_log() 함수 내부만 교체하면 됨.
"""
import json
from datetime import datetime

from app.config import settings
from app.schemas import ClassificationResult


def save_detection_log(result: ClassificationResult) -> None:
    """탐지 이력을 저장한다. 현재는 JSONL 파일에 append."""
    record = result.model_dump()
    record["logged_at"] = datetime.now().isoformat()

    with open(settings.log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
