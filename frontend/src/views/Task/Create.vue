<template>
  <div class="page">
    <h2>创建新任务</h2>
    <div class="card">
      <el-steps :active="step" finish-status="success">
        <el-step title="输入 URL"/><el-step title="预览问卷"/><el-step title="配置提交"/>
      </el-steps>

      <el-form v-if="step===0" class="form" :model="form">
        <el-form-item label="问卷 URL"><el-input v-model="form.url" placeholder="https://..."/></el-form-item>
        <el-form-item label="回答模式"><el-radio-group v-model="form.mode"><el-radio value="random">随机作答</el-radio><el-radio value="high_reliability">AI倾向作答</el-radio><el-radio value="proportional">按选项比例作答</el-radio></el-radio-group></el-form-item>
        <el-alert v-if="form.mode==='proportional'" title="比例模式只解析页面题型和选项，不调用AI识别正反向题。" type="info" :closable="false"/>
        <el-form-item v-else>
          <el-checkbox v-model="form.use_ai" :disabled="!ai.available">使用 AI 识别反向题（需先配置 AI）</el-checkbox>
          <el-link v-if="!ai.available" type="primary" :underline="false" @click="router.push('/settings/ai')">设置 AI</el-link>
          <p class="hint">启用后，系统将使用 AI 模型智能识别反向题和量表选项方向。</p>
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="analyze">解析问卷</el-button>
      </el-form>

      <div v-else-if="step===1">
        <el-alert title="问卷解析成功" type="success" show-icon/>
        <p>共 {{ questionnaire?.total_questions }} 道题，量表题 {{ questionnaire?.scale_questions }} 道</p>
        <el-table :data="questionnaire?.questions" max-height="420">
          <el-table-column prop="id" label="ID" width="90"/><el-table-column prop="label" label="题目"/>
          <el-table-column prop="type" label="题型" width="120"/>
          <el-table-column label="量表题" width="90" align="center"><template #default="{row}">{{row.is_scale?'是':'否'}}</template></el-table-column>
          <el-table-column label="反向题" width="90" align="center"><template #default="{row}">{{row.is_scale?(row.is_reverse?'是':'否'):'-'}}</template></el-table-column>
        </el-table>
        <QuestionPreview v-if="questionnaire" :questions="questionnaire.questions"/>
        <el-form v-if="form.mode==='proportional'"><el-form-item label="提交数量"><el-input-number v-model="form.count" :min="1" :max="1000"/></el-form-item></el-form>
        <ProportionQuestionConfig v-if="questionnaire&&form.mode==='proportional'" ref="proportionEditor" v-model="form.proportion_config" :questions="questionnaire.questions" :count="form.count"/>
        <el-button @click="step=0">上一步</el-button><el-button type="primary" @click="nextFromPreview">下一步</el-button>
      </div>

      <el-form v-else class="form" :model="form">
        <el-form-item label="提交数量"><el-input-number v-model="form.count" :min="1" :max="1000"/></el-form-item>
        <el-form-item label="模式"><el-tag>{{modeText(form.mode)}}</el-tag></el-form-item>
        <el-form-item label="单份最大尝试"><el-input-number v-model="form.max_submit_attempts" :min="1" :max="10"/><span class="inline-hint">本份失败会重试，不会消费下一份任务配额。</span></el-form-item>
        <el-form-item v-if="form.mode==='high_reliability'" label="态度"><el-radio-group v-model="form.attitude"><el-radio value="positive">积极</el-radio><el-radio value="negative">消极</el-radio></el-radio-group></el-form-item>
        <div v-if="form.mode==='high_reliability'" class="variation-option">
          <el-checkbox v-model="form.add_variation">加入随机答案生成</el-checkbox>
          <el-form-item v-if="form.add_variation" label="随机答案比例" class="ratio-field"><el-input-number v-model="form.variation_ratio" :min="1" :max="30"/><span class="ratio-unit">%</span></el-form-item>
        </div>
        <el-divider content-position="left">文本题 AI 作答</el-divider>
        <el-form-item label="AI 批量生成">
          <el-switch v-model="form.ai_text.enabled" :disabled="!ai.available || textQuestionCount===0"/>
          <p class="hint">
            共 {{ textQuestionCount }} 道文本题（单行 {{ singleLineTextCount }} 道，多行 {{ multilineTextCount }} 道）；启用后将在浏览器提交前预生成并持久化
            {{ form.count * textQuestionCount }} 条回答，再按第 N 份问卷确定性使用第 N 组回答。
          </p>
          <el-link v-if="!ai.available" type="primary" :underline="false" @click="router.push('/settings/ai')">设置 AI</el-link>
        </el-form-item>
        <template v-if="form.ai_text.enabled">
          <el-form-item label="生成批次大小"><el-input-number v-model="form.ai_text.batch_size" :min="1" :max="50"/><p class="hint">每次模型调用生成的问卷份数，默认 20。</p></el-form-item>
          <el-form-item label="批次最大尝试"><el-input-number v-model="form.ai_text.max_generation_attempts" :min="1" :max="5"/></el-form-item>
        </template>
        <ProxyConfigForm v-model="form.proxy"/>
        <el-form-item label="浏览器调试"><el-switch v-model="form.debug"/><p class="hint">开启后显示浏览器窗口；关闭则无头运行。</p></el-form-item>
        <el-button @click="step=1">上一步</el-button><el-button type="primary" :loading="loading" @click="create">创建并开始任务</el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { analyzeQuestionnaire } from '@/api/questionnaire'
import { useTaskStore } from '@/stores/task'
import { useAiStore } from '@/stores/ai'
import type { ProxyConfig, Questionnaire } from '@/types'
import QuestionPreview from '@/components/Questionnaire/QuestionPreview.vue'
import ProxyConfigForm from '@/components/Task/ProxyConfigForm.vue'
import ProportionQuestionConfig from '@/components/Task/ProportionQuestionConfig.vue'

const defaultProxy=():ProxyConfig=>({enabled:false,provider:'kuaidaili',area:'',carrier:0,rotate_per_submission:true,dedup:true,verify_exit:true,location_match:'relaxed',required:true,max_acquire_attempts:3})
const step=ref(0); const loading=ref(false); const questionnaire=ref<Questionnaire>(); const proportionEditor=ref<any>()
const form=reactive({url:'',count:10,max_submit_attempts:10,mode:'random' as 'random'|'high_reliability'|'proportional',attitude:'positive' as 'positive'|'negative',use_ai:localStorage.getItem('questionnaire_use_ai')==='true',add_variation:false,variation_ratio:15,debug:false,proxy:defaultProxy(),ai_text:{enabled:false,batch_size:20,max_generation_attempts:3},proportion_config:{questions:[] as any[],seed:0,max_submit_attempts:10}})
const store=useTaskStore(); const ai=useAiStore(); const router=useRouter()
const singleLineTextCount=computed(()=>questionnaire.value?.questions.filter(q=>q.type==='text').length||0)
const multilineTextCount=computed(()=>questionnaire.value?.questions.filter(q=>q.type==='textarea').length||0)
const textQuestionCount=computed(()=>singleLineTextCount.value+multilineTextCount.value)
const modeText=(mode:string)=>({random:'随机作答',high_reliability:'AI倾向作答',proportional:'按选项比例作答'} as Record<string,string>)[mode]||mode
watch(()=>form.use_ai,v=>localStorage.setItem('questionnaire_use_ai',String(v)))
onMounted(()=>ai.fetchConfig())

const analyze=async()=>{if(!form.url)return ElMessage.warning('请输入问卷 URL');loading.value=true;try{form.proportion_config.questions=[];questionnaire.value=(await analyzeQuestionnaire(form.url,form.use_ai,form.mode==='proportional'?'proportional':'standard')).data.data;step.value=1}catch(error:any){ElMessage.error(error.response?.data?.detail||'解析失败')}finally{loading.value=false}}
const nextFromPreview=()=>{if(form.mode==='proportional'){const error=proportionEditor.value?.validate();if(error)return ElMessage.warning(error)}step.value=2}
const create=async()=>{if(!questionnaire.value)return ElMessage.error('请先解析问卷');if(form.proxy.enabled&&!form.proxy.area.trim())return ElMessage.warning('请输入代理目标地区');if(form.ai_text.enabled&&!ai.available)return ElMessage.warning('请先配置并启用 AI');if(form.mode==='proportional'){const error=proportionEditor.value?.validate();if(error)return ElMessage.warning(error)}loading.value=true;try{const task=await store.create({task_id:questionnaire.value.task_id,url:form.url,count:form.count,mode:form.mode,proxy:form.proxy,ai_text:form.ai_text,proportion_config:form.mode==='proportional'?form.proportion_config:undefined,config:{attitude:form.attitude,add_variation:form.mode==='high_reliability'?form.add_variation:false,variation_ratio:form.mode==='high_reliability'?form.variation_ratio/100:0.05,debug:form.debug,max_submit_attempts:form.max_submit_attempts}});await router.push(`/tasks/${task.task_id}`)}catch(error:any){ElMessage.error(error.response?.data?.detail||'创建任务失败')}finally{loading.value=false}}
</script>

<style scoped>.form{max-width:680px;margin:40px auto}.el-steps{margin-bottom:36px}.el-button{margin:20px 8px 0 0}.hint{margin:6px 0 0;color:#8792a6;font-size:12px}.variation-option{margin-top:8px}.ratio-field{margin:14px 0 0 24px}.ratio-unit{margin-left:8px}</style>
