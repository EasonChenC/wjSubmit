import { defineStore } from 'pinia'
import { getAiConfig, updateAiConfig, testAiConnection } from '@/api/ai'
import type { AiConfig } from '@/api/ai'

export const useAiStore = defineStore('ai', {
  state: () => ({ config: null as AiConfig | null, loading: false }),
  getters: { available: (s) => !!s.config?.enabled && !!s.config?.has_api_key },
  actions: {
    async fetchConfig() { this.config = (await getAiConfig()).data.data; return this.config },
    async save(data: { api_key?: string; model: string; base_url: string; enabled: boolean }) { this.config = (await updateAiConfig(data)).data.data; return this.config },
    async test() { return (await testAiConnection()).data.data },
  },
})
