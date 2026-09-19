<template>
  <div class="page">
    <div class="hero">
      <div><div class="eyebrow">WORKSPACE / TASKS</div><h2>&#20219;&#21153;&#31649;&#29702;</h2><p>&#38598;&#20013;&#21019;&#24314;&#12289;&#30417;&#25511;&#21644;&#31649;&#29702;&#38382;&#21367;&#33258;&#21160;&#21270;&#20219;&#21153;</p></div>
      <el-button class="create-btn" type="primary" size="large" @click="dialog=true">&#65291; &#21019;&#24314;&#26032;&#20219;&#21153;</el-button>
    </div>
    <div class="stats">
      <div class="stat"><span>&#20840;&#37096;&#20219;&#21153;</span><strong>{{store.total}}</strong></div>
      <div class="stat blue"><span>&#24403;&#21069;&#39029;&#36827;&#34892;&#20013;</span><strong>{{activeCount}}</strong></div>
      <div class="stat green"><span>&#24403;&#21069;&#39029;&#24050;&#23436;&#25104;</span><strong>{{doneCount}}</strong></div>
      <div class="stat orange"><span>&#24403;&#21069;&#39029;&#25104;&#21151;&#25552;&#20132;</span><strong>{{successCount}}</strong></div>
    </div>
    <div class="card table-card">
      <div class="task-toolbar">
        <el-input v-model="searchText" clearable placeholder="&#25628;&#32034;&#20219;&#21153;&#26631;&#39064;&#12289;&#38382;&#21367; URL &#25110;&#21019;&#24314;&#20154;&#21592;" @keyup.enter="searchTasks" @clear="searchTasks" />
        <el-select v-if="userStore.role==='admin'" v-model="ownerId" clearable filterable placeholder="&#20840;&#37096;&#21019;&#24314;&#20154;&#21592;" @change="searchTasks">
          <el-option v-for="owner in owners" :key="owner.id" :label="owner.username" :value="owner.id" />
        </el-select>
        <el-button type="primary" @click="searchTasks">&#25628;&#32034;</el-button>
      </div>
      <el-empty v-if="!store.tasks.length&&!store.loading" description="&#36824;&#27809;&#26377;&#20219;&#21153;" />
      <el-table v-else :data="store.tasks" v-loading="store.loading" stripe>
        <el-table-column label="&#20219;&#21153;&#21517;&#31216;" min-width="210"><template #default="{row}"><el-link type="primary" @click="router.push('/tasks/'+row.task_id)">{{row.title||'\u672a\u547d\u540d\u95ee\u5377'}}</el-link></template></el-table-column>
        <el-table-column prop="url" label="&#38382;&#21367; URL" min-width="250" show-overflow-tooltip />
        <el-table-column label="&#21019;&#24314;&#20154;&#21592;" width="130"><template #default="{row}"><el-tag type="info" effect="plain">{{row.creator_username||'\u672a\u77e5\u7528\u6237'}}</el-tag></template></el-table-column>
        <el-table-column label="&#20195;&#29702;&#22320;&#21306;" width="110"><template #default="{row}"><el-tag v-if="row.proxy?.enabled" type="info">{{row.proxy.area}}</el-tag><span v-else>&#30452;&#36830;</span></template></el-table-column>
        <el-table-column label="&#36827;&#24230;" width="180"><template #default="{row}"><el-progress :percentage="row.progress" /></template></el-table-column>
        <el-table-column label="&#29366;&#24577;" width="110"><template #default="{row}"><el-tag>{{statusText(row.status)}}</el-tag></template></el-table-column>
        <el-table-column label="&#25805;&#20316;" width="280" fixed="right"><template #default="{row}"><el-button link type="primary" @click="router.push('/tasks/'+row.task_id)">&#20219;&#21153;&#35814;&#24773;</el-button><el-button link type="primary" @click="openConfig(row.task_id)">&#26597;&#30475;&#37197;&#32622;</el-button><el-button link type="primary" @click="router.push('/tasks/'+row.task_id+'/analysis')">&#38382;&#21367;&#35299;&#26512;&#35814;&#24773;</el-button><el-button v-if="row.can_resume" link type="primary" @click="resumeFromList(row.task_id)">&#32487;&#32493;</el-button><el-button v-if="userStore.role==='admin'" link type="danger" @click="remove(row.task_id)">&#21024;&#38500;</el-button></template></el-table-column>
      </el-table>
      <div class="task-pagination"><span>&#20849; {{store.total}} &#26465;&#20219;&#21153;</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev, pager, next" :total="store.total" @current-change="loadTasks" /></div>
    </div>

    <el-dialog v-model="configDialog" title="任务配置" width="680px" destroy-on-close>
      <el-alert v-if="configTaskStatus==='processing'||configTaskStatus==='pending'" title="运行中的任务需先停止后才能修改配置" type="warning" :closable="false" />
      <el-form v-if="taskConfig" label-width="130px">
        <el-form-item label="作答模式"><el-select v-model="taskConfig.mode"><el-option label="随机作答" value="random"/><el-option label="AI 倾向作答" value="high_reliability"/><el-option label="按选项比例" value="proportional"/></el-select></el-form-item>
        <el-form-item v-if="taskConfig.mode==='high_reliability'" label="可靠性态度"><el-radio-group v-model="taskConfig.attitude"><el-radio value="positive">积极</el-radio><el-radio value="negative">消极</el-radio></el-radio-group></el-form-item>
        <el-form-item label="提交失败重试"><el-input-number v-model="taskConfig.max_submit_attempts" :min="1" :max="10"/></el-form-item>
        <el-form-item label="答案变异"><el-switch v-model="taskConfig.add_variation"/></el-form-item>
        <el-form-item v-if="taskConfig.add_variation" label="变异比例"><el-input-number v-model="taskConfig.variation_ratio" :min="0.01" :max="0.3" :step="0.01"/></el-form-item>
        <el-divider content-position="left">代理配置</el-divider>
        <el-form-item label="启用代理"><el-switch v-model="taskConfig.proxy.enabled"/></el-form-item>
        <template v-if="taskConfig.proxy.enabled"><el-form-item label="目标地区"><el-input v-model="taskConfig.proxy.area"/></el-form-item><el-form-item label="运营商"><el-select v-model="taskConfig.proxy.carrier"><el-option label="不限" :value="0"/><el-option label="联通" :value="1"/><el-option label="电信" :value="2"/><el-option label="移动" :value="3"/></el-select></el-form-item><el-form-item label="严格地区匹配"><el-switch v-model="strictProxy"/></el-form-item></template>
        <el-divider content-position="left">AI 文本答案</el-divider>
        <el-form-item label="启用 AI 文本"><el-switch v-model="taskConfig.ai_text.enabled" :disabled="userStore.role!=='admin'||!ai.available"/></el-form-item>
        <template v-if="taskConfig.ai_text.enabled"><el-form-item label="批量生成份数"><el-input-number v-model="taskConfig.ai_text.batch_size" :min="1" :max="50"/></el-form-item><el-form-item label="生成失败重试"><el-input-number v-model="taskConfig.ai_text.max_generation_attempts" :min="1" :max="5"/></el-form-item></template>
        <el-form-item v-if="taskConfig.proportion_config" label="比例配置 JSON"><el-input v-model="proportionJson" type="textarea" :rows="7"/><div class="field-hint">保存前必须是合法 JSON。</div></el-form-item>
        <el-form-item label="浏览器调试"><el-switch v-model="taskConfig.debug"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="configDialog=false">取消</el-button><el-button type="primary" :loading="configSaving" :disabled="configTaskStatus==='processing'||configTaskStatus==='pending'" @click="saveConfig">保存配置</el-button></template>
    </el-dialog>

    <el-dialog v-model="dialog" title="&#21019;&#24314;&#26032;&#20219;&#21153;" width="720px" destroy-on-close>
      <el-steps :active="step" finish-status="success" simple><el-step title="&#36755;&#20837; URL"/><el-step title="&#39044;&#35272;&#38382;&#21367;"/><el-step title="&#37197;&#32622;&#25552;&#20132;"/></el-steps>
      <el-form v-if="step===0" class="wizard-form" :model="form">
        <el-form-item label="&#38382;&#21367; URL"><el-input v-model="form.url"/></el-form-item>
        <el-form-item label="&#22238;&#31572;&#27169;&#24335;"><el-radio-group v-model="form.mode"><el-radio value="random">&#38543;&#26426;&#20316;&#31572;</el-radio><el-radio value="high_reliability">AI &#20542;&#21521;&#20316;&#31572;</el-radio><el-radio value="proportional">&#25353;&#36873;&#39033;&#27604;&#20363;&#20316;&#31572;</el-radio></el-radio-group></el-form-item>
        <el-alert v-if="form.mode==='proportional'" title="&#27604;&#20363;&#27169;&#24335;&#21482;&#35299;&#26512;&#39029;&#38754;&#39064;&#22411;&#21644;&#36873;&#39033;&#65292;&#19981;&#35843;&#29992; AI &#35782;&#21035;&#27491;&#21453;&#21521;&#39064;&#12290;" type="info" :closable="false"/>
        <el-checkbox v-else-if="userStore.role==='admin'" v-model="form.use_ai" :disabled="!ai.available">&#20351;&#29992; AI &#35782;&#21035;&#21453;&#21521;&#39064;</el-checkbox><br/>
        <el-button type="primary" :loading="loading" @click="analyze">&#20998;&#26512;&#38382;&#21367;</el-button>
      </el-form>
      <div v-else-if="step===1">
        <el-alert title="&#38382;&#21367;&#20998;&#26512;&#25104;&#21151;" type="success" show-icon/><p>&#20849; {{questionnaire?.total_questions}} &#36947;&#39064;</p>
        <QuestionPreview v-if="questionnaire" :questions="questionnaire.questions"/>
        <el-checkbox v-if="form.use_ai&&form.mode!=='proportional'" v-model="form.use_ratio">&#37197;&#32622;&#38750;&#37327;&#34920;&#39064;&#30340;&#36873;&#39033;&#22238;&#31572;&#27604;&#20363;</el-checkbox>
        <el-alert v-if="form.use_ratio" title="&#37327;&#34920;&#39064;&#20173;&#25353;&#21487;&#38752;&#24615;&#31574;&#30053;&#20316;&#31572;&#65292;&#20165;&#38750;&#37327;&#34920;&#36873;&#25321;&#39064;&#21487;&#37197;&#32622;&#27604;&#20363;&#12290;" type="info" :closable="false"/>
        <el-form v-if="form.mode==='proportional'||form.use_ratio" class="ratio-count"><el-form-item label="&#25552;&#20132;&#25968;&#37327;"><el-input-number v-model="form.count" :min="1" :max="1000"/><span class="inline-hint">&#27604;&#20363;&#30340;&#39044;&#35745;&#27425;&#25968;&#25353;&#27492;&#25968;&#37327;&#23454;&#26102;&#35745;&#31639;&#65292;&#19979;&#19968;&#27493;&#23558;&#33258;&#21160;&#20351;&#29992;&#35813;&#25968;&#37327;&#12290;</span></el-form-item></el-form>
        <ProportionQuestionConfig v-if="questionnaire&&(form.mode==='proportional'||form.use_ratio)" ref="proportionEditor" v-model="form.proportion_config" :questions="questionnaire.questions" :count="form.count"/>
        <el-button @click="step=0">&#19978;&#19968;&#27493;</el-button><el-button type="primary" @click="nextFromPreview">&#19979;&#19968;&#27493;</el-button>
      </div>
      <el-form v-else class="wizard-form" :model="form">
        <el-form-item label="&#25552;&#20132;&#25968;&#37327;"><el-input-number v-model="form.count" :min="1" :max="1000"/></el-form-item>
        <el-form-item label="&#27169;&#24335;"><el-tag>{{modeText(form.mode)}}</el-tag></el-form-item>
        <el-form-item label="&#21333;&#20221;&#26368;&#22823;&#23581;&#35797;"><el-input-number v-model="form.max_submit_attempts" :min="1" :max="10"/><span class="inline-hint">&#26412;&#20221;&#22833;&#36133;&#20250;&#37325;&#35797;&#65292;&#19981;&#28040;&#32791;&#19979;&#19968;&#20221;&#37197;&#39069;&#12290;</span></el-form-item>
        <el-form-item v-if="form.mode==='high_reliability'" label="&#24577;&#24230;"><el-radio-group v-model="form.attitude"><el-radio value="positive">&#31215;&#26497;</el-radio><el-radio value="negative">&#28040;&#26497;</el-radio></el-radio-group></el-form-item>
        <div v-if="form.mode==='high_reliability'" class="variation-option">
          <el-checkbox v-model="form.add_variation">&#21152;&#20837;&#38543;&#26426;&#31572;&#26696;&#29983;&#25104;</el-checkbox>
          <el-form-item v-if="form.add_variation" label="&#38543;&#26426;&#31572;&#26696;&#27604;&#20363;" class="ratio-field"><el-input-number v-model="form.variation_ratio" :min="1" :max="30"/><span class="ratio-unit">%</span></el-form-item>
        </div>
        <el-alert v-if="form.mode==='proportional'" title="&#27604;&#20363;&#37197;&#32622;&#24050;&#22312;&#19978;&#19968;&#27493;&#23436;&#25104;&#65292;&#36820;&#22238;&#19978;&#19968;&#27493;&#21487;&#32487;&#32493;&#35843;&#25972;&#12290;" type="info" :closable="false"/>
        <template v-if="userStore.role==='admin'">
          <el-divider content-position="left">&#25991;&#26412;&#39064; AI &#20316;&#31572;</el-divider>
          <el-form-item label="AI &#25209;&#37327;&#29983;&#25104;"><el-switch v-model="form.ai_text.enabled" :disabled="!ai.available||textQuestionCount===0"/><div class="field-hint">&#26816;&#27979;&#21040; {{textQuestionCount}} &#36947;&#25991;&#26412;&#39064;&#65288;&#21333;&#34892; {{singleLineTextCount}} &#36947;&#65292;&#22810;&#34892; {{multilineTextCount}} &#36947;&#65289;&#12290;</div><el-link v-if="!ai.available" type="primary" :underline="false" @click="router.push('/settings/ai')">&#35831;&#20808;&#37197;&#32622;&#24182;&#21551;&#29992; AI</el-link><div v-else-if="textQuestionCount===0" class="field-hint">&#24403;&#21069;&#38382;&#21367;&#27809;&#26377;&#25991;&#26412;&#39064;&#12290;</div></el-form-item>
          <template v-if="form.ai_text.enabled"><el-form-item label="&#27599;&#25209;&#29983;&#25104;&#20221;&#25968;"><el-input-number v-model="form.ai_text.batch_size" :min="1" :max="50"/></el-form-item><el-form-item label="&#22833;&#36133;&#26368;&#22823;&#23581;&#35797;"><el-input-number v-model="form.ai_text.max_generation_attempts" :min="1" :max="5"/></el-form-item></template>
        </template>
        <ProxyConfigForm v-model="form.proxy"/>
        <el-form-item label="&#27983;&#35272;&#22120;&#35843;&#35797;"><el-switch v-model="form.debug"/></el-form-item>
        <el-button @click="step=1">&#19978;&#19968;&#27493;</el-button><el-button type="primary" :loading="loading" @click="create">&#21019;&#24314;&#24182;&#24320;&#22987;&#20219;&#21153;</el-button>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {computed,onMounted,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {useRouter} from 'vue-router'
import {useTaskStore} from '@/stores/task'; import {useAiStore} from '@/stores/ai'; import {useUserStore} from '@/stores/user'; import {analyzeQuestionnaire} from '@/api/questionnaire'; import {listUsers} from '@/api/users'; import {getTaskConfig,updateTaskConfig} from '@/api/task'
import type {ProxyConfig,Questionnaire} from '@/types'
import QuestionPreview from '@/components/Questionnaire/QuestionPreview.vue'; import ProxyConfigForm from '@/components/Task/ProxyConfigForm.vue'; import ProportionQuestionConfig from '@/components/Task/ProportionQuestionConfig.vue'
const defaultProxy=():ProxyConfig=>({enabled:false,provider:'kuaidaili',area:'',carrier:0,rotate_per_submission:true,dedup:true,verify_exit:true,location_match:'relaxed',required:true,max_acquire_attempts:3})
const store=useTaskStore(),ai=useAiStore(),userStore=useUserStore(),router=useRouter();const dialog=ref(false),step=ref(0),loading=ref(false),questionnaire=ref<Questionnaire>(),proportionEditor=ref<any>()
const form=reactive({url:'',count:10,max_submit_attempts:10,mode:'random' as 'random'|'high_reliability'|'proportional',attitude:'positive' as 'positive'|'negative',use_ai:localStorage.getItem('questionnaire_use_ai')==='true',use_ratio:false,add_variation:false,variation_ratio:15,debug:false,proxy:defaultProxy(),ai_text:{enabled:false,batch_size:20,max_generation_attempts:3},proportion_config:{questions:[] as any[],seed:0,max_submit_attempts:10}})
watch(()=>form.use_ai,v=>localStorage.setItem('questionnaire_use_ai',String(v)));const page=ref(1),pageSize=ref(20),searchText=ref(''),ownerId=ref(''),owners=ref<Array<{id:string;username:string}>>([]);const loadTasks=()=>store.fetchList({q:searchText.value||undefined,owner_id:ownerId.value||undefined,offset:(page.value-1)*pageSize.value,limit:pageSize.value});const searchTasks=()=>{page.value=1;loadTasks()};onMounted(async()=>{await loadTasks();if(userStore.role==='admin'){ai.fetchConfig();try{owners.value=(await listUsers({limit:100,status:'active'})).data.data.items}catch{}}})
const activeCount=computed(()=>store.tasks.filter(t=>t.status==='processing'||t.status==='pending').length),doneCount=computed(()=>store.tasks.filter(t=>t.status==='completed').length),successCount=computed(()=>store.tasks.reduce((n,t)=>n+t.submitted,0));const statusText=(v:string)=>({pending:'\u7b49\u5f85\u4e2d',processing:'\u8fdb\u884c\u4e2d',completed:'\u5df2\u5b8c\u6210',failed:'\u5931\u8d25',cancelled:'\u5df2\u505c\u6b62'} as Record<string,string>)[v]||v
const singleLineTextCount=computed(()=>questionnaire.value?.questions.filter(q=>q.type==='text').length||0)
const multilineTextCount=computed(()=>questionnaire.value?.questions.filter(q=>q.type==='textarea').length||0)
const textQuestionCount=computed(()=>singleLineTextCount.value+multilineTextCount.value)
const modeText=(mode:string)=>({random:'\u968f\u673a\u4f5c\u7b54',high_reliability:'AI\u503e\u5411\u4f5c\u7b54',proportional:'\u6309\u9009\u9879\u6bd4\u4f8b\u4f5c\u7b54'} as Record<string,string>)[mode]||mode
const remove=async(id:string)=>{if(userStore.role!=='admin')return;try{await ElMessageBox.confirm('\u786e\u5b9a\u5220\u9664\u8be5\u4efb\u52a1\u5417\uff1f','\u786e\u8ba4');await store.remove(id);await loadTasks();ElMessage.success('\u5df2\u5220\u9664')}catch{}}
const configDialog=ref(false),configSaving=ref(false),taskConfig=ref<any>(null),configTaskStatus=ref(''),proportionJson=ref(''),strictProxy=ref(false)
const openConfig=async(id:string)=>{try{const data=(await getTaskConfig(id)).data.data;taskConfig.value=data;configTaskStatus.value=store.tasks.find(t=>t.task_id===id)?.status||'';strictProxy.value=data.proxy.location_match==='strict';proportionJson.value=data.proportion_config?JSON.stringify(data.proportion_config,null,2):'';configDialog.value=true}catch(e:any){ElMessage.error(e?.response?.data?.detail||'读取配置失败')}}
const saveConfig=async()=>{if(!taskConfig.value)return;configSaving.value=true;try{let proportion=taskConfig.value.proportion_config;if(proportionJson.value.trim()){try{proportion=JSON.parse(proportionJson.value)}catch{return ElMessage.error('比例配置 JSON 格式错误')}}else proportion=null;taskConfig.value.proxy.location_match=strictProxy.value?'strict':'relaxed';await updateTaskConfig(taskConfig.value.task_id,{mode:taskConfig.value.mode,attitude:taskConfig.value.attitude,add_variation:taskConfig.value.add_variation,variation_ratio:taskConfig.value.variation_ratio,debug:taskConfig.value.debug,max_submit_attempts:taskConfig.value.max_submit_attempts,proxy:taskConfig.value.proxy,ai_text:taskConfig.value.ai_text,proportion_config:proportion});ElMessage.success('配置已保存');configDialog.value=false}catch(e:any){ElMessage.error(e?.response?.data?.detail||'保存配置失败')}finally{configSaving.value=false}}
const resumeFromList=async(id:string)=>{try{await ElMessageBox.confirm('\u4efb\u52a1\u5c06\u4ece\u5df2\u786e\u8ba4\u6210\u529f\u7684\u65ad\u70b9\u7ee7\u7eed\u6267\u884c\u3002','\u7ee7\u7eed\u4efb\u52a1');await store.resume(id);await loadTasks();ElMessage.success('\u4efb\u52a1\u5df2\u6062\u590d')}catch(error:any){if(error!=='cancel'&&error!=='close')ElMessage.error(error?.response?.data?.detail||'\u6062\u590d\u4efb\u52a1\u5931\u8d25')}}
const analyze=async()=>{if(!form.url)return ElMessage.warning('\u8bf7\u8f93\u5165\u95ee\u5377 URL');loading.value=true;try{form.proportion_config.questions=[];questionnaire.value=(await analyzeQuestionnaire(form.url,form.use_ai,form.mode==='proportional'?'proportional':'standard')).data.data;step.value=1}catch(error:any){ElMessage.error(error.response?.data?.detail||'\u5206\u6790\u5931\u8d25')}finally{loading.value=false}}
const nextFromPreview=()=>{if(form.mode==='proportional'||form.use_ratio){const error=proportionEditor.value?.validate();if(error)return ElMessage.warning(error)}step.value=2}
const create=async()=>{if(!questionnaire.value)return ElMessage.error('\u8bf7\u5148\u5206\u6790\u95ee\u5377');if(form.proxy.enabled&&!form.proxy.area.trim())return ElMessage.warning('\u8bf7\u8f93\u5165\u4ee3\u7406\u76ee\u6807\u5730\u533a');if(form.ai_text.enabled&&userStore.role!=='admin')return ElMessage.warning('\u4ec5\u7ba1\u7406\u5458\u53ef\u4f7f\u7528 AI \u529f\u80fd');if(form.ai_text.enabled&&!ai.available)return ElMessage.warning('\u8bf7\u5148\u914d\u7f6e\u5e76\u542f\u7528 AI');loading.value=true;try{const task=await store.create({task_id:questionnaire.value.task_id,url:form.url,count:form.count,mode:form.mode,proxy:form.proxy,ai_text:form.ai_text,proportion_config:(form.mode==='proportional'||form.use_ratio)?form.proportion_config:undefined,config:{attitude:form.attitude,add_variation:form.mode==='high_reliability'?form.add_variation:false,variation_ratio:form.mode==='high_reliability'?form.variation_ratio/100:0.05,debug:form.debug,max_submit_attempts:form.max_submit_attempts}});dialog.value=false;step.value=0;await router.push('/tasks/'+task.task_id)}catch(error:any){ElMessage.error(error.response?.data?.detail||'\u521b\u5efa\u4efb\u52a1\u5931\u8d25')}finally{loading.value=false}}
</script>
<style scoped>.page{width:100%;max-width:none;margin:0;padding:20px 22px}.hero{display:flex;justify-content:space-between;align-items:center;padding:28px 30px;border-radius:16px;background:linear-gradient(110deg,#1d3263,#4263b8);color:#fff}.eyebrow{font-size:11px;letter-spacing:2px;opacity:.65}.hero h2{margin:7px 0}.hero p{margin:0}.create-btn{background:#fff;color:#3454bd}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}.stat{padding:18px 20px;border-radius:12px;background:#fff;border-left:4px solid #7c8ca8}.stat span{display:block;color:#8b98aa}.stat strong{display:block;font-size:25px;margin-top:8px}.blue{border-color:#5d7df2}.green{border-color:#35b98a}.orange{border-color:#f3a43b}.table-card{padding:10px 18px}.wizard-form{padding:28px 20px}.el-steps{margin:15px 0 25px}.field-hint{width:100%;margin-top:5px;color:#8792a6;font-size:12px;line-height:1.5}.inline-hint{margin-left:12px;color:#8792a6;font-size:12px}.ratio-count{margin-top:18px}.variation-option{margin-top:8px}.ratio-field{margin:14px 0 0 24px}.ratio-unit{margin-left:8px}.task-toolbar{display:grid;grid-template-columns:minmax(280px,1fr) 190px auto;gap:12px;margin-bottom:16px}.task-pagination{display:flex;justify-content:space-between;align-items:center;padding:16px 4px 4px;color:#8792a6;font-size:13px}@media(max-width:800px){.task-toolbar{grid-template-columns:1fr}}</style>




