import request from './request'; import type {ApiResponse} from './types'; import type {Questionnaire} from '@/types';
export const analyzeQuestionnaire=(url:string, use_ai = false)=>request.post<ApiResponse<Questionnaire & { detection_method?: 'ai'|'keyword' }>>('/api/questionnaire/analyze',{url, use_ai});
