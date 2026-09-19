<template>
  <div class="page">
    <el-page-header content="任务详情" @back="$router.push('/tasks')" />
    <div v-if="task" class="card detail">
      <div class="detail-header">
        <div><h2>{{ task.title || '未命名问卷' }}</h2><span class="muted">{{ task.creator_username || '' }}</span></div>
        <div class="actions"><el-button v-if="canResume" type="primary" :loading="resuming" @click="resume">继续任务</el-button><el-button v-if="canCancel" type="danger" :loading="cancelling" @click="cancel">停止任务</el-button></div>
      </div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="状态">{{ statusText(task.status) }}</el-descriptions-item>
        <el-descriptions-item label="问卷 URL">{{ task.url || '—' }}</el-descriptions-item>
        <el-descriptions-item label="目标成功数">{{ task.total }}</el-descriptions-item>
        <el-descriptions-item label="已成功 / 失败尝试">{{ task.submitted }} / {{ task.failed }}</el-descriptions-item>
        <el-descriptions-item label="剩余数量">{{ task.remaining ?? Math.max(task.total-task.submitted,0) }}</el-descriptions-item>
        <el-descriptions-item label="执行批次 / 恢复次数">{{ task.execution_no || 0 }} / {{ task.resume_count || 0 }}</el-descriptions-item>
        <el-descriptions-item v-if="task.ai_text_enabled" label="AI 文本答案池">{{ aiTextStatusText(task.ai_text_status) }}（{{task.ai_text_generated_count||0}} / {{task.total}} 份）</el-descriptions-item>
        <el-descriptions-item v-if="task.proportion_plan_status&&task.proportion_plan_status!=='disabled'" label="比例答案计划">{{task.proportion_plan_status}}（{{task.proportion_plan_count||0}} / {{task.total}} 份）</el-descriptions-item>
        <el-descriptions-item v-if="task.ai_text_error" label="AI 生成错误">{{task.ai_text_error}}</el-descriptions-item>
      </el-descriptions>
      <el-progress :percentage="task.progress" :status="task.status==='failed'||task.status==='cancelled'?'exception':task.status==='completed'?'success':undefined" :stroke-width="16" />
      <el-divider />
      <el-table :data="task.results||[]"><el-table-column prop="index" label="#" width="80"/><el-table-column prop="status" label="结果"/><el-table-column prop="error" label="错误"/></el-table>
    </div>
    <el-empty v-else description="正在加载" />
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import type { Task } from '@/types'
const route=useRoute(),store=useTaskStore();const task=ref<Task|null>(null),cancelling=ref(false),resuming=ref(false);let timer:ReturnType<typeof setInterval>|undefined
const statusText=(s:string)=>({pending:'等待中',processing:'进行中',completed:'已完成',failed:'失败',cancelled:'已停止'} as Record<string,string>)[s]||s
const aiTextStatusText=(s?:string)=>({disabled:'未启用',pending:'等待生成',generating:'生成中',ready:'已就绪',failed:'生成失败',cancelled:'已停止'} as Record<string,string>)[s||'disabled']||s
const canCancel=computed(()=>!!task.value&&['pending','processing'].includes(task.value.status))
const canResume=computed(()=>!!task.value&&['cancelled','failed'].includes(task.value.status)&&task.value.submitted<task.value.total)
const startPolling=()=>{if(!timer)timer=setInterval(refresh,3000)}
const stopPolling=()=>{if(timer){clearInterval(timer);timer=undefined}}
const refresh=async()=>{task.value=await store.refresh(String(route.params.id));if(task.value&&['completed','failed','cancelled'].includes(task.value.status))stopPolling()}
const cancel=async()=>{try{await ElMessageBox.confirm('当前正在提交的一份会先完成，之后停止。','确认停止')}catch{return}cancelling.value=true;try{task.value=await store.cancel(String(route.params.id));ElMessage.success('已请求停止任务');startPolling()}catch(e:any){ElMessage.error(e?.response?.data?.detail||'停止任务失败')}finally{cancelling.value=false}}
const resume=async()=>{const remaining=(task.value?.remaining??Math.max((task.value?.total||0)-(task.value?.submitted||0),0));try{await ElMessageBox.confirm(`任务将从已确认成功的断点继续，剩余 ${remaining} 份。是否继续？`,'继续任务')}catch{return}resuming.value=true;try{task.value=await store.resume(String(route.params.id));ElMessage.success('任务已恢复');startPolling()}catch(e:any){ElMessage.error(e?.response?.data?.detail||'恢复任务失败')}finally{resuming.value=false}}
onMounted(async()=>{await refresh();if(task.value&&!['completed','failed','cancelled'].includes(task.value.status))startPolling()});onUnmounted(stopPolling)
</script>
<style scoped>.detail{margin-top:20px}.detail-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.detail-header h2{margin:0 0 5px}.muted{color:#8792a6}.actions{display:flex;gap:10px}.el-progress{margin-top:28px}</style>
