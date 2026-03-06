import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    upload_dir: Path = Path("./agent_storage")
    model_path: str = "./saved_model/best.pt"
    prescription_agent_url: str = "http://localhost:8001/v1/agent/prescription"
    confidence_threshold: float = 0.6

    @property
    def log_file(self) -> Path:
        return self.upload_dir / "detection_log.jsonl"


settings = Settings()
settings.upload_dir.mkdir(exist_ok=True)

