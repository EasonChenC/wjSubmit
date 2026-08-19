<template>
  <section class="ratio-editor">
    <el-alert title="比例模式按整个任务计算精确次数，不是逐份随机概率。未勾选的题目继续使用默认策略。" type="info" :closable="false"/>
    <div class="plan-settings"><span>单份失败最大尝试</span><el-input-number v-model="model.max_submit_attempts" :min="1" :max="10"/><small>失败时重复提交同一答案计划，不提前消费下一份配额。</small></div>
    <article v-for="(row,index) in ratioRows" :key="row.question.id" class="ratio-card" :class="{'invalid-card':showSubmitValidation&&validation(row.question)}" :data-question-id="row.question.id">
      <header>
        <el-checkbox v-model="row.config.enabled" @change="onToggle(row.question,row.config)">设置比例</el-checkbox>
        <strong>{{ row.question.ratio_display_key || index+1 }}. {{ row.question.label }}</strong>
        <el-tag size="small">{{typeText(row.question.type)}}</el-tag>
      </header>
      <template v-if="row.config.enabled">
        <div v-for="(option,optionIndex) in row.question.options" :key="optionIndex" class="ratio-option">
          <span>{{optionText(option)}}</span>
          <input
            v-model.number="row.config.options[optionIndex].percentage"
            class="ratio-number-input"
            type="number"
            inputmode="numeric"
            min="0"
            max="100"
            step="1"
            :disabled="mustBeZero(row.question,option)"
            @input="normalizeInput(row.config,optionIndex)"
          />
          <b>%</b>
          <small>预计 {{quota(row.question,optionIndex)}} 次 / {{effectivePercentage(row.question,optionIndex)}}%</small>
        </div>
        <footer :class="{invalid:validation(row.question)}">
          合计 {{total(row.question)}}%
          <span v-if="row.question.ratio_kind==='multiple'">；每份限制 {{row.question.selection_min??1}}～{{row.question.selection_max??row.question.options.length}} 项</span>
          <span v-if="validation(row.question)">；{{validation(row.question)}}</span>
          <span v-else>；配置有效</span>
        </footer>
      </template>
    </article>
    <el-empty v-if="!eligibleQuestions.length" description="当前问卷没有支持比例配置的选择题"/>
  </section>
</template>

<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import type {ProportionConfig,ProportionQuestionConfig,Question} from '@/types'

const props=defineProps<{questions:Question[];count:number}>()
const model=defineModel<ProportionConfig>({required:true})
const eligibleQuestions=computed(()=>props.questions.filter(q=>q.ratio_eligible&&q.options?.length))
const optionValue=(option:any)=>typeof option==='object'?option.value:option
const optionText=(option:any)=>typeof option==='object'?String(option.label??option.value):String(option)
const typeText=(type:string)=>({radio:'单选',checkbox:'多选',select:'下拉',matrix:'矩阵小题',rating:'量表',nps:'NPS'} as Record<string,string>)[type]||type
const sameValue=(a:any,b:any)=>JSON.stringify(a)===JSON.stringify(b)
const mustBeZero=(question:Question,option:any)=>(question.ratio_zero_values||[]).some(value=>sameValue(value,optionValue(option)))
const showSubmitValidation=ref(false)

// 初始化只在题目列表变化时执行。模板渲染、合计和校验函数均不再修改配置，
// 避免输入过程中因重新渲染触发默认均分值覆盖用户正在编辑的数值。
const initializeEntries=()=>{
  for(const question of eligibleQuestions.value){
    if(!model.value.questions.some(item=>item.question_id===question.id)){
      model.value.questions.push({question_id:question.id,enabled:false,options:question.options.map(option=>({value:optionValue(option),percentage:0}))})
    }
  }
}
watch(eligibleQuestions,initializeEntries,{immediate:true})
const configFor=(question:Question):ProportionQuestionConfig=>{
  const current=model.value.questions.find(item=>item.question_id===question.id)
  if(!current)throw new Error(`比例配置尚未初始化: ${question.id}`)
  return current
}
const ratioRows=computed(()=>eligibleQuestions.value.map(question=>({question,config:configFor(question)})))
const onToggle=(question:Question,current:ProportionQuestionConfig)=>{
  showSubmitValidation.value=false
  if(current.enabled&&current.options.every(option=>option.percentage===0)){
    const assignable=current.options.map((_,index)=>index).filter(index=>!mustBeZero(question,question.options[index]))
    if(question.ratio_kind==='multiple') assignable.forEach(index=>current.options[index].percentage=Math.ceil(200/assignable.length))
    else {const base=Math.floor(100/assignable.length);assignable.forEach((optionIndex,index)=>current.options[optionIndex].percentage=index===assignable.length-1?100-base*(assignable.length-1):base)}
    current.options.forEach((option,index)=>{if(mustBeZero(question,question.options[index]))option.percentage=0})
  }
}
const normalizeInput=(config:ProportionQuestionConfig,index:number)=>{
  const value=Number(config.options[index].percentage)
  // 只限制输入范围，不做均分、补足100或恢复默认值；0是合法值。
  if(Number.isNaN(value))return
  if(value<0)config.options[index].percentage=0
  else if(value>100)config.options[index].percentage=100
  else config.options[index].percentage=value
}
const total=(question:Question)=>configFor(question).options.reduce((sum,option)=>sum+Number(option.percentage||0),0)
const quotas=(question:Question)=>{
  const percentages=configFor(question).options.map(option=>Number(option.percentage||0))
  if(question.ratio_kind==='multiple')return percentages.map(percentage=>Math.round(props.count*percentage/100))
  const raw=percentages.map(percentage=>props.count*percentage/100)
  const result=raw.map(Math.floor);let remaining=props.count-result.reduce((a,b)=>a+b,0)
  const order=raw.map((value,index)=>({index,remainder:value-result[index]})).sort((a,b)=>b.remainder-a.remainder||a.index-b.index)
  for(let i=0;i<remaining;i++)result[order[i].index]++
  return result
}
const quota=(question:Question,index:number)=>quotas(question)[index]||0
const effectivePercentage=(question:Question,index:number)=>props.count?Number((quota(question,index)*100/props.count).toFixed(2)):0
const validation=(question:Question)=>{
  const current=configFor(question);if(!current.enabled)return ''
  if(current.options.some((option,index)=>mustBeZero(question,question.options[index])&&option.percentage!==0))return '允许填空的选项比例必须为0%'
  if(current.options.length!==question.options.length)return '比例数量与选项数量不一致'
  const sum=total(question)
  if(question.ratio_kind==='multiple'){
    if(sum<=100)return '多选题合计必须大于100%'
    const selections=quotas(question).reduce((n,value)=>n+value,0)
    const min=(question.selection_min??(question.required?1:0))*props.count
    const max=(question.selection_max??question.options.length)*props.count
    if(selections<min||selections>max)return `预计总勾选${selections}次，页面允许${min}～${max}次`
  }else if(sum!==100)return '比例合计必须等于100%'
  return ''
}
defineExpose({validate:()=>{
  showSubmitValidation.value=true
  const enabled=eligibleQuestions.value.filter(q=>configFor(q).enabled)
  if(!enabled.length)return '请至少勾选一道题设置比例'
  for(const question of enabled){
    const error=validation(question)
    if(error){
      requestAnimationFrame(()=>document.querySelector(`[data-question-id="${CSS.escape(question.id)}"]`)?.scrollIntoView({behavior:'smooth',block:'center'}))
      return `${question.label}：${error}`
    }
  }
  return ''
}})
</script>

<style scoped>
.ratio-editor{margin:18px 0}.plan-settings{display:flex;align-items:center;gap:10px;margin:12px 0;color:#5d687a}.plan-settings small{color:#8792a6}.ratio-card{margin:12px 0;padding:14px;border:1px solid #e4e9f2;border-radius:10px}.ratio-card.invalid-card{border-color:#f06c6c;background:#fff9f9}.ratio-card header{display:flex;align-items:center;gap:10px}.ratio-card header strong{flex:1}.ratio-option{display:grid;grid-template-columns:minmax(180px,1fr) 130px 20px 180px;align-items:center;gap:8px;margin:10px 0 0 26px}.ratio-number-input{box-sizing:border-box;width:130px;height:32px;padding:0 11px;border:1px solid #dcdfe6;border-radius:4px;color:#606266;font:inherit;outline:none;transition:border-color .2s}.ratio-number-input:hover{border-color:#c0c4cc}.ratio-number-input:focus{border-color:#409eff}.ratio-number-input:disabled{background:#f5f7fa;color:#a8abb2;cursor:not-allowed}.ratio-option small{color:#8792a6}.ratio-card footer{margin:12px 0 0 26px;color:#26875d;font-size:12px}.ratio-card footer.invalid{color:#d94b4b}
</style>
