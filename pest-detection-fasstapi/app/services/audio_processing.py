import os
import subprocess

import requests
from dotenv import load_dotenv
from faster_whisper import WhisperModel

load_dotenv()


class audio_processing:
    def __init__(self):
        self.model_name = os.getenv("WHISPER_MODEL", "small")
        self.device = os.getenv("AUDIO_DEVICE", "cpu")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = WhisperModel(self.model_name, device=self.device, compute_type="int8")

    def convert_webm_to_wav(self, webm_path: str, wav_path: str) -> None:


        # webm 파일을 wav 파일로 변환합니다.
        # ffmpeg 를 직접 호출합니다. (pydub보다 설치/런타임 안정성이 높습니다)
        # STT 안정성을 위해 모노 채널 + 16kHz로 맞춰줍니다.

        if not os.path.exists(webm_path):
            raise FileNotFoundError(f"Input not found: {webm_path}")

        out_dir = os.path.dirname(wav_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = [
        "ffmpeg",
        "-y", # overwrite
        "-i", webm_path,
        "-ac", "1", # mono
        "-ar", "16000", # 16kHz
        "-vn", # no video
        wav_path,
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg convert failed: {proc.stderr.strip()}")
    
    def convert_mp4_to_wav(self, mp4_path: str, wav_path: str) -> None:
        """
        MP4 파일에서 음성을 추출하여 16kHz, Mono 채널의 WAV 파일로 변환합니다.
        (STT 엔진 최적화 설정)
        """

        # 1. 입력 파일 존재 확인
        if not os.path.exists(mp4_path):
            raise FileNotFoundError(f"Input not found: {mp4_path}")

        # 2. 출력 디렉토리 생성
        out_dir = os.path.dirname(wav_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # 3. ffmpeg 명령어 구성
        # -y: 기존 파일 덮어쓰기
        # -i: 입력 파일 경로
        # -ac 1: 오디오 채널을 1개(Mono)로 설정
        # -ar 16000: 샘플링 레이트를 16000Hz(16kHz)로 설정
        # -vn: 비디오 스트림 제외 (음성만 추출)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", mp4_path,
            "-ac", "1",
            "-ar", "16000",
            "-vn",
            wav_path,
        ]

        # 4. 프로세스 실행
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # 5. 에러 처리
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg convert failed: {proc.stderr.strip()}")

    def transcribe_audio_file_local(self, file_path: str) -> str:
        """
        로컬 Whisper 모델로 STT를 수행합니다.
        (faster-whisper 사용)
        """
        if os.path.exists(file_path):
        # faster-whisper는 segments generator를 반환합니다.
            segments, info = self.model.transcribe(
            file_path,
            beam_size=5,
            vad_filter=True, # 무음 제거(대체로 품질/속도에 도움)
            )
            text = "".join(seg.text for seg in segments).strip()
            return text

    def transcribe_audio_file(self, file_path: str) -> str:
        """
        기존 코드 호환을 위한 래퍼.
        (예전에 transcribe_audio_file만 사용하던 코드가 있다면 그대로 동작하도록)
        """
        return self.transcribe_audio_file_local(file_path)
    
    def text_to_speech(self, text: str, output_path: str = "output.mp3"):
        url = "https://api.openai.com/v1/audio/speech"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "tts-1",
            "input": text,
            "voice": "nova"
        }

        response = requests.post(url, headers=headers, json=data)
        print(f"TTS 응답 상태 코드: {response.status_code}")

        if response.status_code != 200:
            raise Exception(f"TTS 요청 실패: {response.status_code} - {response.text}")

        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path