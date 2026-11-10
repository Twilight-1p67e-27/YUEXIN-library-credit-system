import os, re, sqlite3, secrets, hashlib, time
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

DB = os.getenv('DB_PATH', 'data/library.db')
ADMINS = {'2026211348','2026210633','2026210635','2026210668','2026210666'}
SUPER_ADMIN = '2026211348'
THRESHOLD = int(os.getenv('CREDIT_THRESHOLD', '60'))
if not 0 <= THRESHOLD <= 100:
    raise ValueError('CREDIT_THRESHOLD must be between 0 and 100')
ph = PasswordHasher()
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()
def init():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(student_id TEXT PRIMARY KEY, uid TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, nickname TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
          credit INTEGER NOT NULL DEFAULT 100 CHECK(credit BETWEEN 0 AND 100), admin INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, student_id TEXT REFERENCES users(student_id), expires INTEGER);
        CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, token TEXT UNIQUE, enrollment INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, device TEXT, uid TEXT, points INTEGER, reason TEXT,
          student_id TEXT, before_score INTEGER, after_score INTEGER, created INTEGER);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor TEXT, action TEXT, target TEXT, created INTEGER);
        CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, window INTEGER, count INTEGER);
        CREATE TABLE IF NOT EXISTS credit_adjustments(id TEXT PRIMARY KEY, actor TEXT, student_id TEXT,
          delta INTEGER, reason TEXT, before_score INTEGER, after_score INTEGER, created INTEGER);
        ''')
        # Remove the retired registration mechanism on existing installations.
        c.execute('DROP TABLE IF EXISTS invites')
        c.execute('UPDATE users SET admin=1 WHERE student_id=?', (SUPER_ADMIN,))
@asynccontextmanager
async def lifespan(app):
    init(); yield
app = FastAPI(title='Library Credit API', version='1.4.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x for x in os.getenv('CORS_ORIGINS','http://localhost,https://localhost,capacitor://localhost').split(',') if x], allow_methods=['GET','POST','PATCH'], allow_headers=['Authorization','Content-Type','X-Device-Key'])
@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; connect-src 'self' https: http:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
    return response
def audit(c, actor, action, target):
    c.execute('INSERT INTO audit(actor,action,target,created) VALUES(?,?,?,?)',(actor,action,target,int(time.time())))
def rate(request, category, maximum):
    key = category + ':' + (request.client.host if request.client else 'unknown')
    window = int(time.time()) // 60
    with db() as c:
        c.execute('INSERT INTO limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN window=excluded.window THEN count+1 ELSE 1 END,window=excluded.window',(key,window))
        n = c.execute('SELECT count FROM limits WHERE key=?',(key,)).fetchone()[0]
        c.execute('DELETE FROM limits WHERE window < ?', (window-2,))
    if n > maximum: raise HTTPException(429,'请求过于频繁，请稍后再试')
def public(row):
    return {**{k: row[k] for k in ('student_id','uid','nickname','email','credit','admin')},
            'is_super_admin': row['student_id'] == SUPER_ADMIN}
def user(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '): raise HTTPException(401,'请登录')
    with db() as c:
        r = c.execute('SELECT u.* FROM sessions s JOIN users u USING(student_id) WHERE s.token=? AND expires>?',(digest(authorization[7:]),int(time.time()))).fetchone()
    if r is None: raise HTTPException(401,'登录已失效')
    return r
def admin(u=Depends(user)):
    if not u['admin']: raise HTTPException(403,'需要管理员权限')
    return u
def super_admin(u=Depends(admin)):
    if u['student_id'] != SUPER_ADMIN: raise HTTPException(403,'仅最高管理员可管理管理员权限')
    return u
def device(x_device_key: str = Header(default='')):
    with db() as c: r = c.execute('SELECT * FROM devices WHERE token=?',(digest(x_device_key),)).fetchone()
    if not r: raise HTTPException(401,'设备密钥无效')
    return r
def uid_normalize(v):
    v = re.sub(r'[:\s-]', '', v).upper()
    if not re.fullmatch(r'(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})',v):
        raise ValueError('UID 必须为 4/7/10 字节十六进制，保持读卡字节顺序')
    return v
class Login(BaseModel):
    student_id: str = Field(pattern=r'^[0-9]{10}$')
    password: str = Field(min_length=1, max_length=1024)
class Register(Login):
    uid: str
    nickname: str = Field(default='',max_length=64)
    email: str = Field(default='',max_length=254)
    _uid = field_validator('uid')(uid_normalize)
def register_account(b, actor=None):
    password_hash = ph.hash(b.password)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('INSERT INTO users(student_id,uid,password_hash,nickname,email,admin) VALUES(?,?,?,?,?,?)',(b.student_id,b.uid,password_hash,b.nickname or b.student_id,b.email,int(b.student_id in ADMINS)))
        except sqlite3.IntegrityError: raise HTTPException(409,'学工号或校园卡已绑定')
        audit(c,actor or b.student_id,'admin_create_user' if actor else 'register',b.student_id)
    return {'message':'账号创建成功，初始信誉分 100'}
@app.post('/api/register',status_code=201)
def register(b:Register, request:Request):
    rate(request,'register',10); return register_account(b)
@app.post('/api/login')
def login(b:Login, request:Request):
    rate(request,'login',20)
    with db() as c:
        r = c.execute('SELECT * FROM users WHERE student_id=?',(b.student_id,)).fetchone()
        try: ph.verify(r['password_hash'] if r else DUMMY_HASH,b.password)
        except (VerificationError,InvalidHashError): raise HTTPException(401,'学工号或密码错误')
        if not r: raise HTTPException(401,'学工号或密码错误')
        token = secrets.token_urlsafe(32)
        c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),))
        c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),b.student_id,int(time.time())+86400))
    return {'token':token,'user':public(r)}
DUMMY_HASH = ph.hash(secrets.token_urlsafe(32))
@app.get('/api/me')
def me(u=Depends(user)): return public(u)
@app.post('/api/logout')
def logout(u=Depends(user),authorization:str=Header()):
    with db() as c: c.execute('DELETE FROM sessions WHERE token=?',(digest(authorization[7:]),))
    return {'message':'已退出'}
class Profile(BaseModel):
    nickname:str=Field(max_length=64)
    email:str=Field(default='',max_length=254)
@app.patch('/api/me')
def profile(b:Profile,u=Depends(user)):
    with db() as c: c.execute('UPDATE users SET nickname=?,email=? WHERE student_id=?',(b.nickname or u['student_id'],b.email,u['student_id']))
    return {'message':'资料已更新'}
class Password(BaseModel):
    current_password:str=Field(min_length=1,max_length=1024)
    new_password:str=Field(min_length=1,max_length=1024)
@app.post('/api/me/password')
def password(b:Password,u=Depends(user)):
    try: ph.verify(u['password_hash'],b.current_password)
    except VerificationError: raise HTTPException(403,'原密码错误')
    with db() as c:
        c.execute('UPDATE users SET password_hash=? WHERE student_id=?',(ph.hash(b.new_password),u['student_id']))
        c.execute('DELETE FROM sessions WHERE student_id=?',(u['student_id'],))
        audit(c,u['student_id'],'password_change',u['student_id'])
    return {'message':'密码已修改，请重新登录'}
@app.get('/api/admin/users')
def users(offset:int=0,limit:int=100,q:str=Query(default='',max_length=100),u=Depends(admin)):
    if offset<0 or not 1<=limit<=200: raise HTTPException(422,'分页参数无效')
    with db() as c:
        term=q.strip()
        uid_term=re.sub(r'[:\s-]', '', term).upper()
        where=' WHERE instr(student_id,?)>0 OR instr(uid,?)>0' if term else ''
        args=(term,uid_term or term) if term else ()
        rows=c.execute('SELECT * FROM users'+where+' ORDER BY student_id LIMIT ? OFFSET ?',(*args,limit,offset)).fetchall()
        count=c.execute('SELECT count(*) FROM users'+where,args).fetchone()[0]
    return {'total':count,'items':[public(r) for r in rows]}
class AdminCreate(BaseModel):
    student_id: str = Field(pattern=r'^[0-9]{10}$')
    uid: str
    password: str = Field(default='',max_length=1024)
    nickname: str = Field(default='',max_length=64)
    email: str = Field(default='',max_length=254)
    _uid = field_validator('uid')(uid_normalize)
@app.post('/api/admin/users',status_code=201)
def create_user(b:AdminCreate,u=Depends(admin)):
    initial_password = b.password or secrets.token_urlsafe(12)
    result = register_account(Register(**{**b.model_dump(), 'password': initial_password}),actor=u['student_id'])
    return {**result, 'student_id':b.student_id, 'initial_password':initial_password}
class AdminRole(BaseModel):
    admin: bool = Field(strict=True)
@app.patch('/api/admin/users/{student_id}/admin')
def set_admin(student_id:str,b:AdminRole,u=Depends(super_admin)):
    if student_id == SUPER_ADMIN: raise HTTPException(403,'最高管理员的权限不可修改')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE student_id=?',(student_id,)).fetchone(): raise HTTPException(404,'账号不存在')
        c.execute('UPDATE users SET admin=? WHERE student_id=?',(int(b.admin),student_id))
        audit(c,u['student_id'],'grant_admin' if b.admin else 'revoke_admin',student_id)
    return {'message':'已授予管理员权限' if b.admin else '已移除管理员权限'}
class CreditAdjustment(BaseModel):
    request_id:str=Field(min_length=1,max_length=100)
    delta:int=Field(strict=True,ge=-100,le=100)
    reason:str=Field(min_length=1,max_length=500)
    @field_validator('delta')
    @classmethod
    def nonzero(cls,v):
        if v==0: raise ValueError('调整分数不能为 0')
        return v
    @field_validator('reason')
    @classmethod
    def not_blank(cls,v):
        if not v.strip(): raise ValueError('请填写调整原因')
        return v.strip()
@app.post('/api/admin/users/{student_id}/credit')
def adjust_credit(student_id:str,b:CreditAdjustment,u=Depends(admin)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM credit_adjustments WHERE id=?',(b.request_id,)).fetchone()
        if old:
            if (old['actor'],old['student_id'],old['delta'],old['reason'])!=(u['student_id'],student_id,b.delta,b.reason):
                raise HTTPException(409,'请求编号已用于其他调整')
            return {'message':'该调整已处理','before':old['before_score'],'credit':old['after_score'],'duplicate':True}
        target=c.execute('SELECT credit FROM users WHERE student_id=?',(student_id,)).fetchone()
        if not target: raise HTTPException(404,'账号不存在')
        before=target['credit'];score=max(0,min(100,before+b.delta))
        c.execute('UPDATE users SET credit=? WHERE student_id=?',(score,student_id))
        c.execute('INSERT INTO credit_adjustments VALUES(?,?,?,?,?,?,?,?)',(b.request_id,u['student_id'],student_id,b.delta,b.reason,before,score,int(time.time())))
        audit(c,u['student_id'],'admin_credit_adjustment',b.request_id)
    return {'message':'信誉分已调整','before':before,'credit':score,'duplicate':False}
class DeleteAccount(BaseModel):
    confirm_student_id:str=Field(pattern=r'^[0-9]{10}$')
    uid:str
    _uid=field_validator('uid')(uid_normalize)
@app.post('/api/admin/users/{student_id}/delete')
def delete_account(student_id:str,b:DeleteAccount,u=Depends(admin)):
    if b.confirm_student_id!=student_id: raise HTTPException(422,'二次确认的学工号不一致')
    if student_id==SUPER_ADMIN: raise HTTPException(403,'最高管理员账号不可删除')
    if student_id==u['student_id']: raise HTTPException(403,'不可删除当前登录账号')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        target=c.execute('SELECT * FROM users WHERE student_id=?',(student_id,)).fetchone()
        if not target: raise HTTPException(404,'账号不存在')
        if target['uid']!=b.uid: raise HTTPException(409,'账号绑定信息已变化，请重新查询确认')
        if target['admin'] and u['student_id']!=SUPER_ADMIN: raise HTTPException(403,'仅最高管理员可删除其他管理员账号')
        c.execute('DELETE FROM sessions WHERE student_id=?',(student_id,))
        c.execute('DELETE FROM users WHERE student_id=?',(student_id,))
        audit(c,u['student_id'],'admin_delete_user',student_id)
    return {'message':'账号已删除，校园卡已解绑，登录状态已撤销'}
class Reset(BaseModel):
    new_password:str=Field(min_length=1,max_length=1024)
    admin_password:str=Field(min_length=1,max_length=1024)
@app.post('/api/admin/users/{student_id}/password')
def reset(student_id:str,b:Reset,u=Depends(admin)):
    try: ph.verify(u['password_hash'],b.admin_password)
    except VerificationError: raise HTTPException(403,'管理员密码错误')
    with db() as c:
        if not c.execute('SELECT 1 FROM users WHERE student_id=?',(student_id,)).fetchone(): raise HTTPException(404,'账号不存在')
        c.execute('UPDATE users SET password_hash=? WHERE student_id=?',(ph.hash(b.new_password),student_id))
        c.execute('DELETE FROM sessions WHERE student_id=?',(student_id,))
        audit(c,u['student_id'],'admin_password_reset',student_id)
    return {'message':'已重置该用户密码，并撤销其登录状态'}
class Card(BaseModel):
    uid:str
    _uid=field_validator('uid')(uid_normalize)
@app.post('/api/device/lookup')
def lookup(b:Card,d=Depends(device)):
    with db() as c: r=c.execute('SELECT credit FROM users WHERE uid=?',(b.uid,)).fetchone()
    return {'registered':r is not None,'credit':r['credit'] if r else None,'allowed':bool(r and r['credit']>=THRESHOLD),'threshold':THRESHOLD,'valid_for_seconds':15}
@app.post('/api/device/register',status_code=201)
def device_register(b:Register,d=Depends(device)):
    if not d['enrollment']: raise HTTPException(403,'此设备未授权线下注册')
    return register_account(b)
class Event(Card):
    event_id:str=Field(min_length=1,max_length=100)
    points:int=Field(ge=1,le=100)
    reason:str=Field(min_length=1,max_length=500)
@app.post('/api/device/violations')
def violation(b:Event,d=Depends(device)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM events WHERE id=?',(b.event_id,)).fetchone()
        if old:
            if (old['device'],old['uid'],old['points'],old['reason']) != (d['id'],b.uid,b.points,b.reason): raise HTTPException(409,'事件 ID 已用于其他请求')
            return {'credit':old['after_score'],'duplicate':True}
        r=c.execute('SELECT * FROM users WHERE uid=?',(b.uid,)).fetchone()
        if not r: raise HTTPException(404,'校园卡未绑定')
        score=max(0,r['credit']-b.points)
        c.execute('UPDATE users SET credit=? WHERE uid=?',(score,b.uid))
        c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)',(b.event_id,d['id'],b.uid,b.points,b.reason,r['student_id'],r['credit'],score,int(time.time())))
        audit(c,d['id'],'credit_deduction',b.event_id)
    return {'credit':score,'duplicate':False}
@app.get('/health')
def health():
    with db() as c: c.execute('SELECT 1')
    return {'status':'ok'}
app.mount('/',StaticFiles(directory=Path(__file__).resolve().parent.parent/'web',html=True),name='web')
