import request from './request'
import type { ApiResponse } from './types'

export interface AiConfig { model: string; base_url: string; enabled: boolean; has_api_key: boolean }
export interface AiTestResult { success: boolean; message: string }
export const getAiConfig = () => request.get<ApiResponse<AiConfig>>('/api/ai/config')
export const updateAiConfig = (data: { api_key?: string; model: string; base_url: string; enabled: boolean }) => request.post<ApiResponse<AiConfig>>('/api/ai/config', data)
export const testAiConnection = () => request.post<ApiResponse<AiTestResult>>('/api/ai/test')
