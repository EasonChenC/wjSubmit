import request from './request'; import type {ApiResponse} from './types'; import type {Questionnaire} from '@/types';
export const analyzeQuestionnaire=(url:string, use_ai = false, analysis_mode:'standard'|'proportional'='standard')=>request.post<ApiResponse<Questionnaire>>('/api/questionnaire/analyze',{url,use_ai:analysis_mode==='proportional'?false:use_ai,analysis_mode});
