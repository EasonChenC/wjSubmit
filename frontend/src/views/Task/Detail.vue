<template><div class="page"><el-page-header content="任务详情" @back="$router.push('/tasks')"/><div v-if="task" class="card detail"><h2>{{task.task_id}}</h2><el-descriptions :column="2" border><el-descriptions-item label="状态">{{task.status}}</el-descriptions-item><el-descriptions-item label="问卷 URL">{{task.url||'—'}}</el-descriptions-item><el-descriptions-item label="总数">{{task.total}}</el-descriptions-item><el-descriptions-item label="成功 / 失败">{{task.submitted}} / {{task.failed}}</el-descriptions-item></el-descriptions><el-progress :percentage="task.progress" :stroke-width="16"/><el-divider/><el-table :data="task.results||[]"><el-table-column prop="index" label="#" width="80"/><el-table-column prop="status" label="结果"/><el-table-column prop="error" label="错误"/></el-table></div><el-empty v-else description="正在加载"/></div></template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import type { Task } from '@/types'

const route = useRoute()
const store = useTaskStore()
const task = ref<Task | null>(null)
let timer: ReturnType<typeof setInterval> | undefined

const refresh = async () => {
  task.value = await store.refresh(String(route.params.id))
  if (task.value && ['completed', 'failed'].includes(task.value.status) && timer) {
    clearInterval(timer)
    timer = undefined
  }
}

onMounted(async () => {
  await refresh()
  if (!task.value || !['completed', 'failed'].includes(task.value.status)) {
    timer = setInterval(refresh, 3000)
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
<style scoped>.detail{margin-top:20px}.el-progress{margin-top:28px}</style>
