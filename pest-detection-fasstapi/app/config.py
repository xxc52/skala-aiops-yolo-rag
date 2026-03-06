import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "./agent_storage"))
    model_path: str = os.getenv("MODEL_PATH", str(Path(__file__).resolve().parents[1] / "best.pt"))
    prescription_agent_url: str = os.getenv("PRESCRIPTION_AGENT_URL", "http://localhost:8001/v1/agent/prescription")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

    @property
    def log_file(self) -> Path:
        return self.upload_dir / "detection_log.jsonl"


settings = Settings()
settings.upload_dir.mkdir(exist_ok=True)

