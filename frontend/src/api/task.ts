import request from './request'; import type {ApiResponse} from './types'; import type {SubmitConfig,Task} from '@/types';
export const createTask=(data:{task_id:string;count:number;mode:'random'|'high_reliability';config?:SubmitConfig})=>request.post<ApiResponse<{task_id:string;status:string;submitted:number;total:number}>>('/api/questionnaire/submit',data);
export const getTaskStatus=(id:string)=>request.get<ApiResponse<Task>>(`/api/questionnaire/submit/${id}`);
// List/delete are optional backend extensions; keeping them isolated allows the UI to work with the current API.
export const getTaskList=()=>request.get<ApiResponse<Task[]>>('/api/questionnaire/tasks'); export const deleteTask=(id:string)=>request.delete(`/api/questionnaire/tasks/${id}`);
