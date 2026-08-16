import request from './request'; import type {ApiResponse} from './types'; import type {ProxyConfig,SubmitConfig,Task} from '@/types';
export const createTask=(data:{task_id:string;count:number;mode:'random'|'high_reliability';config?:SubmitConfig;proxy?:ProxyConfig})=>request.post<ApiResponse<{task_id:string;status:string;submitted:number;total:number;proxy?:ProxyConfig}>>('/api/questionnaire/submit',data);
export const getTaskStatus=(id:string)=>request.get<ApiResponse<Task>>(`/api/questionnaire/submit/${id}`);
export const cancelTask=(id:string)=>request.post<ApiResponse<{task_id:string;status:string}>>(`/api/questionnaire/submit/${id}/cancel`);
// List/delete are optional backend extensions; keeping them isolated allows the UI to work with the current API.
export const getTaskList=()=>request.get<ApiResponse<Task[]>>('/api/questionnaire/tasks'); export const deleteTask=(id:string)=>request.delete(`/api/questionnaire/tasks/${id}`);
