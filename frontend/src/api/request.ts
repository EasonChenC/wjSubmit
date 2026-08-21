import axios from 'axios'; import { getToken, removeToken } from '@/utils/storage';
const request=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL||'http://localhost:8000',timeout:60000,withCredentials:true});
request.interceptors.request.use(c=>{const t=getToken(); if(t)c.headers.Authorization=`Bearer ${t}`; return c});
request.interceptors.response.use(r=>r, e=>{const url=e.config?.url||''; if(e.response?.status===401&&!url.includes('/api/auth/login')){removeToken();window.location.href='/login'} if(e.response?.status===403&&!url.includes('/api/auth/login'))window.location.href='/403'; return Promise.reject(e)}); export default request;
