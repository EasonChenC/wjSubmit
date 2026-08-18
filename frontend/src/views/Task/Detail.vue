<template><div class="page"><el-page-header content="任务详情" @back="$router.push('/tasks')"/><div v-if="task" class="card detail"><div class="detail-header"><h2>{{task.task_id}}</h2><el-button v-if="canCancel" type="danger" :loading="cancelling" @click="cancel">停止任务</el-button></div><el-descriptions :column="2" border><el-descriptions-item label="状态">{{statusText(task.status)}}</el-descriptions-item><el-descriptions-item label="问卷 URL">{{task.url||'—'}}</el-descriptions-item><el-descriptions-item label="总数">{{task.total}}</el-descriptions-item><el-descriptions-item label="成功 / 失败">{{task.submitted}} / {{task.failed}}</el-descriptions-item><el-descriptions-item v-if="task.ai_text_enabled" label="AI 文本题答案池">{{aiTextStatusText(task.ai_text_status)}}（{{task.ai_text_generated_count||0}} / {{task.total}} 份）</el-descriptions-item><el-descriptions-item v-if="task.ai_text_error" label="AI 生成错误">{{task.ai_text_error}}</el-descriptions-item></el-descriptions><el-progress :percentage="task.progress" :status="task.status==='failed'||task.status==='cancelled'?'exception':task.status==='completed'?'success':undefined" :stroke-width="16"/><el-divider/><el-table :data="task.results||[]"><el-table-column prop="index" label="#" width="80"/><el-table-column prop="status" label="结果"/><el-table-column prop="error" label="错误"/></el-table></div><el-empty v-else description="正在加载"/></div></template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import type { Task } from '@/types'

const route = useRoute()
const store = useTaskStore()
const task = ref<Task | null>(null)
const cancelling = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

const FINISHED_STATUSES = ['completed', 'failed', 'cancelled']
const statusText = (s: string) => ({ pending: '等待中', processing: '进行中', completed: '已完成', failed: '失败', cancelled: '已停止' } as Record<string, string>)[s] || s
const aiTextStatusText = (s?: string) => ({ disabled: '未启用', pending: '等待生成', generating: '生成中', ready: '已就绪', failed: '生成失败', cancelled: '已停止' } as Record<string, string>)[s||'disabled'] || s
const canCancel = computed(() => task.value && !FINISHED_STATUSES.includes(task.value.status))

const refresh = async () => {
  task.value = await store.refresh(String(route.params.id))
  if (task.value && FINISHED_STATUSES.includes(task.value.status) && timer) {
    clearInterval(timer)
    timer = undefined
  }
}

const cancel = async () => {
  try {
    await ElMessageBox.confirm('确定停止该任务吗？当前正在提交的这一份会先完成，之后不再继续提交。', '确认停止')
  } catch {
    return
  }
  cancelling.value = true
  try {
    task.value = await store.cancel(String(route.params.id))
    ElMessage.success('已请求停止任务')
  } catch {
    ElMessage.error('停止任务失败')
  } finally {
    cancelling.value = false
  }
}

onMounted(async () => {
  await refresh()
  if (!task.value || !FINISHED_STATUSES.includes(task.value.status)) {
    timer = setInterval(refresh, 3000)
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
<style scoped>.detail{margin-top:20px}.detail-header{display:flex;justify-content:space-between;align-items:center}.el-progress{margin-top:28px}</style>
