"""部署服务器设备密钥管理。"""
import argparse, secrets
from app import init, db, digest, audit
p=argparse.ArgumentParser()
sub=p.add_subparsers(dest='command',required=True)
d=sub.add_parser('device'); d.add_argument('device_id'); d.add_argument('--enrollment',action='store_true')
r=sub.add_parser('revoke-device'); r.add_argument('device_id')
a=p.parse_args(); init()
with db() as c:
    if a.command=='device':
        token=secrets.token_urlsafe(32)
        c.execute('INSERT INTO devices VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET token=excluded.token,enrollment=excluded.enrollment',(a.device_id,digest(token),int(a.enrollment)))
        print('X-Device-Key:',token)
    else: c.execute('DELETE FROM devices WHERE id=?',(a.device_id,))
    audit(c,'server-operator',a.command,a.device_id)
