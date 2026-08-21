<template>
  <el-container class="shell">
    <el-header class="header">
      <div class="brand"><span class="brand-mark">问</span><div><b>问卷自动化</b><small>Questionnaire Studio</small></div></div>
      <div class="account"><span class="avatar">{{ user.username.slice(0,1).toUpperCase() }}</span><span>{{ user.username }}</span><el-button link @click="logout">退出</el-button></div>
    </el-header>
    <el-container>
      <el-aside width="220px">
        <div class="nav-caption">工作台</div>
        <el-menu router :default-active="$route.path">
          <el-menu-item index="/tasks"><span class="nav-icon">▣</span>任务管理</el-menu-item>
          <el-menu-item v-if="user.role === 'admin'" index="/settings/ai"><span class="nav-icon">AI</span>AI 配置管理</el-menu-item>
          <el-menu-item v-if="user.role === 'admin'" index="/admin/users"><span class="nav-icon">👥</span>用户管理</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
const user = useUserStore()
const router = useRouter()
const logout = async () => { await user.logout(); await router.push('/login') }
</script>
<style scoped>.shell{min-height:100vh;background:#f3f6fb}.header{height:72px;display:flex;align-items:center;justify-content:space-between;padding:0 30px;background:linear-gradient(110deg,#182848,#284b8c);color:#fff;box-shadow:0 4px 18px #18284830}.brand,.account{display:flex;align-items:center;gap:12px}.brand small{display:block;opacity:.65;font-size:10px;letter-spacing:1px}.brand-mark{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#66d9ef,#647bff);font-weight:700;font-size:20px}.account{font-size:13px}.avatar{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#ffffff2b}.account .el-button{color:#dbe7ff}.el-aside{background:#fff;border-right:1px solid #e8edf5;padding:20px 12px}.nav-caption{padding:8px 14px;color:#a0aec0;font-size:11px;text-transform:uppercase;letter-spacing:1px}.el-menu{border:0}.el-menu-item{border-radius:9px;margin:4px 0}.el-menu-item.is-active{background:#edf2ff;color:#4263d8;font-weight:600}.nav-icon{margin-right:10px;font-size:18px}</style>

