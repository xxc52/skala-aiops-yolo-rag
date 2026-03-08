<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { tokens } from "~/utils/tokens"
import ThemeDropdown from '../components/ThemeDropdown.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ImageCard from '../components/ImageCard.vue'

const backendUrl = ""  // same-origin proxy via vite

function shortUUID(uuid) {
  return uuid.slice(0, 8).toUpperCase();
}

/* ─── State ─── */
const theme = ref("light");
const systemDark = ref(false);
const activeTab = ref("inspect");

const ftEpochs = ref(10);
const ftLR = ref("1e-4");
const ftBatch = ref(16);
const ftTraining = ref(false);
const ftProgress = ref(0);
const ftDone = ref(false);
const ftTimer = ref(null);

const testing = ref(true);
const images = ref([]);
const selections = ref({});
const isLoading = ref(true);
const fetchError = ref("");
const isSending = ref(false);
const cleared = ref(false);
const toast = ref(null);
const toastTimer = ref(null);

// 병해충 클래스 목록
const pestClasses = ref([]);

// 보고서 탭
const reportType = ref("weekly");
const reportContent = ref("");
const reportMeta = ref(null);
const isLoadingReport = ref(false);
const isGeneratingReport = ref(false);

// 설정 탭
const currentThreshold = ref(0.4);
const editingThreshold = ref(0.4);
const isSavingThreshold = ref(false);

/* ─── Derived ─── */
const isDark = computed(
  () => theme.value === "dark" || (theme.value === "device" && systemDark.value)
);
const t = computed(() => tokens(isDark.value));
const pendingCount = computed(() => Object.keys(selections.value).length);
const isDone = computed(
  () =>
    cleared.value ||
    (!isLoading.value && !fetchError.value && images.value.length === 0)
);
const canSend = computed(
  () => pendingCount.value > 0 && !isSending.value && !isDone.value
);

/* ─── Detect system theme ─── */
onMounted(async () => {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  systemDark.value = mq.matches;
  const handler = (e) => { systemDark.value = e.matches; };
  mq.addEventListener("change", handler);
  onUnmounted(() => mq.removeEventListener("change", handler));

  // 병해충 클래스 목록 fetch
  try {
    const res = await fetch(`${backendUrl}/api/manager/classes`);
    const data = await res.json();
    pestClasses.value = data.classes ?? [];
  } catch {
    pestClasses.value = [
      { code: "1", name: "갈색반점병" },
      { code: "3", name: "검은점무늬병" },
      { code: "7", name: "그을음병" },
      { code: "11", name: "잎마름병" },
      { code: "12", name: "잎말이나방" },
      { code: "13", name: "줄기썩음병" },
      { code: "15", name: "총채벌레" },
      { code: "16", name: "탄저병" },
      { code: "17", name: "흰가루병" },
      { code: "20", name: "점무늬병" },
      { code: "999", name: "정상" },
    ];
  }

  // 설정 탭 - 현재 threshold 로드
  try {
    const res = await fetch(`${backendUrl}/api/manager/config`);
    const data = await res.json();
    currentThreshold.value = data.conf_threshold;
    editingThreshold.value = data.conf_threshold;
  } catch {}
});

/* ─── Fake data for testing mode (no server needed) ─── */
const FAKE_IMAGES = [
  { uuid: "550e8400-e29b-41d4-a716-446655440001", imageUrl: "/sample_img1.jpg", confidenceScore: 0.12, category: null, updated: false },
  { uuid: "550e8400-e29b-41d4-a716-446655440002", imageUrl: "/sample_img2.jpg", confidenceScore: 0.38, category: null, updated: false },
  { uuid: "550e8400-e29b-41d4-a716-446655440003", imageUrl: "/sample_img3.jpg", confidenceScore: 0.47, category: null, updated: false },
  { uuid: "550e8400-e29b-41d4-a716-446655440004", imageUrl: "/sample_img1.jpg", confidenceScore: 0.29, category: null, updated: false },
  { uuid: "550e8400-e29b-41d4-a716-446655440005", imageUrl: "/sample_img2.jpg", confidenceScore: 0.05, category: null, updated: false },
]

/* ─── Fetch images ─── */
async function fetchImages() {
  isLoading.value = true;
  fetchError.value = "";
  images.value = [];
  selections.value = {};
  cleared.value = false;

  if (testing.value) {
    images.value = FAKE_IMAGES.map((img) => ({ ...img }));
    isLoading.value = false;
    return;
  }

  try {
    const res = await fetch(`${backendUrl}/api/manager/images`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    images.value = data.images ?? [];
  } catch {
    fetchError.value = "데이터베이스에 연결할 수 없습니다. .env의 DB 정보를 확인해 주세요.";
  } finally {
    isLoading.value = false;
  }
}

watch(testing, fetchImages, { immediate: true });

/* ─── 보고서 fetch ─── */
async function fetchReport() {
  isLoadingReport.value = true;
  reportContent.value = "";
  reportMeta.value = null;
  try {
    const res = await fetch(`${backendUrl}/api/manager/report?type=${reportType.value}`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    reportContent.value = data.content;
    reportMeta.value = { period_start: data.period_start, period_end: data.period_end, created_at: data.created_at };
  } catch {
    reportContent.value = "";
  } finally {
    isLoadingReport.value = false;
  }
}

watch(reportType, fetchReport);

async function generateReport() {
  isGeneratingReport.value = true;
  try {
    const res = await fetch(`${backendUrl}/api/manager/report/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: reportType.value }),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    reportContent.value = data.content;
    reportMeta.value = { period_start: data.period_start, period_end: data.period_end, created_at: data.created_at };
    showToast("success", "보고서가 생성되었습니다.");
  } catch {
    showToast("error", "보고서 생성에 실패했습니다.");
  } finally {
    isGeneratingReport.value = false;
  }
}

/* ─── 보고서 탭 활성화 시 자동 fetch ─── */
watch(activeTab, (tab) => {
  if (tab === "report") fetchReport();
});

/* ─── 설정 저장 ─── */
async function saveThreshold() {
  isSavingThreshold.value = true;
  try {
    const res = await fetch(`${backendUrl}/api/manager/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conf_threshold: editingThreshold.value }),
    });
    if (!res.ok) throw new Error();
    currentThreshold.value = editingThreshold.value;
    showToast("success", `임계값이 ${editingThreshold.value}으로 변경되었습니다.`);
  } catch {
    showToast("error", "저장에 실패했습니다.");
  } finally {
    isSavingThreshold.value = false;
  }
}

/* ─── Toast ─── */
function showToast(kind, msg) {
  if (toastTimer.value) clearTimeout(toastTimer.value);
  toast.value = { kind, message: msg };
  toastTimer.value = setTimeout(() => { toast.value = null; }, 3000);
}

/* ─── Handlers ─── */
function handleSelection(uuid, cat) {
  selections.value = { ...selections.value, [uuid]: cat };
}

async function handleSend() {
  const dirty = Object.keys(selections.value);
  if (!dirty.length) return;

  const updates = dirty.map((uuid) => ({
    uuid,
    category: selections.value[uuid],
    confidenceScore: images.value.find((img) => img.uuid === uuid)?.confidenceScore,
  }));

  isSending.value = true;

  if (testing.value) {
    const sentUuids = new Set(dirty);
    images.value = images.value.filter((img) => !sentUuids.has(img.uuid));
    selections.value = {};
    showToast("success", `${dirty.length}건이 업데이트되었습니다.`);
    isSending.value = false;
    return;
  }

  try {
    const res = await fetch(`${backendUrl}/api/manager/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ updates }),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    showToast("success", `${data.updatedCount}건이 업데이트되었습니다.`);
    const sentUuids = new Set(dirty);
    images.value = images.value.filter((img) => !sentUuids.has(img.uuid));
    selections.value = {};
  } catch {
    showToast("error", "전송에 실패했습니다. 다시 시도해 주세요.");
  } finally {
    isSending.value = false;
  }
}

function startFinetune() {
  if (ftTraining.value) return;
  ftTraining.value = true;
  ftProgress.value = 0;
  ftDone.value = false;

  let p = 0;
  ftTimer.value = setInterval(() => {
    p += Math.floor(Math.random() * 6) + 2;
    if (p >= 100) {
      p = 100;
      clearInterval(ftTimer.value);
      ftProgress.value = 100;
      ftTraining.value = false;
      ftDone.value = true;
    } else {
      ftProgress.value = p;
    }
  }, 400);
}

onUnmounted(() => {
  if (ftTimer.value) clearInterval(ftTimer.value);
  if (toastTimer.value) clearTimeout(toastTimer.value);
});

/* ─── 마크다운 → HTML 간이 변환 ─── */
function mdToHtml(md) {
  if (!md) return "";
  return md
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n\n/g, "<br/><br/>")
    .replace(/\n/g, "<br/>");
}
</script>

<template>
  <main
    class="relative w-screen h-screen overflow-hidden flex flex-col select-none"
    :style="{
      fontFamily: `-apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif`,
      background: t.bg,
      transition: 'background 0.3s ease',
    }"
  >
    <!-- Ambient background gradients -->
    <div class="absolute inset-0 pointer-events-none" :style="{ background: t.bgGrad }" />
    <div
      class="absolute inset-0 pointer-events-none"
      :style="{
        background: isDark
          ? `radial-gradient(circle at 15% 30%, rgba(120,80,200,0.18) 0%, transparent 40%),
             radial-gradient(circle at 85% 70%, rgba(40,90,200,0.14) 0%, transparent 40%),
             radial-gradient(circle at 50% 10%, rgba(180,140,255,0.08) 0%, transparent 35%),
             radial-gradient(circle at 70% 50%, rgba(60,180,200,0.06) 0%, transparent 35%),
             radial-gradient(ellipse at 30% 80%, rgba(100,40,180,0.10) 0%, transparent 40%)`
          : `radial-gradient(circle at 15% 30%, rgba(200,180,255,0.25) 0%, transparent 40%),
             radial-gradient(circle at 85% 70%, rgba(160,200,255,0.20) 0%, transparent 40%),
             radial-gradient(circle at 50% 10%, rgba(240,220,255,0.15) 0%, transparent 35%),
             radial-gradient(circle at 70% 50%, rgba(180,230,240,0.12) 0%, transparent 35%),
             radial-gradient(ellipse at 30% 80%, rgba(220,190,255,0.18) 0%, transparent 40%)`,
      }"
    />

    <!-- ══ HEADER ══ -->
    <header
      class="relative z-20 flex items-center flex-shrink-0"
      :style="{
        paddingLeft: 'clamp(16px, 3vw, 28px)',
        paddingRight: 'clamp(16px, 3vw, 28px)',
        paddingTop: 'clamp(14px, 2.5vh, 20px)',
        paddingBottom: 'clamp(12px, 2vh, 16px)',
        background: t.navBg,
        backdropFilter: 'blur(40px) saturate(180%)',
        WebkitBackdropFilter: 'blur(40px) saturate(180%)',
        borderBottom: `1px solid ${t.navBorder}`,
      }"
    >
      <!-- Back button -->
      <button
        @click="$router.back()"
        class="flex items-center gap-1.5 transition-opacity active:opacity-50"
        :style="{ fontSize: '16px', fontWeight: 400, color: t.tint, minWidth: '64px', flexShrink: 0 }"
      >
        <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
          <path d="M8.5 1.5L1.5 8.5l7 7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        뒤로
      </button>

      <!-- Title center -->
      <div class="flex-1 flex items-center justify-center gap-2">
        <h1 :style="{ fontSize: '17px', fontWeight: 600, color: t.textPrimary, letterSpacing: '-0.02em' }">
          관리자
        </h1>
        <div
          v-if="pendingCount > 0"
          class="rounded-full font-semibold"
          :style="{
            fontSize: '11px',
            color: 'white',
            background: t.tint,
            padding: '1px 8px',
            minWidth: '22px',
            textAlign: 'center',
            animation: 'slide-up 0.2s ease forwards',
          }"
        >
          {{ pendingCount }}
        </div>
      </div>

      <!-- Right controls -->
      <div class="flex items-center justify-end gap-2" :style="{ flexShrink: 0 }">
        <ThemeDropdown :theme="theme" :t="t" @update:theme="theme = $event" />

        <!-- Testing toggle -->
        <button
          @click="testing = !testing"
          class="flex items-center gap-2 px-3 py-1.5 rounded-xl transition-all"
          :style="{
            background: testing ? `${t.tint}20` : 'rgba(128,128,128,0.08)',
            border: `1px solid ${testing ? `${t.tint}40` : 'rgba(128,128,128,0.13)'}`,
            fontSize: '12px',
            fontWeight: 600,
            color: testing ? t.tint : t.textTertiary,
            backdropFilter: 'blur(12px)',
            transition: 'all 0.18s ease',
          }"
          :title="testing ? '테스트 데이터 사용 중 — 클릭하여 실제 DB로 전환' : '실제 DB 사용 중 — 클릭하여 테스트 데이터로 전환'"
        >
          <div
            :style="{
              width: '26px', height: '15px', borderRadius: '999px',
              background: testing ? t.tint : 'rgba(128,128,128,0.25)',
              position: 'relative', transition: 'background 0.2s ease', flexShrink: 0,
            }"
          >
            <div
              :style="{
                position: 'absolute', top: '2px',
                left: testing ? '13px' : '2px',
                width: '11px', height: '11px', borderRadius: '50%',
                background: 'white',
                transition: 'left 0.2s cubic-bezier(0.34,1.56,0.64,1)',
                boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
              }"
            />
          </div>
          테스트
        </button>
      </div>
    </header>

    <!-- ═══════ TAB: 검수 ═══════ -->
    <template v-if="activeTab === 'inspect'">
      <!-- Section title -->
      <div
        class="relative z-10 flex-shrink-0"
        :style="{
          paddingLeft: 'clamp(16px, 3vw, 28px)',
          paddingRight: 'clamp(16px, 3vw, 28px)',
          paddingTop: 'clamp(14px, 2vh, 20px)',
          paddingBottom: 'clamp(6px, 1vh, 10px)',
        }"
      >
        <h2 :style="{ fontSize: '22px', fontWeight: 700, color: t.textPrimary, letterSpacing: '-0.02em', marginBottom: '4px' }">
          검수 대기 항목
        </h2>
        <p :style="{ fontSize: '14px', color: t.textSecondary }">
          아래 이미지를 확인하고 올바른 카테고리를 선택하세요.
        </p>
      </div>

      <!-- Body -->
      <div class="relative z-10 flex-1 flex flex-col overflow-hidden">
        <!-- Loading skeletons -->
        <div v-if="isLoading" class="flex-1 flex items-center px-6 gap-4 overflow-hidden">
          <SkeletonCard v-for="i in 5" :key="i" :t="t" />
        </div>

        <!-- Error state -->
        <div v-else-if="fetchError" class="flex-1 flex items-center justify-center p-6">
          <div
            class="text-center px-8 py-8 max-w-sm w-full"
            :style="{
              borderRadius: '28px',
              background: t.errorCardBg,
              backdropFilter: 'blur(40px) saturate(180%)',
              WebkitBackdropFilter: 'blur(40px) saturate(180%)',
              border: `1px solid ${t.cardBorder}`,
              boxShadow: t.cardShadow,
            }"
          >
            <div class="text-4xl mb-4">⚠️</div>
            <p :style="{ fontSize: '15px', color: t.textSecondary, lineHeight: 1.55 }">{{ fetchError }}</p>
            <button
              @click="$router.go(0)"
              class="mt-5 px-6 py-2.5 rounded-xl transition-opacity active:opacity-80"
              :style="{ fontSize: '14px', fontWeight: 600, color: t.reloadColor, background: t.tint }"
            >
              새로고침
            </button>
          </div>
        </div>

        <!-- Done / empty state -->
        <div
          v-else-if="isDone"
          class="flex-1 flex flex-col items-center justify-center gap-4"
          style="animation: slide-up 0.32s ease forwards"
        >
          <div
            class="w-[72px] h-[72px] rounded-full flex items-center justify-center"
            :style="{
              background: t.emptyIconBg,
              backdropFilter: 'blur(20px)',
              border: `1px solid ${t.emptyIconBorder}`,
              boxShadow: t.cardShadow,
            }"
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path d="M5 12l5 5L20 7" :stroke="t.tint" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <div class="text-center">
            <p :style="{ fontSize: '18px', fontWeight: 600, color: t.emptyTitle, marginBottom: '6px' }">모두 완료!</p>
            <p :style="{ fontSize: '14px', color: t.emptyBody }">모든 항목이 분류되었습니다.</p>
          </div>
        </div>

        <!-- Image cards -->
        <div
          v-else-if="images.length > 0"
          class="flex-1 flex items-center gap-4 overflow-x-auto overflow-y-hidden"
          :style="{
            paddingLeft: 'clamp(16px, 3vw, 28px)',
            paddingRight: 'clamp(16px, 3vw, 28px)',
            paddingTop: 'clamp(8px, 1vh, 12px)',
            paddingBottom: 'clamp(100px, 18vh, 130px)',
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
          }"
        >
          <ImageCard
            v-for="rec in images"
            :key="rec.uuid"
            :record="rec"
            :selected="selections[rec.uuid] ?? ''"
            :is-dirty="rec.uuid in selections"
            :t="t"
            :categories="pestClasses"
            @change="handleSelection"
          />
          <div class="flex-shrink-0 w-2" />
        </div>
      </div>
    </template>

    <!-- Floating send button (inspect tab) -->
    <div
      v-if="activeTab === 'inspect'"
      class="absolute z-40 flex justify-center pointer-events-none"
      :style="{ bottom: 'max(calc(env(safe-area-inset-bottom, 12px) + 68px), 80px)', left: 0, right: 0 }"
    >
      <button
        @click="handleSend"
        :disabled="!canSend"
        class="pointer-events-auto flex items-center gap-2 transition-all active:scale-95"
        :style="{
          padding: '12px 28px',
          borderRadius: '999px',
          fontSize: '15px',
          fontWeight: 600,
          cursor: canSend ? 'pointer' : 'not-allowed',
          background: canSend
            ? (isDark ? 'rgba(255,255,255,0.90)' : 'rgba(0,0,0,0.85)')
            : (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'),
          border: canSend
            ? (isDark ? '1px solid rgba(255,255,255,0.35)' : '1px solid rgba(0,0,0,0.18)')
            : (isDark ? '1px solid rgba(255,255,255,0.10)' : '1px solid rgba(0,0,0,0.07)'),
          color: canSend
            ? (isDark ? 'rgba(0,0,0,0.88)' : 'rgba(255,255,255,0.95)')
            : t.textTertiary,
          backdropFilter: 'blur(30px) saturate(180%)',
          WebkitBackdropFilter: 'blur(30px) saturate(180%)',
          boxShadow: canSend ? '0 6px 28px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.4)' : 'none',
          transition: 'all 0.22s cubic-bezier(0.34,1.2,0.64,1)',
        }"
      >
        <template v-if="isSending">
          <div
            class="spinner"
            :style="{
              width: '13px', height: '13px',
              borderColor: `${isDark ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.3)'}`,
              borderTopColor: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.95)',
            }"
          />
          전송 중…
        </template>
        <template v-else>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
            <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M22 2L15 22 11 13 2 9l20-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          업데이트 전송
          <span
            v-if="pendingCount > 0 && !isDone"
            :style="{
              background: canSend ? 'rgba(128,128,128,0.2)' : 'rgba(128,128,128,0.12)',
              borderRadius: '999px',
              padding: '1px 8px',
              fontSize: '12px',
              fontWeight: 700,
            }"
          >
            {{ pendingCount }}
          </span>
        </template>
      </button>
    </div>

    <!-- ═══════ TAB: 파인튜닝 ═══════ -->
    <div
      v-if="activeTab === 'finetune'"
      class="relative z-10 flex-1 overflow-y-auto"
      :style="{
        paddingLeft: 'clamp(16px, 3vw, 28px)',
        paddingRight: 'clamp(16px, 3vw, 28px)',
        paddingTop: '20px',
        paddingBottom: '140px',
        scrollbarWidth: 'none',
      }"
    >
      <h2 :style="{ fontSize: '22px', fontWeight: 700, color: t.textPrimary, letterSpacing: '-0.02em', marginBottom: '4px' }">파인튜닝</h2>
      <p :style="{ fontSize: '14px', color: t.textSecondary, marginBottom: '24px' }">레이블된 데이터로 모델을 재학습합니다.</p>

      <!-- Model status card -->
      <div
        class="rounded-[24px] p-5 mb-4 relative overflow-hidden"
        :style="{ background: t.cardBg, backdropFilter: 'blur(40px) saturate(180%)', WebkitBackdropFilter: 'blur(40px) saturate(180%)', border: `1px solid ${t.cardBorder}`, boxShadow: t.cardShadow }"
      >
        <div class="absolute inset-x-0 top-0 pointer-events-none" :style="{ height: '50%', background: t.cardHighlight, borderRadius: '24px 24px 0 0' }" />
        <div class="relative z-10 flex items-start justify-between mb-4">
          <div>
            <p :style="{ fontSize: '11px', fontWeight: 600, color: t.textTertiary, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }">현재 모델</p>
            <p :style="{ fontSize: '17px', fontWeight: 700, color: t.textPrimary, letterSpacing: '-0.01em' }">YOLOv8 Classifier</p>
            <p :style="{ fontSize: '12px', color: t.textSecondary, marginTop: '2px' }">병해충 탐지 모델</p>
          </div>
          <div
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-full"
            :style="{
              background: isDark ? 'rgba(52,199,89,0.15)' : 'rgba(52,199,89,0.12)',
              border: `1px solid ${isDark ? 'rgba(52,199,89,0.30)' : 'rgba(52,199,89,0.25)'}`,
            }"
          >
            <div class="w-1.5 h-1.5 rounded-full" style="background: #34c759" />
            <span :style="{ fontSize: '11px', fontWeight: 600, color: '#34c759' }">운영 중</span>
          </div>
        </div>
      </div>

      <!-- Training config card -->
      <div
        class="rounded-[24px] p-5 mb-4 relative overflow-hidden"
        :style="{ background: t.cardBg, backdropFilter: 'blur(40px) saturate(180%)', WebkitBackdropFilter: 'blur(40px) saturate(180%)', border: `1px solid ${t.cardBorder}`, boxShadow: t.cardShadow }"
      >
        <div class="absolute inset-x-0 top-0 pointer-events-none" :style="{ height: '50%', background: t.cardHighlight, borderRadius: '24px 24px 0 0' }" />
        <p class="relative z-10" :style="{ fontSize: '13px', fontWeight: 600, color: t.textPrimary, marginBottom: '16px' }">학습 설정</p>

        <!-- Epochs -->
        <div class="relative z-10 mb-4">
          <div class="flex justify-between mb-2">
            <span :style="{ fontSize: '13px', color: t.textSecondary }">에포크 수</span>
            <span :style="{ fontSize: '13px', fontWeight: 600, color: t.textPrimary }">{{ ftEpochs }}</span>
          </div>
          <input
            type="range" :min="1" :max="50" v-model.number="ftEpochs"
            class="w-full"
            :style="{ accentColor: isDark ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.75)', height: '4px' }"
          />
        </div>

        <!-- Learning rate -->
        <div class="relative z-10 mb-4">
          <p :style="{ fontSize: '13px', color: t.textSecondary, marginBottom: '8px' }">학습률</p>
          <div class="flex gap-2">
            <button
              v-for="lr in ['1e-3', '1e-4', '1e-5']"
              :key="lr"
              @click="ftLR = lr"
              class="flex-1 py-2 rounded-xl transition-all"
              :style="{
                fontSize: '12px',
                fontWeight: ftLR === lr ? 700 : 400,
                color: ftLR === lr ? t.textPrimary : t.textTertiary,
                background: ftLR === lr ? (isDark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.09)') : (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)'),
                border: `1px solid ${ftLR === lr ? t.cardBorderDirty : t.separator}`,
                transition: 'all 0.15s ease',
              }"
            >{{ lr }}</button>
          </div>
        </div>

        <!-- Batch size -->
        <div class="relative z-10">
          <p :style="{ fontSize: '13px', color: t.textSecondary, marginBottom: '8px' }">배치 크기</p>
          <div class="flex gap-2">
            <button
              v-for="b in [8, 16, 32]"
              :key="b"
              @click="ftBatch = b"
              class="flex-1 py-2 rounded-xl transition-all"
              :style="{
                fontSize: '12px',
                fontWeight: ftBatch === b ? 700 : 400,
                color: ftBatch === b ? t.textPrimary : t.textTertiary,
                background: ftBatch === b ? (isDark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.09)') : (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)'),
                border: `1px solid ${ftBatch === b ? t.cardBorderDirty : t.separator}`,
                transition: 'all 0.15s ease',
              }"
            >{{ b }}</button>
          </div>
        </div>
      </div>

      <!-- Progress card -->
      <div
        v-if="ftTraining || ftDone"
        class="rounded-[24px] p-5 relative overflow-hidden"
        :style="{
          background: t.cardBg,
          backdropFilter: 'blur(40px) saturate(180%)',
          WebkitBackdropFilter: 'blur(40px) saturate(180%)',
          border: `1px solid ${ftDone ? t.cardBorderDirty : t.cardBorder}`,
          boxShadow: t.cardShadow,
          animation: 'slide-up 0.3s ease forwards',
        }"
      >
        <div class="absolute inset-x-0 top-0 pointer-events-none" :style="{ height: '50%', background: t.cardHighlight, borderRadius: '24px 24px 0 0' }" />
        <div class="relative z-10 flex items-center justify-between mb-3">
          <p :style="{ fontSize: '13px', fontWeight: 600, color: t.textPrimary }">
            {{ ftDone ? '학습 완료' : '학습 진행 중…' }}
          </p>
          <span :style="{ fontSize: '13px', fontWeight: 700, color: t.textPrimary }">{{ ftProgress }}%</span>
        </div>
        <div
          class="relative z-10 w-full rounded-full overflow-hidden"
          :style="{ height: '6px', background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)' }"
        >
          <div
            :style="{
              height: '100%',
              width: `${ftProgress}%`,
              borderRadius: '999px',
              background: isDark ? 'rgba(255,255,255,0.75)' : 'rgba(0,0,0,0.70)',
              transition: 'width 0.4s ease',
            }"
          />
        </div>
        <p v-if="ftDone" class="relative z-10 mt-3" :style="{ fontSize: '12px', color: t.textSecondary }">
          새 모델이 성공적으로 배포되었습니다. ✓
        </p>
      </div>
    </div>

    <!-- Floating finetune start button -->
    <div
      v-if="activeTab === 'finetune' && !ftDone"
      class="absolute z-40 flex justify-center pointer-events-none"
      :style="{ bottom: 'max(calc(env(safe-area-inset-bottom, 12px) + 68px), 80px)', left: 0, right: 0 }"
    >
      <button
        @click="startFinetune"
        :disabled="ftTraining"
        class="pointer-events-auto flex items-center gap-2 transition-all active:scale-95"
        :style="{
          padding: '12px 28px',
          borderRadius: '999px',
          fontSize: '15px',
          fontWeight: 600,
          cursor: ftTraining ? 'not-allowed' : 'pointer',
          background: ftTraining ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)') : (isDark ? 'rgba(255,255,255,0.90)' : 'rgba(0,0,0,0.85)'),
          border: ftTraining ? (isDark ? '1px solid rgba(255,255,255,0.10)' : '1px solid rgba(0,0,0,0.07)') : (isDark ? '1px solid rgba(255,255,255,0.35)' : '1px solid rgba(0,0,0,0.18)'),
          color: ftTraining ? t.textTertiary : (isDark ? 'rgba(0,0,0,0.88)' : 'rgba(255,255,255,0.95)'),
          backdropFilter: 'blur(30px) saturate(180%)',
          WebkitBackdropFilter: 'blur(30px) saturate(180%)',
          boxShadow: ftTraining ? 'none' : '0 6px 28px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.4)',
          transition: 'all 0.22s cubic-bezier(0.34,1.2,0.64,1)',
        }"
      >
        <template v-if="ftTraining">
          <div class="spinner" :style="{ width: '13px', height: '13px', borderColor: `${t.textTertiary}50`, borderTopColor: t.textTertiary }" />
          학습 중… {{ ftProgress }}%
        </template>
        <template v-else>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
            <polygon points="5,3 19,12 5,21" fill="currentColor" />
          </svg>
          파인튜닝 시작
        </template>
      </button>
    </div>

    <!-- Floating deploy buttons (after training) -->
    <div
      v-if="activeTab === 'finetune' && ftDone"
      class="absolute z-40 flex justify-center gap-3 pointer-events-none"
      :style="{ bottom: 'max(calc(env(safe-area-inset-bottom, 12px) + 68px), 80px)', left: 0, right: 0 }"
    >
      <button
        @click="ftDone = false; ftProgress = 0"
        class="pointer-events-auto flex items-center gap-2 transition-all active:scale-95"
        :style="{
          padding: '12px 22px', borderRadius: '999px', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
          background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
          border: isDark ? '1px solid rgba(255,255,255,0.14)' : '1px solid rgba(0,0,0,0.10)',
          color: t.textSecondary,
          backdropFilter: 'blur(30px) saturate(180%)',
          transition: 'all 0.22s cubic-bezier(0.34,1.2,0.64,1)',
        }"
      >재학습</button>
      <button
        @click="showToast('success', '모델이 성공적으로 배포되었습니다.')"
        class="pointer-events-auto flex items-center gap-2 transition-all active:scale-95"
        :style="{
          padding: '12px 28px', borderRadius: '999px', fontSize: '15px', fontWeight: 600, cursor: 'pointer',
          background: isDark ? 'rgba(255,255,255,0.90)' : 'rgba(0,0,0,0.85)',
          border: isDark ? '1px solid rgba(255,255,255,0.35)' : '1px solid rgba(0,0,0,0.18)',
          color: isDark ? 'rgba(0,0,0,0.88)' : 'rgba(255,255,255,0.95)',
          backdropFilter: 'blur(30px) saturate(180%)',
          boxShadow: '0 6px 28px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.4)',
        }"
      >모델 배포</button>
    </div>

    <!-- ═══════ TAB: 보고서 ═══════ -->
    <div
      v-if="activeTab === 'report'"
      class="relative z-10 flex-1 overflow-y-auto"
      :style="{
        paddingLeft: 'clamp(16px, 3vw, 28px)',
        paddingRight: 'clamp(16px, 3vw, 28px)',
        paddingTop: '20px',
        paddingBottom: '140px',
        scrollbarWidth: 'none',
      }"
    >
      <h2 :style="{ fontSize: '22px', fontWeight: 700, color: t.textPrimary, letterSpacing: '-0.02em', marginBottom: '4px' }">AI 운영 보고서</h2>
      <p :style="{ fontSize: '14px', color: t.textSecondary, marginBottom: '20px' }">병해충 탐지 현황 및 모델 성능 분석 보고서입니다.</p>

      <!-- 기간 세그먼트 버튼 -->
      <div class="flex gap-2 mb-5">
        <button
          v-for="opt in [{ value: 'weekly', label: '주간' }, { value: 'monthly', label: '월간' }]"
          :key="opt.value"
          @click="reportType = opt.value"
          class="flex-1 py-2.5 rounded-2xl transition-all"
          :style="{
            fontSize: '14px',
            fontWeight: reportType === opt.value ? 700 : 400,
            color: reportType === opt.value ? t.textPrimary : t.textTertiary,
            background: reportType === opt.value ? (isDark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.09)') : (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)'),
            border: `1px solid ${reportType === opt.value ? t.cardBorderDirty : t.separator}`,
          }"
        >{{ opt.label }}</button>
      </div>

      <!-- 보고서 메타 -->
      <p v-if="reportMeta" :style="{ fontSize: '11px', color: t.textTertiary, marginBottom: '12px' }">
        {{ reportMeta.period_start?.slice(0,10) }} ~ {{ reportMeta.period_end?.slice(0,10) }} 기준 · 생성: {{ reportMeta.created_at?.slice(0,16).replace('T', ' ') }}
      </p>

      <!-- 보고서 카드 -->
      <div
        class="rounded-[24px] p-5 relative overflow-hidden"
        :style="{ background: t.cardBg, backdropFilter: 'blur(40px) saturate(180%)', WebkitBackdropFilter: 'blur(40px) saturate(180%)', border: `1px solid ${t.cardBorder}`, boxShadow: t.cardShadow, minHeight: '160px' }"
      >
        <div class="absolute inset-x-0 top-0 pointer-events-none" :style="{ height: '40%', background: t.cardHighlight, borderRadius: '24px 24px 0 0' }" />

        <!-- 로딩 -->
        <div v-if="isLoadingReport" class="relative z-10 flex items-center justify-center py-12">
          <div class="spinner" :style="{ width: '20px', height: '20px', borderColor: `${t.textTertiary}40`, borderTopColor: t.textTertiary }" />
        </div>

        <!-- 내용 없음 -->
        <div v-else-if="!reportContent" class="relative z-10 py-8 text-center">
          <p :style="{ fontSize: '15px', color: t.textSecondary }">아직 보고서가 없습니다.</p>
          <p :style="{ fontSize: '13px', color: t.textTertiary, marginTop: '6px' }">아래 버튼을 눌러 보고서를 생성하세요.</p>
        </div>

        <!-- 마크다운 보고서 -->
        <div
          v-else
          class="relative z-10 report-content"
          :style="{ fontSize: '14px', lineHeight: 1.7, color: t.textPrimary }"
          v-html="mdToHtml(reportContent)"
        />
      </div>
    </div>

    <!-- Floating 보고서 생성 버튼 -->
    <div
      v-if="activeTab === 'report'"
      class="absolute z-40 flex justify-center pointer-events-none"
      :style="{ bottom: 'max(calc(env(safe-area-inset-bottom, 12px) + 68px), 80px)', left: 0, right: 0 }"
    >
      <button
        @click="generateReport"
        :disabled="isGeneratingReport"
        class="pointer-events-auto flex items-center gap-2 transition-all active:scale-95"
        :style="{
          padding: '12px 28px',
          borderRadius: '999px',
          fontSize: '15px',
          fontWeight: 600,
          cursor: isGeneratingReport ? 'not-allowed' : 'pointer',
          background: isGeneratingReport
            ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)')
            : (isDark ? 'rgba(255,255,255,0.90)' : 'rgba(0,0,0,0.85)'),
          border: isGeneratingReport
            ? (isDark ? '1px solid rgba(255,255,255,0.10)' : '1px solid rgba(0,0,0,0.07)')
            : (isDark ? '1px solid rgba(255,255,255,0.35)' : '1px solid rgba(0,0,0,0.18)'),
          color: isGeneratingReport ? t.textTertiary : (isDark ? 'rgba(0,0,0,0.88)' : 'rgba(255,255,255,0.95)'),
          backdropFilter: 'blur(30px) saturate(180%)',
          WebkitBackdropFilter: 'blur(30px) saturate(180%)',
          boxShadow: isGeneratingReport ? 'none' : '0 6px 28px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.4)',
          transition: 'all 0.22s cubic-bezier(0.34,1.2,0.64,1)',
        }"
      >
        <template v-if="isGeneratingReport">
          <div class="spinner" :style="{ width: '13px', height: '13px', borderColor: `${t.textTertiary}50`, borderTopColor: t.textTertiary }" />
          생성 중…
        </template>
        <template v-else>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
            <path d="M12 2v20M2 12h20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
          </svg>
          보고서 생성
        </template>
      </button>
    </div>

    <!-- ═══════ TAB: 설정 ═══════ -->
    <div
      v-if="activeTab === 'settings'"
      class="relative z-10 flex-1 overflow-y-auto"
      :style="{
        paddingLeft: 'clamp(16px, 3vw, 28px)',
        paddingRight: 'clamp(16px, 3vw, 28px)',
        paddingTop: '20px',
        paddingBottom: '140px',
        scrollbarWidth: 'none',
      }"
    >
      <h2 :style="{ fontSize: '22px', fontWeight: 700, color: t.textPrimary, letterSpacing: '-0.02em', marginBottom: '4px' }">모델 설정</h2>
      <p :style="{ fontSize: '14px', color: t.textSecondary, marginBottom: '24px' }">신뢰도 임계값을 조정합니다.</p>

      <!-- 현재 임계값 카드 -->
      <div
        class="rounded-[24px] p-5 mb-4 relative overflow-hidden"
        :style="{ background: t.cardBg, backdropFilter: 'blur(40px) saturate(180%)', WebkitBackdropFilter: 'blur(40px) saturate(180%)', border: `1px solid ${t.cardBorder}`, boxShadow: t.cardShadow }"
      >
        <div class="absolute inset-x-0 top-0 pointer-events-none" :style="{ height: '50%', background: t.cardHighlight, borderRadius: '24px 24px 0 0' }" />
        <div class="relative z-10 flex items-center justify-between mb-2">
          <p :style="{ fontSize: '13px', fontWeight: 600, color: t.textPrimary }">현재 적용 임계값</p>
          <span
            :style="{
              fontSize: '22px', fontWeight: 700, color: t.tint,
              fontVariantNumeric: 'tabular-nums',
            }"
          >{{ currentThreshold.toFixed(2) }}</span>
        </div>
        <p :style="{ fontSize: '12px', color: t.textSecondary }">
          임계값 이하의 탐지 결과는 관리자 검수 대기열로 이동됩니다.
        </p>
      </div>

      <!-- 임계값 조정 카드 -->
      <div
        class="rounded-[24px] p-5 relative overflow-hidden"
        :style="{ background: t.cardBg, backdropFilter: 'blur(40px) saturate(180%)', WebkitBackdropFilter: 'blur(40px) saturate(180%)', border: `1px solid ${t.cardBorder}`, boxShadow: t.cardShadow }"
      >
        <div class="absolute inset-x-0 top-0 pointer-events-none" :style="{ height: '50%', background: t.cardHighlight, borderRadius: '24px 24px 0 0' }" />
        <div class="relative z-10 flex items-center justify-between mb-4">
          <p :style="{ fontSize: '13px', fontWeight: 600, color: t.textPrimary }">새 임계값 설정</p>
          <span :style="{ fontSize: '18px', fontWeight: 700, color: t.textPrimary }">{{ editingThreshold.toFixed(2) }}</span>
        </div>

        <!-- 슬라이더 -->
        <div class="relative z-10 mb-5">
          <input
            type="range" min="0.1" max="0.9" step="0.05"
            v-model.number="editingThreshold"
            class="w-full"
            :style="{ accentColor: isDark ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.75)', height: '4px' }"
          />
          <div class="flex justify-between mt-1">
            <span :style="{ fontSize: '10px', color: t.textTertiary }">0.10</span>
            <span :style="{ fontSize: '10px', color: t.textTertiary }">0.90</span>
          </div>
        </div>

        <!-- 적용 버튼 -->
        <button
          @click="saveThreshold"
          :disabled="isSavingThreshold || editingThreshold === currentThreshold"
          class="relative z-10 w-full py-3 rounded-2xl transition-all active:scale-[0.98]"
          :style="{
            fontSize: '14px',
            fontWeight: 600,
            cursor: (isSavingThreshold || editingThreshold === currentThreshold) ? 'not-allowed' : 'pointer',
            background: (isSavingThreshold || editingThreshold === currentThreshold)
              ? (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)')
              : (isDark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.09)'),
            color: (isSavingThreshold || editingThreshold === currentThreshold) ? t.textTertiary : t.textPrimary,
            border: `1px solid ${t.separator}`,
            transition: 'all 0.15s ease',
          }"
        >
          <template v-if="isSavingThreshold">
            저장 중…
          </template>
          <template v-else>
            적용
          </template>
        </button>
      </div>
    </div>

    <!-- ═══════ FLOATING TAB BAR ═══════ -->
    <div
      class="absolute z-30 left-0 right-0 flex justify-center pointer-events-none"
      :style="{ bottom: 'max(env(safe-area-inset-bottom, 12px), 12px)' }"
    >
      <nav
        class="pointer-events-auto relative flex items-stretch overflow-hidden"
        :style="{
          borderRadius: '999px',
          padding: '6px 8px',
          gap: '4px',
          background: isDark ? 'rgba(28,28,40,0.42)' : 'rgba(255,255,255,0.35)',
          backdropFilter: 'blur(60px) saturate(200%) brightness(1.1)',
          WebkitBackdropFilter: 'blur(60px) saturate(200%) brightness(1.1)',
          border: isDark ? '1px solid rgba(255,255,255,0.18)' : '1px solid rgba(255,255,255,0.65)',
          boxShadow: isDark
            ? '0 8px 40px rgba(0,0,0,0.45), 0 1.5px 0 rgba(255,255,255,0.08) inset, 0 -0.5px 0 rgba(0,0,0,0.2) inset'
            : '0 8px 40px rgba(0,0,0,0.12), 0 1.5px 0 rgba(255,255,255,0.9) inset, 0 -0.5px 0 rgba(0,0,0,0.06) inset',
        }"
      >
        <!-- Inner specular highlight -->
        <div
          class="absolute inset-x-0 top-0 pointer-events-none"
          :style="{
            height: '55%',
            borderRadius: '999px 999px 0 0',
            background: isDark
              ? 'linear-gradient(180deg, rgba(255,255,255,0.10) 0%, transparent 100%)'
              : 'linear-gradient(180deg, rgba(255,255,255,0.55) 0%, transparent 100%)',
          }"
        />

        <button
          v-for="tab in [
            { id: 'inspect', label: '검수' },
            { id: 'finetune', label: '파인튜닝' },
            { id: 'report', label: '보고서' },
            { id: 'settings', label: '설정' },
          ]"
          :key="tab.id"
          @click="activeTab = tab.id"
          class="relative z-10 flex items-center gap-2 transition-all active:scale-95"
          :style="{
            padding: '8px 16px',
            borderRadius: '999px',
            background: activeTab === tab.id ? (isDark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.08)') : 'transparent',
            border: 'none',
            color: activeTab === tab.id ? t.textPrimary : t.textTertiary,
            fontSize: '13px',
            fontWeight: activeTab === tab.id ? 600 : 400,
            transition: 'all 0.2s cubic-bezier(0.34,1.2,0.64,1)',
            letterSpacing: '-0.01em',
          }"
        >
          <!-- 검수 icon -->
          <svg v-if="tab.id === 'inspect'" width="16" height="16" viewBox="0 0 24 24" :fill="activeTab === 'inspect' ? 'currentColor' : 'none'">
            <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" />
            <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" />
            <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" />
            <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2" />
          </svg>
          <!-- 파인튜닝 icon -->
          <svg v-else-if="tab.id === 'finetune'" width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
              :fill="activeTab === 'finetune' ? 'currentColor' : 'none'" :fill-opacity="activeTab === 'finetune' ? 0.18 : 0"
            />
          </svg>
          <!-- 보고서 icon -->
          <svg v-else-if="tab.id === 'report'" width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :fill="activeTab === 'report' ? 'currentColor' : 'none'" :fill-opacity="activeTab === 'report' ? 0.15 : 0" />
            <polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <!-- 설정 icon -->
          <svg v-else-if="tab.id === 'settings'" width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" :fill="activeTab === 'settings' ? 'currentColor' : 'none'" :fill-opacity="activeTab === 'settings' ? 0.25 : 0" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            />
          </svg>
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- ══ TOAST ══ -->
    <div v-if="toast" class="absolute bottom-28 left-0 right-0 z-50 flex justify-center pointer-events-none">
      <div
        class="flex items-center gap-3 px-5 py-3.5 rounded-2xl pointer-events-auto"
        :style="{
          background: t.toastBg,
          backdropFilter: 'blur(40px) saturate(180%)',
          WebkitBackdropFilter: 'blur(40px) saturate(180%)',
          border: `1px solid ${t.navBorder}`,
          boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
          animation: 'slide-up 0.22s cubic-bezier(0.34,1.2,0.64,1) forwards',
          whiteSpace: 'nowrap',
        }"
      >
        <span :style="{ fontSize: '14px', fontWeight: 700, color: t.textPrimary }">
          {{ toast.kind === 'success' ? '✓' : '✕' }}
        </span>
        <span :style="{ fontSize: '14px', color: t.textPrimary, fontWeight: 500 }">{{ toast.message }}</span>
      </div>
    </div>
  </main>
</template>
