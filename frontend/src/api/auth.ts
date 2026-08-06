import request from './request'; import type {ApiResponse} from './types'; import type {User} from '@/types';
export const loginApi=(data:{username:string;password:string})=>request.post<ApiResponse<{token:string;user:User}>>('/api/auth/login',data);
export const logoutApi=()=>request.post('/api/auth/logout'); export const userInfoApi=()=>request.get<ApiResponse<User>>('/api/auth/me');
