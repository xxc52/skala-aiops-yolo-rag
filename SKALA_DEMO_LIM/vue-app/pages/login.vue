<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const username = ref('')
const password = ref('')
const isAuthenticating = ref(false)
const authError = ref(false)

async function handleLogin() {
  if (isAuthenticating.value) return
  isAuthenticating.value = true
  authError.value = false

  try {
    const response = await fetch("http://localhost:3001/api/manager/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.value, password: password.value }),
    });

    if (!response.ok) throw new Error("Auth failed")
    const data = await response.json()

    if (data.success && data.token) {
      localStorage.setItem("admin_token", data.token)
      router.push("/new-window")
    } else {
      throw new Error("Invalid username or password")
    }
  } catch (err) {
    console.error("Login Error:", err)
    authError.value = true
    password.value = ""
    setTimeout(() => { authError.value = false }, 500)
  } finally {
    isAuthenticating.value = false
  }
}

function goBack() {
  router.push('/')
}

function goToRegister() {
  router.push('/register')
}
</script>

<template>
  <div class="fixed inset-0 w-full h-full bg-[#0a0a0c] flex items-center justify-center p-6 z-[9999] overflow-hidden font-sans">
    <!-- Ambient Background -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-600/10 blur-[100px] rounded-full" />
      <div class="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-600/10 blur-[100px] rounded-full" />
    </div>

    <div 
      class="w-full max-w-[380px] relative z-10 flex flex-col"
    >
      <!-- Back Button -->
      <button 
        @click="goBack"
        class="mb-6 self-start flex items-center gap-2 text-white/40 hover:text-white transition-colors cursor-pointer"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        <span class="text-sm">돌아가기</span>
      </button>

      <!-- Login Card -->
      <div class="bg-[#1c1c1e] border border-white/10 rounded-[28px] p-8 shadow-2xl">
        <div class="flex flex-col items-center text-center mb-8">
          <div class="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-4 border border-white/10">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h1 class="text-white text-xl font-bold mb-1">관리자 인증</h1>
          <p class="text-white/40 text-xs">아이디와 비밀번호를 입력하세요</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-4">
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

          <button
            type="submit"
            :disabled="isAuthenticating || !username || !password"
            class="w-full py-4 bg-white text-black font-bold rounded-xl active:scale-[0.98] transition-all disabled:opacity-30 flex items-center justify-center gap-2 cursor-pointer mt-2"
          >
            <span v-if="isAuthenticating" class="spinner-small" />
            {{ isAuthenticating ? '확인 중...' : '잠금 해제' }}
          </button>
        </form>

        <div class="mt-6 pt-6 border-t border-white/5 text-center">
          <p class="text-white/30 text-xs mb-3">계정이 없으신가요?</p>
          <button @click="goToRegister" class="text-white/60 hover:text-white text-sm font-medium transition-colors cursor-pointer">
            새 계정 생성하기
          </button>
        </div>

        <div v-if="authError" class="mt-4 text-center">
          <p class="text-red-400 text-xs font-medium">아이디 또는 비밀번호가 올바르지 않습니다</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fixed { position: fixed; inset: 0; }
.shake-anim { animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both; }
@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}
.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(0,0,0,0.1);
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.cursor-pointer { cursor: pointer; }
</style>