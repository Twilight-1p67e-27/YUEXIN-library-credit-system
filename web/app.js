const $=id=>document.getElementById(id);
let token='', me=null, offset=0, searchTerm='';
const native=!!window.Capacitor?.isNativePlatform();
let base=localStorage.getItem('library-server') || (native?'':location.origin);
$('server').value=base;
function notify(t){$('status').textContent=t;}
function clearSession(){pendingAdjustment=null;closeDeleteDialog();closeAdmin();searchTerm='';$('searchUsers').reset();document.querySelectorAll('.password-strength').forEach(el=>{el.className='password-strength';el.textContent='';});$('openAdmin').hidden=true;document.querySelectorAll('input[type=password]').forEach(el=>el.value='');token='';me=null;offset=0;$('roleManager').hidden=true;$('createdCredentials').textContent='';$('account').hidden=true;$('admin').hidden=true;$('logout').hidden=true;$('loginTab').hidden=false;$('registerTab').hidden=false;$('login').hidden=false;$('register').hidden=true;$('users').replaceChildren();}
async function api(path,method='GET',body){
 if(!base)throw Error('请先填写学校服务器地址');
 const headers={'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})};
 let status,data;
 if(native){
  const response=await window.Capacitor.nativePromise('CapacitorHttp','request',{url:base+path,method,headers,...(body?{data:body}:{}),responseType:'json',connectTimeout:15000,readTimeout:15000});
  status=response.status;data=typeof response.data==='string'?JSON.parse(response.data):response.data;
 }else{
  const response=await fetch(base+path,{method,headers,body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});
  status=response.status;data=await response.json();
 }
 if(status<200||status>=300){if(status===401)clearSession();throw Error(typeof data?.detail==='string'?data.detail:'输入格式有误，请检查学工号、UID 和密码');}return data;
}
function bind(id,fn){$(id).addEventListener('submit',async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;try{await fn(Object.fromEntries(new FormData(e.target)));updatePasswordHints(e.target);}catch(err){notify(err.message);}finally{btn.disabled=false;}});}
$('saveServer').onclick=async()=>{try{const u=new URL($('server').value.trim());if(!['https:','http:'].includes(u.protocol)||u.username||u.password||u.search||u.hash||u.pathname!=='/')throw Error('请输入域名或 IP 加端口，不带路径');base=u.origin;clearSession();localStorage.setItem('library-server',base);await api('/health');notify('服务器已连接');}catch(e){notify(e.message);}};
$('loginTab').onclick=()=>{$('register').hidden=true;$('login').hidden=false;};
$('registerTab').onclick=()=>{$('login').hidden=true;$('register').hidden=false;};
$('logout').onclick=async()=>{try{await api('/api/logout','POST');}catch{}clearSession();notify('已退出登录');};
async function refresh(){me=await api('/api/me');$('credit').textContent=me.credit;$('identity').textContent=`${me.student_id} · UID ${me.uid}`;$('profile').elements.nickname.value=me.nickname;$('profile').elements.email.value=me.email;$('openAdmin').hidden=!me.admin;$('roleFunction').hidden=!me.is_super_admin;if(!me.admin)closeAdmin();else if(document.body.classList.contains('admin-mode'))selectAdminPanel(activePanel);}
bind('login',async b=>{const r=await api('/api/login','POST',b);token=r.token;$('login').reset();await refresh();$('login').hidden=true;$('register').hidden=true;$('loginTab').hidden=true;$('registerTab').hidden=true;$('logout').hidden=false;$('account').hidden=false;$('openAdmin').hidden=!me.admin;notify('登录成功');});
bind('register',async b=>{const r=await api('/api/register','POST',b);$('register').reset();$('loginTab').click();notify(r.message);});
bind('profile',async b=>{const r=await api('/api/me','PATCH',b);await refresh();notify(r.message);});
bind('password',async b=>{const r=await api('/api/me/password','POST',b);$('password').reset();clearSession();notify(r.message);});
async function loadUsers(){
 let r=await api(`/api/admin/users?offset=${offset}&limit=50&q=${encodeURIComponent(searchTerm)}`);if(offset>0&&offset>=r.total){offset=Math.max(0,Math.floor((r.total-1)/50)*50);r=await api(`/api/admin/users?offset=${offset}&limit=50&q=${encodeURIComponent(searchTerm)}`);}$('users').replaceChildren();
 for(const u of r.items){const row=document.createElement('tr');for(const value of [u.student_id,u.nickname,u.uid,u.email||'—',u.credit,u.is_super_admin?'最高管理员':u.admin?'管理员':'普通用户']){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}$('users').append(row);}
 $('emptyUsers').hidden=r.total>0;$('emptyUsers').textContent=searchTerm?'没有匹配的账号':'暂无用户';$('page').textContent=r.total?`${offset+1}–${offset+r.items.length} / ${r.total}`:'0 / 0';$('prev').disabled=offset===0;$('next').disabled=offset+50>=r.total;
}
$('prev').onclick=async()=>{offset=Math.max(0,offset-50);try{await loadUsers();}catch(e){notify(e.message);}};
$('next').onclick=async()=>{offset+=50;try{await loadUsers();}catch(e){notify(e.message);}};
bind('reset',async b=>{if(!confirm(`确认重置 ${b.student_id} 的密码？`))return;const id=b.student_id;delete b.student_id;const r=await api(`/api/admin/users/${id}/password`,'POST',b);$('reset').reset();if(id===me.student_id)clearSession();notify(r.message);});
$('scan').onclick=async()=>{const btn=$('scan');btn.disabled=true;try{if(!native)throw Error('浏览器版请手输 UID；NFC 读卡请安装手机 App');notify('请将校园卡靠近手机 NFC 区域');const r=await window.Capacitor.nativePromise('CampusNfc','read',{});$('uid').value=r.uid;notify('已读取 UID：'+r.uid);}catch(e){notify(e.message||'读卡失败；该卡可能不受此手机支持，可使用终端读取 UID');}finally{btn.disabled=false;}};

bind('createUser',async b=>{const r=await api('/api/admin/users','POST',b);$('createUser').reset();$('createdCredentials').textContent=`已创建：${r.student_id}\n初始密码：${r.initial_password}\n请将初始密码告知用户，此处仅在本次操作后展示。`;offset=0;await loadUsers();notify(r.message);});
bind('setRole',async b=>{const r=await api(`/api/admin/users/${b.student_id}/admin`,'PATCH',{admin:b.admin==='true'});await loadUsers();notify(r.message);});
$('refreshUsers').onclick=async()=>{try{await refresh();if(me.admin)await loadUsers();notify('列表与权限已刷新');}catch(e){notify(e.message);}};

let activePanel='users';
function selectAdminPanel(panel){
 if(panel==='roles'&&!me?.is_super_admin)panel='users';activePanel=panel;
 document.querySelectorAll('[data-admin-panel]').forEach(el=>el.hidden=el.dataset.adminPanel!==panel);
 document.querySelectorAll('[data-panel]').forEach(el=>{const selected=el.dataset.panel===panel;el.classList.toggle('selected',selected);el.setAttribute('aria-pressed',String(selected));});
}
function closeAdmin(){document.body.classList.remove('admin-mode');$('admin').hidden=true;$('account').hidden=!me;$('createdCredentials').textContent='';$('admin').querySelectorAll('input[type=password]').forEach(el=>el.value='');updatePasswordHints($('admin'));closeDeleteDialog();}
$('openAdmin').onclick=async()=>{try{await refresh();if(!me.admin)return;await loadUsers();$('account').hidden=true;$('admin').hidden=false;document.body.classList.add('admin-mode');selectAdminPanel('users');$('adminTitle').focus();window.scrollTo(0,0);notify('');}catch(e){notify(e.message);}};
$('backAccount').onclick=()=>{closeAdmin();$('openAdmin').focus();notify('');window.scrollTo(0,0);};
document.querySelectorAll('[data-panel]').forEach(btn=>btn.onclick=()=>{selectAdminPanel(btn.dataset.panel);notify('');});

bind('searchUsers',async b=>{searchTerm=b.q.trim();offset=0;await loadUsers();notify(searchTerm?'搜索结果已更新':'已显示全部账号');});
$('clearSearch').onclick=async()=>{try{$('searchUsers').reset();searchTerm='';offset=0;await loadUsers();notify('已显示全部账号');}catch(e){notify(e.message);}};
let pendingAdjustment=null,deleteSnapshot=null;
function newRequestId(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');}
bind('adjustCredit',async b=>{const delta=Number(b.direction)*Number(b.points);const signature=JSON.stringify([b.student_id,delta,b.reason]);if(!pendingAdjustment||pendingAdjustment.signature!==signature)pendingAdjustment={signature,id:newRequestId()};const r=await api(`/api/admin/users/${b.student_id}/credit`,'POST',{request_id:pendingAdjustment.id,delta,reason:b.reason});pendingAdjustment=null;$('creditResult').textContent=`${b.student_id}：${r.before} → ${r.credit} 分`;$('adjustCredit').reset();await refresh();await loadUsers();notify(r.message);});
function closeDeleteDialog(){if($('deleteDialog').open)$('deleteDialog').close();deleteSnapshot=null;$('confirmDelete').reset();$('deleteError').textContent='';}
bind('deleteUser',async b=>{const r=await api(`/api/admin/users?q=${encodeURIComponent(b.student_id)}&limit=200`);const target=r.items.find(u=>u.student_id===b.student_id);if(!target)throw Error('账号不存在');if(target.is_super_admin)throw Error('最高管理员账号不可删除');if(target.student_id===me.student_id)throw Error('不可删除当前登录账号');if(target.admin&&!me.is_super_admin)throw Error('仅最高管理员可删除其他管理员账号');deleteSnapshot=target;$('deletePreview').textContent=`学工号：${target.student_id}\n昵称：${target.nickname}\nUID：${target.uid}\n信誉分：${target.credit}`;$('confirmDelete').reset();$('deleteError').textContent='';$('deleteDialog').showModal();});
bind('confirmDelete',async b=>{if(!deleteSnapshot)return;if(b.confirm_student_id!==deleteSnapshot.student_id){$('deleteError').textContent='学工号不一致，请核对后重新输入';return;}try{const r=await api(`/api/admin/users/${deleteSnapshot.student_id}/delete`,'POST',{confirm_student_id:b.confirm_student_id,uid:deleteSnapshot.uid});closeDeleteDialog();$('deleteUser').reset();await loadUsers();notify(r.message);}catch(e){$('deleteError').textContent=e.message;}});
$('cancelDelete').onclick=closeDeleteDialog;
$('deleteDialog').addEventListener('cancel',e=>{e.preventDefault();closeDeleteDialog();});

// Local heuristic for playful feedback only; it never imposes password requirements.
function passwordLevel(value){
 const chars=Array.from(value),n=chars.length;if(!n)return -1;
 const lower=value.toLowerCase();const common=['password','qwerty','123456','abcdef','letmein','admin','111111'];
 const repeated=new Set(chars).size<=2||/(.{1,4})\1{2,}/u.test(value);
 if(common.some(word=>lower.includes(word))||repeated||/^\d{10}$/.test(value))return n<8?0:1;
 const types=[/[a-z]/,/[A-Z]/,/[0-9]/,/[^a-zA-Z0-9]/].filter(re=>re.test(value)).length;
 if(n<5)return 0;if(n<8)return 1;if(n<10)return types>=2?2:1;
 if(n>=24&&new Set(chars).size>=10&&types>=2)return 5;
 if(n>=16||(n>=12&&types>=3))return 4;
 if(n>=12||types>=3)return 3;return 2;
}
const strengthLabels=['超级弱鸡','弱鸡','勉强','中等','安全','你真的记得下来？'];
function updatePasswordHints(scope=document){scope.querySelectorAll('[data-password-strength]').forEach(input=>{const hint=$(input.dataset.strengthId);if(!hint)return;const level=passwordLevel(input.value);hint.className='password-strength'+(level>=0?' strength-'+level:'');hint.textContent=level<0?'':strengthLabels[level];});}
document.querySelectorAll('[data-password-strength]').forEach((input,i)=>{const hint=document.createElement('span');hint.id='password-strength-'+i;hint.className='password-strength';hint.title='强度提示仅供参考，不限制密码设置';hint.setAttribute('aria-live','polite');input.dataset.strengthId=hint.id;input.setAttribute('aria-describedby',hint.id);input.after(hint);input.addEventListener('input',()=>updatePasswordHints(input.parentElement));input.form?.addEventListener('reset',()=>setTimeout(()=>updatePasswordHints(input.form),0));});
