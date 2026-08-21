import request from './request'
export interface UserQuery { q?:string; role?:string; status?:string; offset?:number; limit?:number }
export const listUsers=(params:UserQuery={})=>request.get('/api/users',{params})
export const createUser=(data:any)=>request.post('/api/users',data)
export const updateUser=(id:string,data:any)=>request.patch(`/api/users/${id}`,data)
export const disableUser=(id:string)=>request.post(`/api/users/${id}/disable`)
export const enableUser=(id:string)=>request.post(`/api/users/${id}/enable`)
export const resetPassword=(id:string,password:string)=>request.post(`/api/users/${id}/reset-password`,{password})
export const deleteUser=(id:string)=>request.delete(`/api/users/${id}`)
