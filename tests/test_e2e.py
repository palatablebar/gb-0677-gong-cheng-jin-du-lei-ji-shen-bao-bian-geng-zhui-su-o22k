import csv,io
from app.pipeline import execute,load_sample
from app import store
def test_full_sample_flow(client):
    r=client.post("/api/runs",json={"sample":"dirty.csv"});assert r.status_code==200
    p=r.get_json();assert len(p["stages"])==7
    assert p["stages"][5]["metrics"]["balanced"] is True
def test_idempotent_real_input(sample):
    a=execute(sample);b=execute(sample)
    assert a["run_id"]==b["run_id"] and len(store.history())==1
def test_stale_review_409(client):
    "TRAP-26 陈旧复核不得覆盖新版本"
    p=client.post("/api/runs",json={"sample":"dirty.csv"}).get_json();u="/api/runs/"+p["run_id"]+"/review"
    assert client.post(u,json={"version":1,"decision":"已复核"}).status_code==200
    assert client.post(u,json={"version":1,"decision":"退回复核"}).status_code==409
def test_export_has_manifest_and_quarantine(client):
    p=client.post("/api/runs",json={"sample":"dirty.csv"}).get_json()
    r=client.get("/api/runs/"+p["run_id"]+"/archive")
    rows=list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
    assert rows[0][1]=="input_sha256" and any(x[3]=="quarantine" for x in rows[1:])
def test_failed_import_is_atomic(client):
    assert client.post("/api/runs",json={"csv":"bad"}).status_code==422
    assert store.history()==[]
def test_module_entrances(client):
    from app.config import MODULES
    for slug,name in MODULES:
        assert client.get("/api/"+slug).status_code==200
        assert client.get("/"+slug).status_code==200
def test_missing_run_404(client): assert client.get("/api/runs/missing").status_code==404
def run_with_advance(client,total,recovered):
    return client.post("/api/runs",json={"sample":"dirty.csv","parameters":{"advance_total":total,"advance_recovered":recovered}}).get_json()
def test_advance_cap_visible_in_run(client):
    "预付款只剩最后一笔可扣：本期扣回被压到上限，逐项保留依据"
    p=run_with_advance(client,"8000","7900")
    m=p["stages"][4]["metrics"]
    assert (m["advance_cap"],m["advance_deducted"],m["advance_remaining"])==("100.00","100.00","0.00") and m["capped_rows"]>0
    assert all("advance_basis" in r for r in p["stages"][4]["rows"])
def test_activate_switch_and_idempotent(client):
    p=run_with_advance(client,"8050","0")
    r=client.post("/api/runs/"+p["run_id"]+"/activate",json={})
    assert r.status_code==200 and r.get_json()["advance_remaining"]=="0.00"
    again=client.post("/api/runs/"+p["run_id"]+"/activate",json={}).get_json()
    assert again["version"]==r.get_json()["version"]
    assert client.get("/api/certificates/active").get_json()["run_id"]==p["run_id"]
def test_failed_switch_keeps_old_certificate(client):
    "新签证前期已扣回与当前剩余不符时切换失败，旧版保留"
    p1=run_with_advance(client,"8050","0")
    assert client.post("/api/runs/"+p1["run_id"]+"/activate",json={}).status_code==200
    p2=run_with_advance(client,"8050","100")
    assert client.post("/api/runs/"+p2["run_id"]+"/activate",json={}).status_code==409
    state=client.get("/api/certificates/active").get_json()
    assert state["run_id"]==p1["run_id"] and state["advance_remaining"]=="0.00" and state["version"]==1
def test_continuous_switch_succeeds(client):
    p1=run_with_advance(client,"9000","0")
    assert client.post("/api/runs/"+p1["run_id"]+"/activate",json={}).status_code==200
    p2=run_with_advance(client,"9000","950")
    r=client.post("/api/runs/"+p2["run_id"]+"/activate",json={})
    assert r.status_code==200 and r.get_json()["version"]==2 and r.get_json()["advance_remaining"]=="0.00"
def test_activate_missing_run_404(client): assert client.post("/api/runs/missing/activate",json={}).status_code==404
