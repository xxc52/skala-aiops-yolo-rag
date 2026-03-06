<script setup>
const props = defineProps({ t: Object });
</script>

<template>
  <div
    class="flex-shrink-0 relative overflow-hidden"
    :style="{
      width: '244px',
      height: '344px',
      borderRadius: '28px',
      background: t.cardBg,
      backdropFilter: 'blur(40px) saturate(180%)',
      WebkitBackdropFilter: 'blur(40px) saturate(180%)',
      border: `1px solid ${t.cardBorder}`,
      boxShadow: t.cardShadow,
      animation: 'skeleton-pulse 1.8s ease-in-out infinite',
    }"
  >
    <!-- Top specular highlight -->
    <div
      class="absolute inset-x-0 top-0 pointer-events-none"
      :style="{ height: '52%', background: t.cardHighlight, borderRadius: '28px 28px 0 0' }"
    />
    <!-- Fake image area -->
    <div
      :style="{
        position: 'absolute',
        inset: 0,
        bottom: '88px',
        background: t.skeletonBg,
      }"
    />
    <!-- Fake footer lines -->
    <div
      :style="{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '88px',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }"
    >
      <div :style="{ height: '9px', width: '40%', borderRadius: '6px', background: t.skeletonBg }" />
      <div :style="{ height: '36px', borderRadius: '14px', background: t.skeletonBg }" />
    </div>
  </div>
</template>
