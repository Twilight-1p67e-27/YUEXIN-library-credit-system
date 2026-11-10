import sys, importlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'test.db'))
    import app
    importlib.reload(app)
    with TestClient(app.app) as client:
        with app.db() as c:
            c.execute('INSERT INTO devices VALUES(?,?,1)',('desk-1',app.digest('device-secret')))
            c.execute('INSERT INTO devices VALUES(?,?,0)',('desk-2',app.digest('lookup-secret')))
        yield app,client
def reg(client,sid='2026211001',uid='a1:b2:c3:d4',**extra):
    return client.post('/api/register',json=dict(student_id=sid,uid=uid,password='x',**extra))
def login(client,sid='2026211001',pw='x'):
    r=client.post('/api/login',json={'student_id':sid,'password':pw})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}
def test_registration_hash_uniqueness(env):
    app,c=env
    assert reg(c).status_code==201
    h=login(c); u=c.get('/api/me',headers=h).json()
    assert u['credit']==100 and u['nickname']=='2026211001' and u['uid']=='A1B2C3D4'
    assert 'password_hash' not in u
    assert reg(c,'2026211002').status_code==409
    with app.db() as db:
        r=db.execute('SELECT password_hash FROM users').fetchone()[0]
        assert r!='x' and r.startswith('$argon2id$')
def test_admin_auto_registration_and_access(env):
    _,c=env
    assert reg(c).status_code==201
    assert c.get('/api/admin/users',headers=login(c)).status_code==403
    assert c.get('/api/admin/users').status_code==401
    assert reg(c,'2026211348','11223344').status_code==201
    h=login(c,'2026211348')
    assert c.get('/api/admin/users',headers=h).json()['total']==2
def test_reset_revokes_and_password_change(env):
    _,c=env
    reg(c);reg(c,'2026211348','11223344')
    student=login(c);adm=login(c,'2026211348')
    body={'new_password':'1','admin_password':'bad'}
    assert c.post('/api/admin/users/2026211001/password',headers=adm,json=body).status_code==403
    body['admin_password']='x'
    assert c.post('/api/admin/users/2026211001/password',headers=adm,json=body).status_code==200
    assert c.get('/api/me',headers=student).status_code==401
    new=login(c,pw='1')
    assert c.post('/api/me/password',headers=new,json={'current_password':'1','new_password':'2'}).status_code==200
    assert c.get('/api/me',headers=new).status_code==401
    login(c,pw='2')
def test_device_and_idempotence(env):
    _,c=env;reg(c)
    h={'X-Device-Key':'device-secret'}
    assert c.post('/api/device/lookup',json={'uid':'A1B2C3D4'}).status_code==401
    assert c.post('/api/device/lookup',headers=h,json={'uid':'00000000'}).json()['allowed'] is False
    assert c.post('/api/device/lookup',headers=h,json={'uid':'A1B2C3D4'}).json()['allowed'] is True
    b={'uid':'A1B2C3D4','event_id':'evt-1','points':50,'reason':'检测到长时占座'}
    assert c.post('/api/device/violations',headers=h,json=b).json()['credit']==50
    assert c.post('/api/device/violations',headers=h,json=b).json()['duplicate'] is True
    b['points']=1
    assert c.post('/api/device/violations',headers=h,json=b).status_code==409
    assert c.post('/api/device/lookup',headers=h,json={'uid':'A1B2C3D4'}).json()['allowed'] is False
    b['event_id']='evt-2';b['points']=100
    assert c.post('/api/device/violations',headers=h,json=b).json()['credit']==0
def test_offline_registration(env):
    _,c=env
    b=dict(student_id='2026211002',uid='12345678',password='x')
    assert c.post('/api/device/register',headers={'X-Device-Key':'lookup-secret'},json=b).status_code==403
    assert c.post('/api/device/register',headers={'X-Device-Key':'device-secret'},json=b).status_code==201
def test_validation_profile_logout(env):
    _,c=env
    assert reg(c,uid='123').status_code==422
    reg(c);h=login(c)
    assert c.patch('/api/me',headers=h,json={'nickname':'书友','email':'a@example.edu'}).status_code==200
    assert c.get('/api/me',headers=h).json()['nickname']=='书友'
    assert c.post('/api/logout',headers=h).status_code==200
    assert c.get('/api/me',headers=h).status_code==401
def test_rate_limit(env):
    _,c=env
    for _ in range(20): assert c.post('/api/login',json={'student_id':'2026211001','password':'bad'}).status_code==401
    assert c.post('/api/login',json={'student_id':'2026211001','password':'bad'}).status_code==429
def test_concurrent_duplicate_event(env):
    from concurrent.futures import ThreadPoolExecutor
    app,c=env;reg(c)
    b={'uid':'A1B2C3D4','event_id':'concurrent-1','points':10,'reason':'same event retried'}
    def send(_): return c.post('/api/device/violations',headers={'X-Device-Key':'device-secret'},json=b)
    with ThreadPoolExecutor(max_workers=8) as pool: responses=list(pool.map(send,range(8)))
    assert all(r.status_code==200 for r in responses)
    assert sum(not r.json()['duplicate'] for r in responses)==1
    with app.db() as db: assert db.execute('SELECT credit FROM users').fetchone()[0]==90

def test_all_designated_admins(env):
    app,c=env
    for i,sid in enumerate(sorted(app.ADMINS)):
        assert reg(c,sid,f'{i+1:08X}').status_code==201
        u=c.get('/api/me',headers=login(c,sid)).json()
        assert u['admin']==1
        assert u['is_super_admin']==(sid=='2026211348')

def test_admin_create_user(env):
    app,c=env;reg(c);reg(c,'2026210633','11223344')
    body={'student_id':'2026211002','uid':'11223355'}
    assert c.post('/api/admin/users',json=body).status_code==401
    assert c.post('/api/admin/users',headers=login(c),json=body).status_code==403
    h=login(c,'2026210633')
    result=c.post('/api/admin/users',headers=h,json=body)
    assert result.status_code==201
    pw=result.json()['initial_password'];assert pw
    u=c.get('/api/me',headers=login(c,'2026211002',pw)).json()
    assert u['credit']==100 and u['admin']==0 and u['nickname']=='2026211002'
    assert c.post('/api/admin/users',headers=h,json=body).status_code==409
    body={'student_id':'2026210635','uid':'11223366','password':'1','nickname':'developer'}
    assert c.post('/api/admin/users',headers=h,json=body).status_code==201
    assert c.get('/api/me',headers=login(c,'2026210635','1')).json()['admin']==1
    with app.db() as db:
        assert db.execute("SELECT count(*) FROM audit WHERE action='admin_create_user' AND actor='2026210633'").fetchone()[0]==2

def test_super_admin_roles_live_and_persistent(env):
    app,c=env;reg(c);reg(c,'2026211348','11223344');reg(c,'2026210633','11223355')
    student=login(c);other=login(c,'2026210633');root=login(c,'2026211348')
    path='/api/admin/users/2026211001/admin'
    assert c.patch(path,json={'admin':True}).status_code==401
    assert c.patch(path,headers=student,json={'admin':True}).status_code==403
    assert c.patch(path,headers=other,json={'admin':True}).status_code==403
    assert c.patch(path,headers=root,json={'admin':True}).status_code==200
    assert c.get('/api/admin/users',headers=student).status_code==200
    assert c.patch('/api/admin/users/2026210633/admin',headers=root,json={'admin':False}).status_code==200
    assert c.get('/api/admin/users',headers=other).status_code==403
    assert c.patch(path,headers=root,json={'admin':False}).status_code==200
    assert c.get('/api/admin/users',headers=student).status_code==403
    assert c.patch('/api/admin/users/2026211348/admin',headers=root,json={'admin':False}).status_code==403
    assert c.patch('/api/admin/users/9999999999/admin',headers=root,json={'admin':True}).status_code==404
    app.init()
    assert c.get('/api/admin/users',headers=other).status_code==403
    assert c.get('/api/me',headers=root).json()['is_super_admin'] is True

def test_legacy_database_upgrade(env):
    app,c=env
    reg(c,'2026211348','11223344')
    with app.db() as db:
        db.execute('CREATE TABLE invites(code TEXT PRIMARY KEY,student_id TEXT)')
        db.execute("UPDATE users SET admin=0 WHERE student_id='2026211348'")
    app.init()
    with app.db() as db:
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE name='invites'").fetchone()[0]==0
    assert c.get('/api/me',headers=login(c,'2026211348')).json()['admin']==1

def test_admin_search(env):
    _,c=env;reg(c);reg(c,'2026211002','11223344');reg(c,'2026211348','11223355')
    h=login(c,'2026211348')
    r=c.get('/api/admin/users',headers=h,params={'q':'202621100','limit':1}).json()
    assert r['total']==2 and len(r['items'])==1
    assert c.get('/api/admin/users',headers=h,params={'q':'a1:b2'}).json()['items'][0]['student_id']=='2026211001'
    assert c.get('/api/admin/users',headers=h,params={'q':'%'}).json()['total']==0
    assert c.get('/api/admin/users',headers=h,params={'q':"' OR 1=1 --"}).json()['total']==0
    assert c.get('/api/admin/users',headers=h,params={'q':'nothing'}).json()['total']==0

def test_credit_adjustment_bounds_retry_and_permissions(env):
    app,c=env;reg(c);reg(c,'2026211348','11223344')
    h=login(c,'2026211348');normal=login(c);path='/api/admin/users/2026211001/credit'
    body={'request_id':'adjust-1','delta':-50,'reason':'人工复核'}
    assert c.post(path,json=body).status_code==401
    assert c.post(path,headers=normal,json=body).status_code==403
    r=c.post(path,headers=h,json=body).json();assert r['before']==100 and r['credit']==50
    assert c.post(path,headers=h,json=body).json()['duplicate'] is True
    assert c.post(path,headers=h,json={**body,'delta':-10}).status_code==409
    assert c.post(path,headers=h,json={**body,'request_id':'adjust-2','delta':10}).json()['credit']==60
    assert c.post('/api/device/lookup',headers={'X-Device-Key':'device-secret'},json={'uid':'A1B2C3D4'}).json()['allowed'] is True
    assert c.post(path,headers=h,json={**body,'request_id':'adjust-3','delta':100}).json()['credit']==100
    assert c.post(path,headers=h,json={**body,'request_id':'adjust-4','delta':-100}).json()['credit']==0
    assert c.post('/api/admin/users/9999999999/credit',headers=h,json={**body,'request_id':'missing'}).status_code==404
    for delta in [0,101,-101,True,1.5]:
        assert c.post(path,headers=h,json={**body,'delta':delta}).status_code==422
    assert c.post(path,headers=h,json={**body,'reason':'   '}).status_code==422
    with app.db() as db:
        assert db.execute('SELECT count(*) FROM credit_adjustments').fetchone()[0]==4

def test_credit_adjustment_concurrent_retry(env):
    from concurrent.futures import ThreadPoolExecutor
    _,c=env;reg(c);reg(c,'2026211348','11223344');h=login(c,'2026211348')
    body={'request_id':'parallel-adjust','delta':-5,'reason':'same adjustment'}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:c.post('/api/admin/users/2026211001/credit',headers=h,json=body),range(8)))
    assert all(r.status_code==200 and r.json()['credit']==95 for r in results)
    assert sum(not r.json()['duplicate'] for r in results)==1

def test_delete_account_confirmation_and_cleanup(env):
    app,c=env;reg(c);reg(c,'2026211348','11223344');h=login(c,'2026211348');normal=login(c)
    path='/api/admin/users/2026211001/delete';body={'confirm_student_id':'2026211001','uid':'A1B2C3D4'}
    assert c.post(path,json=body).status_code==401
    assert c.post(path,headers=normal,json=body).status_code==403
    assert c.post(path,headers=h,json={**body,'confirm_student_id':'2026211002'}).status_code==422
    assert c.post(path,headers=h,json={**body,'uid':'00000000'}).status_code==409
    event={'uid':'A1B2C3D4','event_id':'old-event','points':5,'reason':'历史违规'}
    c.post('/api/device/violations',headers={'X-Device-Key':'device-secret'},json=event)
    assert c.post(path,headers=h,json=body).status_code==200
    assert c.get('/api/me',headers=normal).status_code==401
    assert c.post('/api/device/lookup',headers={'X-Device-Key':'device-secret'},json={'uid':'A1B2C3D4'}).json()['allowed'] is False
    with app.db() as db:
        assert db.execute('SELECT count(*) FROM sessions WHERE student_id=?',('2026211001',)).fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM events').fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM audit WHERE action='admin_delete_user'").fetchone()[0]==1
    assert c.post(path,headers=h,json=body).status_code==404
    assert reg(c).status_code==201

def test_delete_admin_protections(env):
    _,c=env;reg(c,'2026211348','11223344');reg(c,'2026210633','11223355');reg(c,'2026210635','11223366')
    root=login(c,'2026211348');other=login(c,'2026210633')
    def delete(sid,uid,h):return c.post(f'/api/admin/users/{sid}/delete',headers=h,json={'confirm_student_id':sid,'uid':uid})
    assert delete('2026211348','11223344',root).status_code==403
    assert delete('2026210633','11223355',other).status_code==403
    assert delete('2026210635','11223366',other).status_code==403
    assert delete('2026210635','11223366',root).status_code==200
