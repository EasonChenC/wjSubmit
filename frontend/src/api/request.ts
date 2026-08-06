import axios from 'axios'; import { getToken, removeToken } from '@/utils/storage';
const request=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL||'http://localhost:8000',timeout:60000});
request.interceptors.request.use(c=>{const t=getToken(); if(t)c.headers.Authorization=`Bearer ${t}`; return c});
request.interceptors.response.use(r=>r, e=>{if(e.response?.status===401)removeToken(); return Promise.reject(e)}); export default request;
