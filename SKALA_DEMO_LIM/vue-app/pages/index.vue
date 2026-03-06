<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

/* ─── Helpers ─── */
function getSupportedMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
}

function blobExtension(mimeType) {
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
}

function formatDuration(sec) {
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = (sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

/* ─── DOM refs ─── */
const videoRef = ref(null);
const canvasRef = ref(null);
const langRef = ref(null);

/* ─── Internal refs (non-reactive) ─── */
const streamRef = ref(null);
const recorderRef = ref(null);
const chunksRef = ref([]);
const capturedPhotoRef = ref(null);
const timerRef = ref(null);
const audioRef = ref(null);

/* ─── State ─── */
const appState = ref("idle");
const recSeconds = ref(0);
const responseText = ref("");
const responseAudioUrl = ref(null);
const showResponse = ref(false);
const flashActive = ref(false);
const cameraError = ref("");
const language = ref("ko");
const langOpen = ref(false);
const testing = ref(true);

/* ─── Derived state ─── */
const isRecordingA = computed(() => appState.value === "recording-a");
const isRecordingB = computed(() => appState.value === "recording-b");
const isProcessing = computed(() => appState.value === "processing");

const langLabels = {
  ko: "🇰🇷 한국어",
  vi: "🇻🇳 Tiếng Việt",
  th: "🇹🇭 ภาษาไทย",
};

/* ─── Initialize camera ─── */
onMounted(async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "environment",
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30 },
      },
      audio: true,
    });
    streamRef.value = stream;
    if (videoRef.value) {
      videoRef.value.srcObject = stream;
    }
  } catch {
    cameraError.value =
      "Camera & microphone access required.\nPlease allow permissions and reload.";
  }
});

onUnmounted(() => {
  streamRef.value?.getTracks().forEach((t) => t.stop());
  if (timerRef.value) clearInterval(timerRef.value);
  langOpenCleanup();
});

/* ─── Close language dropdown on outside click ─── */
let outsideClickHandler = null;

function langOpenCleanup() {
  if (outsideClickHandler) {
    document.removeEventListener("mousedown", outsideClickHandler);
    outsideClickHandler = null;
  }
}

watch(langOpen, (newVal) => {
  langOpenCleanup();
  if (newVal) {
    outsideClickHandler = (e) => {
        if (langRef.value && !langRef.value.contains(e.target)) {
        langOpen.value = false;
      }
    };
    document.addEventListener("mousedown", outsideClickHandler);
  }
});

/* ─── Audio helpers ─── */
function stopAudio() {
  if (audioRef.value) {
    audioRef.value.pause();
    audioRef.value.currentTime = 0;
    audioRef.value = null;
  }
  window.speechSynthesis?.cancel();
}

function speakTTS(text, onDone) {
  if (!("speechSynthesis" in window)) {
    onDone?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
    utt.lang = ({ ko: "ko-KR", vi: "vi-VN", th: "th-TH" })[language.value] ?? "ko-KR";
  utt.rate = 1.05;
  utt.pitch = 1.0;
  utt.volume = 1.0;
  if (onDone) utt.onend = onDone;
  window.speechSynthesis.speak(utt);
}

function playAudioUrl(url, onDone) {
  stopAudio();
  const audio = new Audio(url);
  audioRef.value = audio;
  audio.onended = () => {
    audioRef.value = null;
    onDone?.();
  };
  audio.onerror = () => {
    audioRef.value = null;
    onDone?.();
  };
  audio.play().catch(() => onDone?.());
}

function displayResponse(text, audioBlobUrl) {
  responseText.value = text;
  responseAudioUrl.value = audioBlobUrl ?? null;
  showResponse.value = true;
  if (audioBlobUrl) {
    playAudioUrl(audioBlobUrl, () => {
      showResponse.value = false;
    });
  } else {
    speakTTS(text, () => {
      showResponse.value = false;
    });
  }
}

function replayResponse() {
  if (responseAudioUrl.value) {
    playAudioUrl(responseAudioUrl.value, () => {
      showResponse.value = false;
    });
  } else {
    speakTTS(responseText.value, () => {
      showResponse.value = false;
    });
  }
}

/* ─── Recording helpers ─── */
function startRecording() {
  const stream = streamRef.value;
  if (!stream) return false;

  const audioTracks = stream.getAudioTracks();
  if (!audioTracks.length) return false;

  chunksRef.value = [];
  const audioStream = new MediaStream(audioTracks);
  const mimeType = getSupportedMimeType();
  const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : {});

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunksRef.value.push(e.data);
  };

  recorderRef.value = recorder;
  recorder.start(100);

  recSeconds.value = 0;
  timerRef.value = setInterval(() => {
    recSeconds.value++;
  }, 1000);

  return true;
}

function stopRecording() {
  return new Promise((resolve) => {
    if (timerRef.value) {
      clearInterval(timerRef.value);
      timerRef.value = null;
    }

    const recorder = recorderRef.value;
    if (!recorder || recorder.state === "inactive") {
      resolve(new Blob([], { type: "audio/webm" }));
      return;
    }
    recorder.onstop = () => {
      const mime = recorder.mimeType || "audio/webm";
      resolve(new Blob(chunksRef.value, { type: mime }));
    };
    recorder.stop();
  });
}

/* ─── Photo capture with shutter flash ─── */
function capturePhoto() {
  const video = videoRef.value;
  const canvas = canvasRef.value;
  if (!video || !canvas || !video.videoWidth) return null;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d")?.drawImage(video, 0, 0);

  flashActive.value = true;
  setTimeout(() => {
    flashActive.value = false;
  }, 200);

  return canvas.toDataURL("image/jpeg", 0.85);
}

/* ─── Testing mode: sample mp3 per language ─── */
const SAMPLE_AUDIO = {
  ko: "/korean_sample.mp3",
  vi: "/vat_sample.mp3",
  th: "/thai_sample.mp3",
};

const SAMPLE_TEXT = {
  ko: "테스트 응답입니다.",
  vi: "Đây là phản hồi thử nghiệm.",
  th: "นี่คือการตอบกลับทดสอบ",
};

/* ─── Shared: call /analyze with optional image ─── */
async function callAnalyze(audio, photo) {
  if (testing.value) {
    const audioUrl = SAMPLE_AUDIO[language.value] ?? SAMPLE_AUDIO.ko;
    const text = SAMPLE_TEXT[language.value] ?? SAMPLE_TEXT.ko;
    displayResponse(text, audioUrl);
    return;
  }

  const fd = new FormData();
  fd.append("audio", audio, `recording.${blobExtension(audio.type)}`);
  fd.append("language", language.value);

  if (photo) {
    const imgBlob = await fetch(photo).then((r) => r.blob());
    fd.append("image", imgBlob, "photo.jpg");
  }

  const backendUrl = import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8113";
  const res = await fetch(`${backendUrl}/api/analyze`, { method: "POST", body: fd });
  if (!res.ok) throw new Error("Bad response");

  const contentType = res.headers.get("Content-Type") ?? "";
  if (contentType.includes("audio")) {
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const text = decodeURIComponent(res.headers.get("X-Response-Text") ?? "");
    displayResponse(text || "Response received.", blobUrl);
  } else {
    const data = await res.json();
    displayResponse(data.text ?? "No response received.");
  }
}

/* ─── Button A: Ask (voice only) ─── */
async function handleButtonA() {
  if (appState.value === "recording-a") {
    appState.value = "processing";
    const audio = await stopRecording();
    try {
      await callAnalyze(audio); // no image
    } catch {
      displayResponse("Could not get a response. Please try again.");
    }
    appState.value = "idle";
    return;
  }

  if (appState.value === "idle") {
    if (startRecording()) appState.value = "recording-a";
  }
}

/* ─── Button B: Analyze (photo + voice) ─── */
async function handleButtonB() {
  if (appState.value === "recording-b") {
    appState.value = "processing";
    const audio = await stopRecording();
    try {
      await callAnalyze(audio, capturedPhotoRef.value); // with image
    } catch {
      displayResponse("Could not analyze the scene. Please try again.");
    }
    appState.value = "idle";
    return;
  }

  if (appState.value === "idle") {
    capturedPhotoRef.value = capturePhoto();
    if (startRecording()) appState.value = "recording-b";
  }
}

/* ─── Button C: Navigate ─── */
function handleButtonC() {
  router.push("/new-window");
}

/* ─── Dismiss response ─── */
function dismissResponse() {
  showResponse.value = false;
  stopAudio();
}

function selectLanguage(code) {
  language.value = code;
  langOpen.value = false;
}
</script>

<template>
  <main
    class="relative w-screen h-screen overflow-hidden bg-black select-none"
    style="font-family: var(--font-sys)"
  >
    <!-- Camera feed -->
    <video
      ref="videoRef"
      autoplay
      playsinline
      muted
      class="absolute inset-0 w-full h-full object-cover"
      style="transform: scaleX(-1)"
    />

    <!-- Hidden canvas -->
    <canvas ref="canvasRef" class="hidden" />

    <!-- Shutter flash -->
    <div
      v-if="flashActive"
      class="absolute inset-0 bg-white shutter-flash pointer-events-none z-50"
    />

    <!-- Camera error overlay -->
    <div
      v-if="cameraError"
      class="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-40"
    >
      <div
        class="response-panel p-7 max-w-xs text-center"
        style="animation: slide-up 0.3s ease forwards"
      >
        <div class="text-4xl mb-4">📷</div>
        <p class="text-white/90 text-sm leading-relaxed whitespace-pre-line">
          {{ cameraError }}
        </p>
      </div>
    </div>

    <!-- UI Overlay -->
    <div class="absolute inset-0 pointer-events-none z-10">
      <!-- Top-left: Button C -->
      <button
        @click="handleButtonC"
        class="glass-btn absolute pointer-events-auto"
        :style="{ top: 'clamp(16px, 3vh, 28px)', left: 'clamp(16px, 3vw, 28px)' }"
        aria-label="Menu"
      >
        <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="white" stroke-width="1.9" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="white" stroke-width="1.9" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="white" stroke-width="1.9" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="white" stroke-width="1.9" />
        </svg>
      </button>

      <!-- Top-right: Buttons B, A + language dropdown -->
      <div
        class="absolute flex flex-col items-end gap-2.5 pointer-events-auto"
        :style="{ top: 'clamp(16px, 3vh, 28px)', right: 'clamp(16px, 3vw, 28px)' }"
      >
        <!-- Buttons row -->
        <div class="flex items-center gap-3">
          <!-- Button B — Scan / Analyze -->
          <button
            @click="handleButtonB"
            :disabled="isRecordingA || isProcessing"
            :class="['glass-btn', isRecordingB ? 'is-recording' : '']"
            :aria-label="isRecordingB ? 'Stop analyzing' : 'Analyze scene'"
          >
            <template v-if="isRecordingB">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                <rect x="5" y="5" width="14" height="14" rx="3" />
              </svg>
            </template>
            <template v-else>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M15 3h4a2 2 0 0 1 2 2v4" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
                <path d="M9 3H5a2 2 0 0 0-2 2v4" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
                <path d="M15 21h4a2 2 0 0 0 2-2v-4" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
                <path d="M9 21H5a2 2 0 0 1-2-2v-4" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
                <circle cx="12" cy="12" r="3" stroke="white" stroke-width="1.9" />
              </svg>
            </template>
          </button>

          <!-- Button A — Ask -->
          <button
            @click="handleButtonA"
            :disabled="isRecordingB || isProcessing"
            :class="['glass-btn', isRecordingA ? 'is-recording' : '']"
            :aria-label="isRecordingA ? 'Stop recording' : 'Ask a question'"
          >
            <template v-if="isRecordingA">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                <rect x="5" y="5" width="14" height="14" rx="3" />
              </svg>
            </template>
            <template v-else>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <rect x="9" y="1" width="6" height="12" rx="3" stroke="white" stroke-width="1.9" stroke-linejoin="round" />
                <path d="M5 11a7 7 0 0 0 14 0" stroke="white" stroke-width="1.9" stroke-linecap="round" />
                <line x1="12" y1="18" x2="12" y2="22" stroke="white" stroke-width="1.9" stroke-linecap="round" />
                <line x1="9" y1="22" x2="15" y2="22" stroke="white" stroke-width="1.9" stroke-linecap="round" />
              </svg>
            </template>
          </button>
        </div>

        <!-- Language dropdown -->
        <div ref="langRef" class="relative">
          <button
            @click="langOpen = !langOpen"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl"
            :style="{
              background: 'rgba(255,255,255,0.12)',
              backdropFilter: 'blur(20px) saturate(180%)',
              WebkitBackdropFilter: 'blur(20px) saturate(180%)',
              border: '1px solid rgba(255,255,255,0.22)',
              boxShadow: '0 4px 16px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.3)',
              fontSize: '12px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.88)',
              letterSpacing: '0.02em',
            }"
          >
            {{ langLabels[language] }}
            <svg
              width="10" height="10" viewBox="0 0 24 24" fill="none"
              :style="{ transform: langOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.18s' }"
            >
              <path d="M6 9l6 6 6-6" stroke="rgba(255,255,255,0.7)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>

          <!-- Dropdown menu -->
          <div
            v-if="langOpen"
            class="absolute top-full mt-1.5 right-0 rounded-2xl overflow-hidden z-50"
            :style="{
              minWidth: '148px',
              background: 'rgba(20,20,22,0.92)',
              backdropFilter: 'blur(32px) saturate(180%)',
              WebkitBackdropFilter: 'blur(32px) saturate(180%)',
              border: '1px solid rgba(255,255,255,0.14)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.45)',
              animation: 'slide-up 0.16s ease forwards',
            }"
          >
            <button
              v-for="(lang, i) in [
                { code: 'ko', label: '🇰🇷 한국어' },
                { code: 'vi', label: '🇻🇳 Tiếng Việt' },
                { code: 'th', label: '🇹🇭 ภาษาไทย' },
              ]"
              :key="lang.code"
              @click="selectLanguage(lang.code)"
              class="w-full text-left px-3.5 py-2.5 flex items-center justify-between"
              :style="{
                fontSize: '13px',
                color: language === lang.code ? 'white' : 'rgba(255,255,255,0.6)',
                background: language === lang.code ? 'rgba(255,255,255,0.1)' : 'transparent',
                borderTop: i > 0 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                transition: 'background 0.12s',
              }"
            >
              <span>{{ lang.label }}</span>
              <svg v-if="language === lang.code" width="11" height="11" viewBox="0 0 24 24" fill="none">
                <path d="M5 12l5 5L20 7" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Top-center: Testing toggle + Recording indicator -->
      <div
        class="absolute left-1/2 flex flex-col items-center gap-2 pointer-events-auto"
        :style="{ top: 'clamp(16px, 3vh, 28px)', transform: 'translateX(-50%)' }"
      >
        <!-- Testing toggle -->
        <button
          @click="testing = !testing"
          class="flex items-center gap-2 px-3 py-1.5 rounded-xl"
          :style="{
            background: testing ? 'rgba(255,255,255,0.13)' : 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(20px) saturate(180%)',
            WebkitBackdropFilter: 'blur(20px) saturate(180%)',
            border: testing ? '1px solid rgba(255,255,255,0.25)' : '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 4px 16px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.25)',
            fontSize: '12px',
            fontWeight: 600,
            color: testing ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.28)',
            transition: 'all 0.2s ease',
            whiteSpace: 'nowrap',
          }"
          :title="testing ? 'Testing mode ON — using fake responses' : 'Live mode — using real backend'"
        >
          <div
            :style="{
              width: '26px', height: '15px', borderRadius: '999px',
              background: testing ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.15)',
              position: 'relative', transition: 'background 0.2s', flexShrink: 0,
            }"
          >
            <div :style="{
              position: 'absolute', top: '2px',
              left: testing ? '13px' : '2px',
              width: '11px', height: '11px', borderRadius: '50%',
              background: testing ? '#000' : 'rgba(255,255,255,0.45)',
              transition: 'left 0.2s cubic-bezier(0.34,1.56,0.64,1)',
            }" />
          </div>
          Testing
        </button>

        <!-- Recording indicator -->
        <div v-if="isRecordingA || isRecordingB" style="animation: slide-up 0.25s ease forwards">
          <div class="glass-pill pointer-events-none">
            <div class="flex items-center gap-[3px]" style="height: 18px">
              <div class="wave-dot" />
              <div class="wave-dot" />
              <div class="wave-dot" />
              <div class="wave-dot" />
              <div class="wave-dot" />
            </div>
            <span class="text-white text-sm font-medium" style="letter-spacing: 0.02em">
              {{ isRecordingA ? "Listening" : "Scanning" }} · {{ formatDuration(recSeconds) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Center: Processing spinner -->
      <div
        v-if="isProcessing"
        class="absolute left-1/2 top-1/2"
        style="transform: translate(-50%, -50%); animation: slide-up 0.2s ease forwards"
      >
        <div class="processing-panel">
          <div class="spinner" />
          <span class="text-white text-sm font-medium" style="letter-spacing: 0.01em">
            Processing…
          </span>
        </div>
      </div>

      <!-- Bottom-left: Response text panel -->
      <div
        v-if="showResponse && responseText"
        class="absolute pointer-events-auto slide-up"
        :style="{
          bottom: 'clamp(24px, 5vh, 40px)',
          left: 'clamp(16px, 3vw, 28px)',
          maxWidth: 'min(520px, 58vw)',
        }"
      >
        <div class="response-panel p-4 pr-10 relative">
          <!-- Dismiss -->
          <button
            @click="dismissResponse"
            class="absolute top-3 right-3 w-6 h-6 rounded-full flex items-center justify-center"
            style="background: rgba(255,255,255,0.15)"
            aria-label="Dismiss"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="white">
              <line x1="1" y1="1" x2="9" y2="9" stroke="white" stroke-width="1.6" stroke-linecap="round" />
              <line x1="9" y1="1" x2="1" y2="9" stroke="white" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </button>

          <!-- Label -->
          <div class="flex items-center gap-2 mb-2">
            <div class="w-1.5 h-1.5 rounded-full bg-blue-400" />
            <span
              class="text-white/60 uppercase tracking-widest"
              style="font-size: 10px; letter-spacing: 0.1em"
            >
              Response
            </span>
          </div>

          <!-- Text -->
          <p class="text-white text-sm leading-relaxed">{{ responseText }}</p>

          <!-- Replay -->
          <button
            @click="replayResponse"
            class="mt-3 flex items-center gap-1.5 text-white/50 hover:text-white/80 transition-colors"
            style="font-size: 11px"
            aria-label="Replay audio"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
              <polygon points="5,3 19,12 5,21" stroke="currentColor" stroke-width="2" stroke-linejoin="round" fill="currentColor" />
            </svg>
            Replay
          </button>
        </div>
      </div>

      <!-- Subtle vignette -->
      <div
        class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.35) 100%)"
      />
    </div>
  </main>
</template>