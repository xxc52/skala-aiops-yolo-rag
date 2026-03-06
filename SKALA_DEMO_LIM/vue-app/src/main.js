import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../app.vue'
import IndexPage from '../pages/index.vue'
import NewWindowPage from '../pages/new-window.vue'
import '../assets/css/main.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: IndexPage },
    { path: '/new-window', component: NewWindowPage },
  ],
})

const app = createApp(App)
app.use(router)
app.mount('#app')
