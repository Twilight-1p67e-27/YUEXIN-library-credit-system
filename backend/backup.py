"""在线一致性备份：python backend/backup.py /safe/path/library-backup.db"""
import sys, sqlite3
from pathlib import Path
from app import DB
if len(sys.argv)!=2: raise SystemExit('usage: python backend/backup.py TARGET.db')
target=Path(sys.argv[1]).resolve()
if target.exists() or target==Path(DB).resolve(): raise SystemExit('目标必须是尚不存在的新文件')
if not Path(DB).exists(): raise SystemExit('源数据库不存在，请检查 DB_PATH')
target.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(DB) as source, sqlite3.connect(target) as dest:
    source.backup(dest)
print(target)
