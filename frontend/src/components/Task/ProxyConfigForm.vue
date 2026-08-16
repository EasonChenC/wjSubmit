<template>
  <section class="proxy-config">
    <el-divider content-position="left">代理配置</el-divider>
    <el-form-item label="启用动态代理">
      <el-switch v-model="model.enabled" />
      <p class="hint">每份问卷可使用独立代理出口；代理凭据由服务端配置。</p>
    </el-form-item>
    <template v-if="model.enabled">
      <el-form-item label="目标地区"><el-input v-model="model.area" maxlength="64" show-word-limit placeholder="例如：南京" /></el-form-item>
      <el-form-item label="运营商"><el-select v-model="model.carrier" style="width:180px"><el-option :value="0" label="不限"/><el-option :value="1" label="联通"/><el-option :value="2" label="电信"/><el-option :value="3" label="移动"/></el-select></el-form-item>
      <el-form-item label="每份更换 IP"><el-switch v-model="model.rotate_per_submission" /></el-form-item>
      <el-form-item label="验证出口地区"><el-switch v-model="model.verify_exit" /></el-form-item>
      <el-form-item label="地区匹配"><el-radio-group v-model="model.location_match"><el-radio value="relaxed">宽松匹配</el-radio><el-radio value="strict">严格匹配</el-radio></el-radio-group></el-form-item>
      <el-form-item label="代理失败处理"><el-checkbox v-model="model.required">禁止回退到本机直连</el-checkbox></el-form-item>
      <el-form-item label="最大获取次数"><el-input-number v-model="model.max_acquire_attempts" :min="1" :max="5" /></el-form-item>
    </template>
  </section>
</template>
<script setup lang="ts">
import type { ProxyConfig } from '@/types'
const model = defineModel<ProxyConfig>({ required: true })
</script>
<style scoped>.proxy-config{margin-top:12px}.hint{margin:6px 0 0;color:#8792a6;font-size:12px;line-height:1.5}</style>
