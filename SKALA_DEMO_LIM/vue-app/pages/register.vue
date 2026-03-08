<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const isRegistering = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

async function handleRegister() {
  if (isRegistering.value) return
  if (password.value !== confirmPassword.value) {
    errorMsg.value = "비밀번호가 일치하지 않습니다."
    return
  }

  isRegistering.value = true
  errorMsg.value = ''
  successMsg.value = ''

  try {
    const response = await fetch("http://localhost:3001/api/manager/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.value, password: password.value }),
    });

    const data = await response.json()
    if (data.success) {
      successMsg.value = "회원가입 성공! 로그인 페이지로 이동합니다."
      setTimeout(() => router.push('/login'), 2000)
    } else {
      errorMsg.value = data.error || "회원가입에 실패했습니다."
    }
  } catch (err) {
    errorMsg.value = "서버 연결 오류가 발생했습니다."
  } finally {
    isRegistering.value = false
  }
}

function goBack() {
  router.push('/login')
}
</script>

<template>
  <div class="fixed inset-0 w-full h-full bg-[#0a0a0c] flex items-center justify-center p-6 z-[9999] overflow-hidden font-sans">
    <!-- Ambient Background -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-600/10 blur-[100px] rounded-full" />
      <div class="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-600/10 blur-[100px] rounded-full" />
    </div>

    <div class="w-full max-w-[380px] relative z-10 flex flex-col">
      <!-- Back Button -->
      <button @click="goBack" class="mb-6 self-start flex items-center gap-2 text-white/40 hover:text-white transition-colors cursor-pointer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        <span class="text-sm">로그인으로 돌아가기</span>
      </button>

      <!-- Register Card -->
      <div class="bg-[#1c1c1e] border border-white/10 rounded-[28px] p-8 shadow-2xl">
        <div class="flex flex-col items-center text-center mb-8">
          <div class="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-4 border border-white/10">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="8.5" cy="7" r="4" />
              <line x1="20" y1="8" x2="20" y2="14" />
              <line x1="23" y1="11" x2="17" y2="11" />
            </svg>
          </div>
          <h1 class="text-white text-xl font-bold mb-1">회원가입</h1>
          <p class="text-white/40 text-xs">새로운 관리자 계정을 생성하세요</p>
        </div>

        <form @submit.prevent="handleRegister" class="space-y-4">
          <input
            v-model="username"
            type="text"
            placeholder="아이디"
            class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-white/30 transition-all placeholder:text-white/20"
            required
          />
          <input
            v-model="password"
            type="password"
            placeholder="비밀번호"
            class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-white/30 transition-all placeholder:text-white/20"
            required
          />
          <input
            v-model="confirmPassword"
            type="password"
            placeholder="비밀번호 확인"
            class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-white/30 transition-all placeholder:text-white/20"
            required
          />

          <button
            type="submit"
            :disabled="isRegistering || !username || !password"
            class="w-full py-4 bg-white text-black font-bold rounded-xl active:scale-[0.98] transition-all disabled:opacity-30 flex items-center justify-center gap-2 cursor-pointer mt-4"
          >
            {{ isRegistering ? '등록 중...' : '계정 생성' }}
          </button>
        </form>

        <p v-if="errorMsg" class="mt-4 text-red-400 text-xs text-center font-medium">{{ errorMsg }}</p>
        <p v-if="successMsg" class="mt-4 text-green-400 text-xs text-center font-medium">{{ successMsg }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fixed { position: fixed; inset: 0; }
.cursor-pointer { cursor: pointer; }
</style>
