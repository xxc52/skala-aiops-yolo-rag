<script setup>
import { ref, watch, onUnmounted } from 'vue'

const CATEGORIES = ["Class A", "Class B", "Class C", "Class D", "Class E"];

const props = defineProps({
  record: Object,
  selected: String,
  isDirty: Boolean,
  t: Object,
});

const emit = defineEmits(["change"]);

const imgError = ref(false);
const open = ref(false);
const dropRef = ref(null);

let outsideHandler = null;

function cleanupOutside() {
  if (outsideHandler) {
    document.removeEventListener("mousedown", outsideHandler);
    outsideHandler = null;
  }
}

watch(open, (newVal) => {
  cleanupOutside();
  if (newVal) {
    outsideHandler = (e) => {
      if (dropRef.value && !dropRef.value.contains(e.target)) {
        open.value = false;
      }
    };
    document.addEventListener("mousedown", outsideHandler);
  }
});

onUnmounted(cleanupOutside);

function shortUUID(uuid) {
  return uuid.slice(0, 8).toUpperCase();
}
</script>

<template>
  <div
    class="flex-shrink-0 flex flex-col relative overflow-hidden"
    :style="{
      width: '244px',
      height: '344px',
      borderRadius: '28px',
      background: isDirty ? t.cardBgDirty : t.cardBg,
      backdropFilter: 'blur(40px) saturate(180%) brightness(1.02)',
      WebkitBackdropFilter: 'blur(40px) saturate(180%) brightness(1.02)',
      border: `1.5px solid ${isDirty ? t.cardBorderDirty : t.cardBorder}`,
      boxShadow: t.cardShadow,
      transition: 'border-color 0.25s ease, background 0.25s ease, box-shadow 0.25s ease',
    }"
  >
    <!-- Specular inner highlight -->
    <div
      class="absolute inset-x-0 top-0 pointer-events-none z-10"
      :style="{ height: '52%', background: t.cardHighlight, borderRadius: '28px 28px 0 0' }"
    />

    <!-- Image area -->
    <div
      class="relative overflow-hidden"
      :style="{
        flex: '1 1 0',
        background: t.imagePlaceholderBg,
        borderRadius: '26px 26px 0 0',
      }"
    >
      <!-- Error placeholder -->
      <div
        v-if="imgError"
        class="w-full h-full flex flex-col items-center justify-center gap-2"
        :style="{ color: t.textTertiary }"
      >
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="1.5" />
          <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
          <path d="M3 15l5-5 4 4 3-3 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span :style="{ fontSize: '11px', color: t.textTertiary }">이미지 없음</span>
      </div>

      <!-- Image -->
      <img
        v-else
        :src="record.imageUrl"
        :alt="`Image ${shortUUID(record.uuid)}`"
        class="absolute inset-0 w-full h-full object-cover"
        @error="imgError = true"
      />

      <!-- Confidence badge -->
      <div
        class="absolute top-3 left-3 z-20 px-2.5 py-1 rounded-full font-semibold"
        :style="{
          background: t.badgeBg,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: `1px solid ${t.badgeBorder}`,
          fontSize: '11px',
          color: t.textSecondary,
          letterSpacing: '0.04em',
        }"
      >
        {{ (record.confidenceScore * 100).toFixed(0) }}%
      </div>

      <!-- Dirty indicator dot -->
      <div
        v-if="isDirty"
        class="absolute top-3 right-3 z-20 w-2.5 h-2.5 rounded-full"
        :style="{ background: t.tint, boxShadow: `0 0 10px ${t.tint}90` }"
      />
    </div>

    <!-- Footer info -->
    <div class="p-3.5 flex flex-col gap-2.5 relative z-20">
      <span
        class="font-mono"
        :style="{ fontSize: '10px', color: t.uuidColor, letterSpacing: '0.07em' }"
      >
        {{ shortUUID(record.uuid) }}…
      </span>

      <!-- Dropdown -->
      <div ref="dropRef" class="relative">
        <button
          @click="open = !open"
          class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-2xl"
          :style="{
            background: open ? t.dropBtnOpen : t.dropBtn,
            border: `1px solid ${open ? t.dropBtnOpenBorder : t.dropBtnBorder}`,
            fontSize: '13px',
            fontWeight: 500,
            color: selected ? t.textPrimary : t.textTertiary,
            backdropFilter: 'blur(12px)',
            transition: 'all 0.15s ease',
            textAlign: 'left',
          }"
        >
          <span class="truncate">{{ selected || "카테고리 선택" }}</span>
          <svg
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            :style="{
              transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s cubic-bezier(0.34,1.56,0.64,1)',
              flexShrink: 0,
              marginLeft: '8px',
            }"
          >
            <path d="M6 9l6 6 6-6" :stroke="t.textSecondary" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>

        <div
          v-if="open"
          class="absolute bottom-full mb-2 left-0 right-0 z-50 overflow-hidden"
          :style="{
            borderRadius: '18px',
            background: t.dropdownBg,
            backdropFilter: 'blur(40px) saturate(180%)',
            WebkitBackdropFilter: 'blur(40px) saturate(180%)',
            border: `1px solid ${t.dropdownBorder}`,
            boxShadow: '0 -8px 40px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.1)',
            animation: 'slide-up 0.18s cubic-bezier(0.34,1.2,0.64,1) forwards',
          }"
        >
          <button
            v-for="(cat, i) in CATEGORIES"
            :key="cat"
            @click="emit('change', record.uuid, cat); open = false"
            class="w-full text-left px-4 py-3 flex items-center gap-3"
            :style="{
              fontSize: '14px',
              fontWeight: selected === cat ? 600 : 400,
              color: selected === cat ? t.tint : t.textPrimary,
              background: 'transparent',
              borderTop: i > 0 ? `1px solid ${t.separator}` : 'none',
              transition: 'background 0.1s',
            }"
            @mouseenter="$event.currentTarget.style.background = t.dropdownHover"
            @mouseleave="$event.currentTarget.style.background = 'transparent'"
          >
            <span :style="{ width: '16px', display: 'flex', alignItems: 'center', flexShrink: 0 }">
              <svg v-if="selected === cat" width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M5 12l5 5L20 7" :stroke="t.tint" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            {{ cat }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
