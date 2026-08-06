<template>
  <div class="question-list">
    <article v-for="(question, index) in questions" :key="question.id" class="question-card">
      <div class="q-head">
        <span class="q-index">{{ index + 1 }}</span>
        <div class="q-title">{{ question.label }}</div>
        <el-tag size="small" effect="plain">{{ typeText(question.type) }}</el-tag>
        <el-tag v-if="question.is_scale" size="small" type="success">量表题</el-tag>
        <el-tag v-if="question.required" size="small" type="danger" effect="plain">必填</el-tag>
        <el-tag v-if="question.is_scale && question.is_reverse" size="small" class="reverse-tag">↺ 反向题</el-tag>
        <el-tag v-else-if="question.is_scale" size="small" type="info" effect="plain">正向题</el-tag>
        <el-tag v-if="question.detection_method" size="small" :type="question.detection_method === 'ai' ? 'primary' : 'info'">
          {{ question.detection_method === 'ai' ? '🤖 AI' : '📝 关键词' }}
        </el-tag>
      </div>
      <div v-if="question.options?.length" class="options">
        <div v-for="(option, optionIndex) in question.options" :key="optionIndex" class="option">
          <span class="option-no">{{ optionIndex + 1 }}</span><span>{{ optionText(option) }}</span>
          <el-tag v-if="valueClass(question, option)" size="small" :type="valueClass(question, option)!.type">{{ valueClass(question, option)!.label }}</el-tag>
        </div>
      </div>
      <div v-else class="no-options">文本输入题，无预设选项</div>
    </article>
  </div>
</template>
<script setup lang="ts">
import type { Question } from '@/types'
defineProps<{ questions: Question[] }>()
const labels: Record<string, string> = { radio:'单选题', checkbox:'多选题', select:'下拉选择', text:'单行文本', textarea:'多行文本', matrix:'矩阵评分', rating:'评分题', nps:'NPS推荐度', sort:'排序题', weight_allocation:'权重分配', unknown:'未识别' }
const typeText = (type: string) => labels[type] || type
const optionText = (option: any) => typeof option === 'object' ? `${option.title ?? option.label ?? ''}${option.rowid != null ? `（编号 ${option.rowid}）` : ''}` : String(option)
const hasValue=(values:any[]|undefined,option:any)=>values?.map(String).includes(String(typeof option==='object' ? option.rowid ?? option.value : option))
const valueClass=(question:Question,option:any)=>hasValue(question.positive_values,option)?{label:'积极',type:'success' as const}:hasValue(question.negative_values,option)?{label:'消极',type:'danger' as const}:hasValue(question.neutral_values,option)?{label:'中立',type:'info' as const}:null
</script>
<style scoped>
.question-card{padding:16px 0;border-bottom:1px solid #edf0f6}.q-head{display:flex;align-items:center;gap:8px}.q-index{display:grid;place-items:center;width:25px;height:25px;border-radius:8px;background:#edf2ff;color:#4164d8;font-weight:700;font-size:12px}.q-title{flex:1;font-size:14px;line-height:1.5}.reverse-tag{background:linear-gradient(135deg,#fff0f3,#f8e8ff)!important;border-color:#e58aa2!important;color:#b4235a!important;font-weight:700;box-shadow:0 2px 8px #d84e7626}.options{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin:12px 0 0 33px}.option{display:flex;gap:8px;align-items:center;padding:8px 10px;border-radius:7px;background:#f7f9fc;color:#5d687a;font-size:13px}.option-no{color:#7184cd;font-weight:600}.no-options{margin:12px 0 0 33px;color:#a0a9b8;font-size:12px}
</style>
