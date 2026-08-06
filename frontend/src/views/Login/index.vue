<template><div class="login"><div class="card box"><h1>问卷自动化系统</h1><p class="muted">登录后管理问卷分析与提交任务</p><el-form :model="form" @submit.prevent="submit"><el-form-item prop="username"><el-input v-model="form.username" placeholder="用户名" size="large"/></el-form-item><el-form-item prop="password"><el-input v-model="form.password" type="password" show-password placeholder="密码" size="large"/></el-form-item><el-checkbox v-model="remember">记住登录状态</el-checkbox><el-button class="submit" type="primary" size="large" native-type="submit" :loading="loading">登录</el-button></el-form></div></div></template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const form = reactive({ username: '', password: '' })
const remember = ref(true)
const loading = ref(false)
const userStore = useUserStore()
const router = useRouter()

const submit = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  const ok = await userStore.login(form.username, form.password)
  loading.value = false
  if (ok) await router.push('/tasks')
  else ElMessage.error('登录失败')
}
</script>
<style scoped>.login{min-height:100vh;display:grid;place-items:center;background:linear-gradient(135deg,#e8f1ff,#f8fbff)}.box{width:390px}.box h1{margin:0 0 8px}.muted{color:#86909c}.submit{width:100%;margin-top:22px}</style>
