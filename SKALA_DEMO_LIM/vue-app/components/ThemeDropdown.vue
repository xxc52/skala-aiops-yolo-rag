<script setup>
import { ref, watch, computed, onUnmounted } from 'vue'

const props = defineProps({ theme: String, t: Object });
const emit = defineEmits(["update:theme"]);

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

const THEME_OPTIONS = [
  { id: "light", label: "라이트" },
  { id: "dark",  label: "다크" },
  { id: "device", label: "자동" },
];

const activeOption = computed(
  () => THEME_OPTIONS.find((o) => o.id === props.theme)
);

function selectTheme(id) {
  emit("update:theme", id);
  open.value = false;
}
</script>

<template>
  <div ref="dropRef" class="relative">
    <button
      @click="open = !open"
      class="flex items-center gap-2 px-3 py-1.5 rounded-xl transition-all"
      :style="{
        background: open ? t.dropBtnOpen : 'rgba(128,128,128,0.08)',
        border: `1px solid ${open ? t.dropBtnOpenBorder : 'rgba(128,128,128,0.13)'}`,
        fontSize: '12px',
        fontWeight: 600,
        color: open ? t.tint : t.textSecondary,
        backdropFilter: 'blur(12px)',
        transition: 'all 0.18s ease',
        gap: '6px',
      }"
    >
      <!-- Theme icon -->
      <span :style="{ color: open ? t.tint : t.textSecondary, display: 'flex' }">
        <!-- Light icon -->
        <svg v-if="theme === 'light'" width="13" height="13" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <!-- Dark icon -->
        <svg v-else-if="theme === 'dark'" width="13" height="13" viewBox="0 0 24 24" fill="none">
          <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <!-- Device icon -->
        <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none">
          <rect x="5" y="2" width="14" height="20" rx="3" stroke="currentColor" stroke-width="2" />
          <circle cx="12" cy="17" r="1" fill="currentColor" />
        </svg>
      </span>

      {{ activeOption.label }}

      <svg
        width="10" height="10" viewBox="0 0 24 24" fill="none"
        :style="{
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.18s cubic-bezier(0.34,1.56,0.64,1)',
          opacity: 0.55,
        }"
      >
        <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <div
      v-if="open"
      class="absolute top-full mt-1.5 right-0 z-50 overflow-hidden"
      :style="{
        borderRadius: '16px',
        minWidth: '120px',
        background: t.dropdownBg,
        backdropFilter: 'blur(40px) saturate(180%)',
        WebkitBackdropFilter: 'blur(40px) saturate(180%)',
        border: `1px solid ${t.dropdownBorder}`,
        boxShadow: '0 8px 32px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.1)',
        animation: 'slide-up 0.16s cubic-bezier(0.34,1.2,0.64,1) forwards',
      }"
    >
      <button
        v-for="(opt, i) in THEME_OPTIONS"
        :key="opt.id"
        @click="selectTheme(opt.id)"
        class="w-full flex items-center gap-2.5 px-3.5 py-2.5"
        :style="{
          fontSize: '13px',
          fontWeight: theme === opt.id ? 600 : 400,
          color: theme === opt.id ? t.tint : t.textPrimary,
          background: 'transparent',
          borderTop: i > 0 ? `1px solid ${t.separator}` : 'none',
          transition: 'background 0.1s',
          textAlign: 'left',
        }"
        @mouseenter="$event.currentTarget.style.background = t.dropdownHover"
        @mouseleave="$event.currentTarget.style.background = 'transparent'"
      >
        <span :style="{ color: theme === opt.id ? t.tint : t.textSecondary, display: 'flex' }">
          <svg v-if="opt.id === 'light'" width="13" height="13" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <svg v-else-if="opt.id === 'dark'" width="13" height="13" viewBox="0 0 24 24" fill="none">
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none">
            <rect x="5" y="2" width="14" height="20" rx="3" stroke="currentColor" stroke-width="2" />
            <circle cx="12" cy="17" r="1" fill="currentColor" />
          </svg>
        </span>
        {{ opt.label }}
        <span v-if="theme === opt.id" class="ml-auto">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M5 12l5 5L20 7" :stroke="t.tint" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </button>
    </div>
  </div>
</template>
