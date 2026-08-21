<template>
  <div class="users-page">
    <section class="hero">
      <div><div class="eyebrow">SYSTEM ADMINISTRATION</div><h1>用户管理</h1><p>统一管理系统成员、访问角色与账户状态</p></div>
      <el-button type="primary" size="large" :icon="Plus" @click="openCreate">创建用户</el-button>
    </section>

    <section class="stats-grid">
      <div class="stat-card"><span class="stat-icon blue"><User /></span><div><small>用户总数</small><strong>{{ total }}</strong></div></div>
      <div class="stat-card"><span class="stat-icon green"><CircleCheck /></span><div><small>当前页已启用</small><strong>{{ activeCount }}</strong></div></div>
      <div class="stat-card"><span class="stat-icon violet"><Key /></span><div><small>当前页管理员</small><strong>{{ adminCount }}</strong></div></div>
    </section>

    <section class="content-card">
      <div class="toolbar">
        <el-input v-model="query.q" :prefix-icon="Search" clearable placeholder="搜索用户名或邮箱" @keyup.enter="search" @clear="search" />
        <el-select v-model="query.role" clearable placeholder="全部角色" @change="search"><el-option v-for="r in roles" :key="r.value" :label="r.label" :value="r.value" /></el-select>
        <el-select v-model="query.status" clearable placeholder="全部状态" @change="search"><el-option label="已启用" value="active"/><el-option label="已禁用" value="disabled"/></el-select>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading" row-key="id" class="user-table">
        <el-table-column label="用户" min-width="230">
          <template #default="{row}"><div class="identity"><el-avatar :style="avatarStyle(row.username)">{{ row.username.slice(0,1).toUpperCase() }}</el-avatar><div><b>{{ row.username }}</b><span>{{ row.email || '未设置邮箱' }}</span></div></div></template>
        </el-table-column>
        <el-table-column label="角色" width="130"><template #default="{row}"><el-tag :type="roleType(row.role)" effect="light" round>{{ roleLabel(row.role) }}</el-tag></template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="{row}"><span :class="['status',row.is_active?'on':'off']"><i></i>{{ row.is_active ? '正常' : '已禁用' }}</span></template></el-table-column>
        <el-table-column label="最后登录" min-width="170"><template #default="{row}">{{ formatDate(row.last_login_at) }}</template></el-table-column>
        <el-table-column label="创建时间" min-width="170"><template #default="{row}">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="255" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openPassword(row)">重置密码</el-button>
            <el-dropdown trigger="click" @command="(c:string)=>handleCommand(c,row)"><el-button link class="more">更多<el-icon><ArrowDown /></el-icon></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :command="row.is_active?'disable':'enable'">{{ row.is_active?'禁用账户':'启用账户' }}</el-dropdown-item><el-dropdown-item command="delete" divided class="danger-item">删除用户</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
          </template>
        </el-table-column>
        <template #empty><el-empty description="没有匹配的用户" /></template>
      </el-table>
      <div class="pagination"><span>共 {{ total }} 位用户</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev, pager, next" :total="total" @current-change="load" /></div>
    </section>

    <el-dialog v-model="userDialog" :title="editing?'编辑用户':'创建用户'" width="520px" destroy-on-close>
      <el-form ref="userFormRef" :model="form" :rules="userRules" label-position="top">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" :disabled="editing" placeholder="请输入用户名" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" placeholder="name@example.com" /></el-form-item>
        <el-form-item label="角色" prop="role"><el-select v-model="form.role" style="width:100%"><el-option v-for="r in roles" :key="r.value" :label="r.label" :value="r.value" /></el-select></el-form-item>
        <el-form-item v-if="!editing" label="初始密码" prop="password"><el-input v-model="form.password" type="password" show-password placeholder="至少12位，含大小写、数字和符号" /></el-form-item>
        <el-form-item v-if="editing" label="账户状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="userDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveUser">{{ editing?'保存修改':'创建用户' }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="passwordDialog" title="重置密码" width="460px" destroy-on-close>
      <p class="dialog-tip">正在为 <b>{{ selected?.username }}</b> 设置新密码。保存后该用户的现有会话将失效。</p>
      <el-input v-model="newPassword" type="password" show-password placeholder="至少12位，含大小写、数字和符号" />
      <template #footer><el-button @click="passwordDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePassword">确认重置</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { ArrowDown, CircleCheck, Key, Plus, Refresh, Search, User } from '@element-plus/icons-vue'
import { createUser, deleteUser, disableUser, enableUser, listUsers, resetPassword, updateUser } from '@/api/users'
interface UserRow {id:string;username:string;email?:string;role:string;is_active:boolean;created_at?:string;last_login_at?:string}
const roles=[{label:'管理员',value:'admin'},{label:'操作员',value:'operator'},{label:'查看者',value:'viewer'}]
const items=ref<UserRow[]>([]), loading=ref(false), saving=ref(false), total=ref(0), page=ref(1), pageSize=ref(20)
const query=reactive({q:'',role:'',status:''})
const activeCount=computed(()=>items.value.filter(x=>x.is_active).length), adminCount=computed(()=>items.value.filter(x=>x.role==='admin').length)
const userDialog=ref(false), passwordDialog=ref(false), editing=ref(false), selected=ref<UserRow|null>(null), newPassword=ref(''), userFormRef=ref<FormInstance>()
const form=reactive({username:'',email:'',role:'viewer',password:'',is_active:true})
const userRules:FormRules={username:[{required:true,message:'请输入用户名',trigger:'blur'}],role:[{required:true,message:'请选择角色',trigger:'change'}],password:[{required:true,message:'请输入初始密码',trigger:'blur'},{min:12,message:'密码至少12位',trigger:'blur'}]}
async function load(){loading.value=true;try{const r=await listUsers({q:query.q||undefined,role:query.role||undefined,status:query.status||undefined,offset:(page.value-1)*pageSize.value,limit:pageSize.value});items.value=r.data.data.items;total.value=r.data.data.total}catch(e:any){ElMessage.error(e?.response?.data?.detail||'加载用户失败')}finally{loading.value=false}}
function search(){page.value=1;load()}
function resetForm(){Object.assign(form,{username:'',email:'',role:'viewer',password:'',is_active:true})}
function openCreate(){editing.value=false;selected.value=null;resetForm();userDialog.value=true}
function openEdit(row:UserRow){editing.value=true;selected.value=row;Object.assign(form,{username:row.username,email:row.email||'',role:row.role,is_active:row.is_active,password:''});userDialog.value=true}
async function saveUser(){if(!await userFormRef.value?.validate())return;saving.value=true;try{if(editing.value&&selected.value)await updateUser(selected.value.id,{email:form.email||null,role:form.role,is_active:form.is_active});else await createUser({username:form.username,email:form.email||null,role:form.role,password:form.password});ElMessage.success(editing.value?'用户已更新':'用户已创建');userDialog.value=false;await load()}catch(e:any){ElMessage.error(e?.response?.data?.detail||'保存失败')}finally{saving.value=false}}
function openPassword(row:UserRow){selected.value=row;newPassword.value='';passwordDialog.value=true}
async function savePassword(){if(newPassword.value.length<12){ElMessage.warning('密码至少12位');return}saving.value=true;try{await resetPassword(selected.value!.id,newPassword.value);ElMessage.success('密码已重置');passwordDialog.value=false}catch(e:any){ElMessage.error(e?.response?.data?.detail||'重置失败')}finally{saving.value=false}}
async function handleCommand(command:string,row:UserRow){try{if(command==='delete'){await ElMessageBox.confirm(`删除用户“${row.username}”？该操作将软删除账户并撤销会话。`,'删除确认',{type:'warning',confirmButtonText:'删除',cancelButtonText:'取消'});await deleteUser(row.id);ElMessage.success('用户已删除')}else if(command==='disable'){await ElMessageBox.confirm(`禁用“${row.username}”？该用户会被立即退出。`,'禁用确认',{type:'warning'});await disableUser(row.id);ElMessage.success('账户已禁用')}else{await enableUser(row.id);ElMessage.success('账户已启用')}await load()}catch(e:any){if(e!=='cancel'&&e!=='close')ElMessage.error(e?.response?.data?.detail||'操作失败')}}
function roleLabel(v:string){return roles.find(x=>x.value===v)?.label||v}
function roleType(v:string):''|'success'|'warning'|'info'|'primary'|'danger'{return v==='admin'?'danger':v==='operator'?'primary':'info'}
function formatDate(v?:string){return v?new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(v)):'从未登录'}
function avatarStyle(name:string){const colors=['#536dfe','#7c4dff','#00a884','#e87933','#d84f70'];return {background:colors[name.charCodeAt(0)%colors.length],color:'#fff'}}
onMounted(load)
</script>
<style scoped>
.users-page{max-width:1480px;margin:auto;color:#172033}.hero{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:22px}.hero h1{font-size:28px;margin:4px 0 6px;letter-spacing:-.5px}.hero p{margin:0;color:#778197}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.5px;color:#6574d9}.stats-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:18px}.stat-card{background:#fff;border:1px solid #e9edf5;border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 6px 20px #26375d0a}.stat-card small{display:block;color:#8490a5;margin-bottom:4px}.stat-card strong{font-size:25px}.stat-icon{width:42px;height:42px;border-radius:12px;display:grid;place-items:center}.stat-icon :deep(svg){width:21px}.blue{background:#edf2ff;color:#5069e8}.green{background:#e9f9f2;color:#16a36a}.violet{background:#f3edff;color:#7b50d8}.content-card{background:#fff;border:1px solid #e7ebf2;border-radius:16px;box-shadow:0 8px 28px #26375d0b;overflow:hidden}.toolbar{padding:18px 20px;border-bottom:1px solid #edf0f5;display:grid;grid-template-columns:minmax(240px,1fr) 150px 150px auto;gap:12px}.user-table{width:100%}.user-table :deep(th.el-table__cell){background:#f8f9fc;color:#69758b;font-size:12px;font-weight:600;height:48px}.user-table :deep(td.el-table__cell){padding:14px 0}.identity{display:flex;align-items:center;gap:12px}.identity b,.identity span{display:block}.identity b{font-size:14px;margin-bottom:4px}.identity span{font-size:12px;color:#8a94a7}.status{display:inline-flex;align-items:center;gap:7px;font-size:13px}.status i{width:7px;height:7px;border-radius:50%}.status.on{color:#16865c}.status.on i{background:#23b77d;box-shadow:0 0 0 4px #23b77d18}.status.off{color:#9a6470}.status.off i{background:#d3687c;box-shadow:0 0 0 4px #d3687c18}.more{margin-left:12px;color:#667085}.danger-item{color:#d84d63}.pagination{padding:16px 20px;display:flex;justify-content:space-between;align-items:center;color:#8490a5;font-size:13px;border-top:1px solid #edf0f5}.dialog-tip{padding:12px 14px;background:#f6f8fc;border-radius:8px;color:#657086;font-size:13px;line-height:1.6;margin-top:0}@media(max-width:900px){.stats-grid{grid-template-columns:1fr}.toolbar{grid-template-columns:1fr}.hero{align-items:flex-start}.hero .el-button{margin-top:10px}}
</style>
