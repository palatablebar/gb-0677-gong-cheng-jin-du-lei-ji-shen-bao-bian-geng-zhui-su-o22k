import sqlite3,json
from datetime import datetime,timezone
from pathlib import Path
from app.config import DATA_DIR
from app.errors import DomainError
from app.values import number
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS certificates (project TEXT PRIMARY KEY,run_id TEXT NOT NULL,advance_remaining TEXT,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS certificate_events (project TEXT NOT NULL,run_id TEXT NOT NULL,deducted TEXT,applied_at TEXT NOT NULL,PRIMARY KEY(project,run_id))")
    return db
def save(run_id,payload):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES (?,?)",(run_id,json.dumps(payload,ensure_ascii=False)))
    return get(run_id)
def get(run_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone(): raise DomainError("NOT_FOUND","批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)
def certificate_state(project="default"):
    with connect() as db: row=db.execute("SELECT project,run_id,advance_remaining,version,updated_at FROM certificates WHERE project=?",(project,)).fetchone()
    if not row: return {"project":project,"run_id":None,"advance_remaining":None,"version":0,"updated_at":None}
    return {"project":row[0],"run_id":row[1],"advance_remaining":row[2],"version":row[3],"updated_at":row[4]}
def activate(run_id,project="default"):
    """把指定批次的签证切换为项目当前签证。

    整个校验与切换在单一事务内完成：任一步失败即回滚，旧版签证原样保留。
    同一批次重复签发直接返回现状，预付款不会重复扣减。
    """
    with connect() as db:
        row=db.execute("SELECT payload FROM runs WHERE id=?",(run_id,)).fetchone()
        if not row: raise DomainError("NOT_FOUND","批次不存在",404)
        metrics=json.loads(row[0])["stages"][4]["metrics"]
        before=metrics.get("advance_recovered_before");deducted=metrics.get("advance_deducted")
        total=metrics.get("advance_total");remaining=metrics.get("advance_remaining")
        if remaining is not None and (number(remaining)<0 or number(before)+number(deducted)>number(total)):
            raise DomainError("ADVANCE_EXCEEDED","累计扣回超出原预付款，已保留旧版签证")
        current=db.execute("SELECT run_id,advance_remaining,version FROM certificates WHERE project=?",(project,)).fetchone()
        if current and current[0]==run_id: return certificate_state(project)
        if current and current[1] is not None and before is not None and number(before)!=number(current[1]):
            raise DomainError("ADVANCE_DISCONTINUOUS","新签证的前期已扣回与当前剩余预付款不符，已保留旧版签证",409)
        now=datetime.now(timezone.utc).isoformat()
        db.execute("INSERT OR IGNORE INTO certificate_events(project,run_id,deducted,applied_at) VALUES (?,?,?,?)",(project,run_id,deducted,now))
        db.execute("INSERT OR REPLACE INTO certificates(project,run_id,advance_remaining,version,updated_at) VALUES (?,?,?,?,?)",(project,run_id,remaining,(current[2] if current else 0)+1,now))
    return certificate_state(project)
