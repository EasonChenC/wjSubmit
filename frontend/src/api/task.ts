import request from './request'
import type {ApiResponse} from './types'
import type {AITextAnswerConfig,ProportionConfig,ProxyConfig,SubmitConfig,SubmitMode,Task} from '@/types'
export interface TaskQuery {q?:string;owner_id?:string;offset?:number;limit?:number}
export interface TaskPage {items:Task[];total:number}
export const createTask=(data:{task_id:string;count:number;mode:SubmitMode;config?:SubmitConfig;proxy?:ProxyConfig;ai_text?:AITextAnswerConfig;proportion_config?:ProportionConfig})=>request.post<ApiResponse<{task_id:string;status:string;submitted:number;total:number;proxy?:ProxyConfig;ai_text?:AITextAnswerConfig;proportion_plan_status?:string}>>('/api/questionnaire/submit',data)
export const getTaskStatus=(id:string)=>request.get<ApiResponse<Task>>(`/api/questionnaire/submit/${id}`)
export const cancelTask=(id:string)=>request.post<ApiResponse<{task_id:string;status:string}>>(`/api/questionnaire/submit/${id}/cancel`)
export const getTaskList=(params:TaskQuery={})=>request.get<ApiResponse<TaskPage>>('/api/questionnaire/tasks',{params})
export const deleteTask=(id:string)=>request.delete(`/api/questionnaire/tasks/${id}`)
