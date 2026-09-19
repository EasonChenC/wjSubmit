import request from './request'
import type {ApiResponse} from './types'
import type {AITextAnswerConfig,ProportionConfig,ProxyConfig,Questionnaire,SubmitConfig,SubmitMode,Task} from '@/types'
export interface TaskQuery {q?:string;owner_id?:string;offset?:number;limit?:number}
export interface TaskPage {items:Task[];total:number}
export const createTask=(data:{task_id:string;count:number;mode:SubmitMode;config?:SubmitConfig;proxy?:ProxyConfig;ai_text?:AITextAnswerConfig;proportion_config?:ProportionConfig})=>request.post<ApiResponse<{task_id:string;status:string;submitted:number;total:number;proxy?:ProxyConfig;ai_text?:AITextAnswerConfig;proportion_plan_status?:string}>>('/api/questionnaire/submit',data)
export const getTaskStatus=(id:string)=>request.get<ApiResponse<Task>>(`/api/questionnaire/submit/${id}`)
export const cancelTask=(id:string)=>request.post<ApiResponse<{task_id:string;status:string}>>(`/api/questionnaire/submit/${id}/cancel`)
export const resumeTask=(id:string)=>request.post<ApiResponse<{task_id:string;status:string;submitted:number;total:number;remaining:number}>>(`/api/questionnaire/submit/${id}/resume`)
export const getTaskList=(params:TaskQuery={})=>request.get<ApiResponse<TaskPage>>('/api/questionnaire/tasks',{params})
export const getTaskAnalysis=(id:string)=>request.get<ApiResponse<Questionnaire>>(`/api/questionnaire/tasks/${id}/analysis`)
export const getTaskConfig=(id:string)=>request.get<ApiResponse<any>>(`/api/questionnaire/tasks/${id}/config`)
export const updateTaskConfig=(id:string,data:any)=>request.patch<ApiResponse<any>>(`/api/questionnaire/tasks/${id}/config`,data)
export const deleteTask=(id:string)=>request.delete(`/api/questionnaire/tasks/${id}`)
