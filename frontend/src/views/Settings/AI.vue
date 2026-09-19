<template>
  <div class="page ai-page">
    <div class="hero"><div><div class="eyebrow">SETTINGS / AI</div><h2>AI 配置管理</h2><p>配置问卷智能分析与文本生成服务</p></div></div>
    <div class="card panel">
      <el-form label-position="top">
        <el-form-item label="启用 AI 识别"><el-switch v-model="form.enabled" :disabled="!form.api_key && !ai.config?.has_api_key"/><span class="hint">启用后可在问卷分析时使用 AI 识别量表题和反向题</span></el-form-item>
        <el-form-item label="API Key"><el-input v-model="form.api_key" type="password" show-password :placeholder="ai.config?.has_api_key ? '已配置，留空表示保持原密钥' : '请输入 API Key'"/></el-form-item>
        <div class="form-grid"><el-form-item label="模型名称"><el-input v-model="form.model" placeholder="gpt-4o-mini" :disabled="!form.enabled"/></el-form-item><el-form-item label="API 基础 URL"><el-input v-model="form.base_url" placeholder="https://api.openai.com/v1" :disabled="!form.enabled"/></el-form-item></div>
        <div class="hint block-hint">支持自定义兼容接口 URL，例如内部网关或代理服务地址。</div>
        <div class="actions"><el-button :loading="testing" :disabled="!form.enabled || (!form.api_key && !ai.config?.has_api_key)" @click="test">测试连接</el-button><el-button type="primary" :loading="saving" @click="save">保存配置</el-button><el-button @click="$router.push('/tasks')">取消</el-button></div>
        <el-alert v-if="testMessage" :title="testMessage" :type="testSuccess ? 'success' : 'error'" show-icon/>
      </el-form>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAiStore } from '@/stores/ai'
const ai=useAiStore(); const saving=ref(false); const testing=ref(false); const testMessage=ref(''); const testSuccess=ref(false)
const form=reactive({enabled:false,api_key:'',model:'gpt-4o-mini',base_url:'https://api.openai.com/v1'})
onMounted(async()=>{try{const c=await ai.fetchConfig();Object.assign(form,{enabled:c.enabled,model:c.model,base_url:c.base_url})}catch{ElMessage.error('加载 AI 配置失败')}})
const save=async()=>{if(form.enabled&&!form.api_key&&!ai.config?.has_api_key){ElMessage.warning('启用 AI 前请输入 API Key');return}saving.value=true;try{await ai.save({...form,api_key:form.api_key||undefined});ElMessage.success('AI 配置已保存')}catch{ElMessage.error('保存失败')}finally{saving.value=false}}
const test=async()=>{testing.value=true;testMessage.value='';try{const r=await ai.test();testSuccess.value=r.success;testMessage.value=r.message}catch{testSuccess.value=false;testMessage.value='连接失败'}finally{testing.value=false}}
</script>
<style scoped>.ai-page{width:100%;max-width:none;margin:0;padding:20px 22px}.hero{padding:28px 30px;border-radius:16px;background:linear-gradient(110deg,#1d3263,#4263b8);color:#fff}.eyebrow{font-size:11px;letter-spacing:2px;opacity:.65}.hero h2{margin:7px 0}.hero p{margin:0;color:#d6e2ff}.panel{width:100%;max-width:none;margin:22px 0;padding:28px 32px}.form-grid{display:grid;grid-template-columns:minmax(260px,1fr) minmax(340px,1.4fr);gap:22px}.hint{margin-left:12px;color:#8995a8;font-size:12px}.block-hint{margin:-8px 0 10px}.actions{display:flex;gap:10px;margin:24px 0}@media(max-width:850px){.form-grid{grid-template-columns:1fr}.panel{padding:22px}}</style>
