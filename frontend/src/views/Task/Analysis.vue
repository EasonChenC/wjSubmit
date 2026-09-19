<template>
  <div class="analysis-page">
    <el-page-header content="问卷解析详情" @back="$router.push('/tasks')" />
    <section v-if="analysis" class="summary-card">
      <div><div class="eyebrow">QUESTIONNAIRE ANALYSIS</div><h1>{{analysis.title||'未命名问卷'}}</h1><a :href="analysis.url" target="_blank">{{analysis.url}}</a></div>
      <div class="summary-stats"><div><strong>{{analysis.total_questions}}</strong><span>题目总数</span></div><div><strong>{{analysis.scale_questions}}</strong><span>量表题</span></div><div><strong>{{analysis.reverse_items?.length||0}}</strong><span>反向题</span></div><div><strong>{{methodText(analysis.detection_method)}}</strong><span>解析方式</span></div></div>
    </section>
    <section v-if="analysis" class="content-card"><div class="section-head"><div><h2>问卷题目结构</h2><p>展示创建任务时保存的解析结果，不会重新访问问卷页面。</p></div><el-tag effect="plain">{{analysis.platform||'unknown'}}</el-tag></div><QuestionPreview :questions="analysis.questions" /></section>
    <el-skeleton v-else :rows="8" animated />
  </div>
</template>
<script setup lang="ts">
import {onMounted,ref} from 'vue'
import {useRoute} from 'vue-router'
import {ElMessage} from 'element-plus'
import {getTaskAnalysis} from '@/api/task'
import QuestionPreview from '@/components/Questionnaire/QuestionPreview.vue'
import type {Questionnaire} from '@/types'
const route=useRoute();const analysis=ref<(Questionnaire&{platform?:string})|null>(null)
const methodText=(v?:string)=>({ai:'AI',keyword:'关键词',structure:'结构解析'} as Record<string,string>)[v||'']||v||'未知'
onMounted(async()=>{try{analysis.value=(await getTaskAnalysis(String(route.params.id))).data.data as any}catch(e:any){ElMessage.error(e?.response?.data?.detail||'加载解析详情失败')}})
</script>
<style scoped>.analysis-page{width:100%;max-width:none;margin:0;padding:20px 22px}.summary-card{margin-top:20px;padding:26px 30px;border-radius:16px;background:linear-gradient(110deg,#1d3263,#4263b8);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:30px}.eyebrow{font-size:11px;letter-spacing:2px;opacity:.65}.summary-card h1{margin:6px 0 8px;font-size:24px}.summary-card a{color:#d6e2ff;font-size:13px}.summary-stats{display:grid;grid-template-columns:repeat(4,minmax(90px,1fr));gap:12px}.summary-stats div{padding:14px 18px;border:1px solid #ffffff26;border-radius:12px;background:#ffffff0d;text-align:center}.summary-stats strong,.summary-stats span{display:block}.summary-stats strong{font-size:20px}.summary-stats span{margin-top:4px;font-size:11px;opacity:.72}.content-card{margin-top:20px;padding:24px 28px;background:#fff;border-radius:14px;box-shadow:0 4px 20px #1f29370d}.section-head{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #edf0f6;padding-bottom:16px}.section-head h2{margin:0 0 5px}.section-head p{margin:0;color:#8792a6;font-size:13px}@media(max-width:900px){.summary-card{align-items:flex-start;flex-direction:column}.summary-stats{width:100%;grid-template-columns:repeat(2,1fr)}}</style>
