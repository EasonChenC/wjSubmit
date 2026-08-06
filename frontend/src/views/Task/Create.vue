<template><div class="page"><h2>创建新任务</h2><div class="card"><el-steps :active="step" finish-status="success"><el-step title="输入 URL"/><el-step title="预览问卷"/><el-step title="配置提交"/></el-steps><el-form v-if="step===0" class="form" :model="form"><el-form-item label="问卷 URL"><el-input v-model="form.url" placeholder="https://..."/></el-form-item><el-form-item><el-checkbox v-model="form.use_ai" :disabled="!ai.available">使用 AI 识别反向题（需先配置 AI）</el-checkbox><el-link v-if="!ai.available" type="primary" :underline="false" @click="$router.push('/settings/ai')">设置 AI</el-link><p class="ai-hint">启用后，系统将使用 AI 模型智能识别反向题和量表选项方向</p></el-form-item><el-button type="primary" :loading="loading" @click="analyze">解析问卷</el-button></el-form><div v-else-if="step===1"><el-alert title="问卷解析成功" type="success" show-icon/><p>共 {{questionnaire?.total_questions}} 道题，量表题 {{questionnaire?.scale_questions}} 道</p><el-table :data="questionnaire?.questions" max-height="420"><el-table-column prop="id" label="ID" width="90"/><el-table-column prop="label" label="题目"/><el-table-column prop="type" label="题型" width="120"/><el-table-column label="是量表题" width="90" align="center"><template #default="{row}">{{ row.is_scale ? '是' : '否' }}</template></el-table-column><el-table-column label="反向题" width="90" align="center"><template #default="{row}">{{ row.is_scale ? (row.is_reverse ? '是' : '否') : '-' }}</template></el-table-column><el-table-column label="检测方法" width="105"><template #default="{row}"><el-tag v-if="row.detection_method" size="small" :type="row.detection_method==='ai'?'primary':'info'">{{row.detection_method==='ai'?'AI':'关键词'}}</el-tag><span v-else>-</span></template></el-table-column><el-table-column label="积极值" width="105"><template #default="{row}">{{row.is_scale&&row.positive_values?.length?`[${row.positive_values.join(',')}]`:'-'}}</template></el-table-column><el-table-column label="消极值" width="105"><template #default="{row}">{{row.is_scale&&row.negative_values?.length?`[${row.negative_values.join(',')}]`:'-'}}</template></el-table-column></el-table><QuestionPreview v-if="questionnaire" :questions="questionnaire.questions" /><el-button @click="step=0">上一步</el-button><el-button type="primary" @click="step=2">下一步</el-button></div><el-form v-else class="form" :model="form"><el-form-item label="提交数量"><el-input-number v-model="form.count" :min="1" :max="1000"/></el-form-item><el-form-item label="模式"><el-radio-group v-model="form.mode"><el-radio value="random">随机</el-radio><el-radio value="high_reliability">高可靠性</el-radio></el-radio-group></el-form-item><el-form-item v-if="form.mode==='high_reliability'" label="态度"><el-radio-group v-model="form.attitude"><el-radio value="positive">积极</el-radio><el-radio value="negative">消极</el-radio></el-radio-group></el-form-item><el-alert v-if="form.use_ai && questionnaire" type="info" :closable="false" show-icon :title="`AI ???? ${questionnaire.scale_questions} ????`"><template #default><div>???????????/?????????????????/??????</div></template></el-alert><div v-if="form.mode === 'high_reliability' && (form.attitude === 'positive' || form.attitude === 'negative')" class="variation-option"><el-checkbox v-model="form.add_variation">加入随机答案生成</el-checkbox><p class="variation-hint">勾选后，会在保证量表题积极或消极倾向的情况下包含随机答案，使答案没有那么极端。</p><el-form-item v-if="form.add_variation" label="随机答案比例" class="ratio-field"><el-input-number v-model="form.variation_ratio" :min="1" :max="30" :step="1" /><span class="ratio-unit">%</span></el-form-item></div><div><el-button @click="step=1">上一步</el-button><el-button type="primary" :loading="loading" @click="create">创建并开始任务</el-button></div></el-form></div></div></template>
<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { analyzeQuestionnaire } from '@/api/questionnaire'
import { useTaskStore } from '@/stores/task'
import { useAiStore } from '@/stores/ai'
import type { Questionnaire } from '@/types'
import QuestionPreview from '@/components/Questionnaire/QuestionPreview.vue'

const step = ref(0)
const loading = ref(false)
const questionnaire = ref<Questionnaire>()
const form = reactive({
  url: '', count: 10, mode: 'random' as 'random' | 'high_reliability',
  attitude: 'positive' as 'positive' | 'negative', use_ai: localStorage.getItem('questionnaire_use_ai') === 'true', add_variation: false, variation_ratio: 15,
})
watch(() => form.use_ai, value => localStorage.setItem('questionnaire_use_ai', String(value)))
const store = useTaskStore()
const ai = useAiStore()
const router = useRouter()
onMounted(() => ai.fetchConfig())

const analyze = async () => {
  if (!form.url) {
    ElMessage.warning('请输入问卷 URL')
    return
  }
  loading.value = true
  try {
    questionnaire.value = (await analyzeQuestionnaire(form.url, form.use_ai)).data.data
    step.value = 1
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '解析失败')
  } finally {
    loading.value = false
  }
}

const create = async () => {
  loading.value = true
  try {
    const task = await store.create({
      url: form.url, count: form.count, mode: form.mode,
      config: form.mode === 'high_reliability' ? {
        attitude: form.attitude, add_variation: form.add_variation,
        variation_ratio: form.variation_ratio / 100,
      } : undefined,
    })
    await router.push(`/tasks/${task.task_id}`)
  } catch {
    ElMessage.error('创建任务失败')
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>.form{max-width:650px;margin:40px auto}.el-steps{margin-bottom:36px}.el-button{margin:20px 8px 0 0} .variation-hint{margin:6px 0 0 24px;color:#8792a6;font-size:12px;line-height:1.5}.variation-option{margin-top:8px}.ratio-field{margin:14px 0 0 24px}.ratio-unit{margin-left:8px;color:#657085}</style>
