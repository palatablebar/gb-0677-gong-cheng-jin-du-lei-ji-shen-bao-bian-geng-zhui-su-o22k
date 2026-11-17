import hashlib,json
from app.errors import DomainError
from app.reasons import sources
from app.values import number
def evaluate(rows,context):
    stages=[v for v in context.values() if isinstance(v,dict) and "metrics" in v]
    balances=[s["metrics"]["balanced"] for s in stages if "balanced" in s["metrics"]]
    if balances and not all(balances): raise DomainError("UNBALANCED","来源行未对平，不能归档")
    ids=[str(r.get("claim_id",r.get("_line",""))) for r in rows]
    if len(ids)!=len(set(ids)): raise DomainError("ARCHIVE_DUPLICATE","归档业务键重复")
    deductions=context.get("deductions",{}).get("metrics",{})
    metrics={"records":len(rows),"source_lines":len(set(x for row in rows for x in sources(row)))}
    if "advance_remaining" in deductions:
        remaining=number(deductions["advance_remaining"])
        if remaining<0 or number(deductions["advance_recovered_before"])+number(deductions["advance_deducted"])>number(deductions["advance_total"]):
            raise DomainError("ADVANCE_EXCEEDED","累计扣回超出原预付款，不能归档")
        metrics.update(advance_total=deductions["advance_total"],advance_remaining=deductions["advance_remaining"])
    encoded=json.dumps(rows,ensure_ascii=False,sort_keys=True,default=str).encode()
    metrics.update(sha256=hashlib.sha256(encoded).hexdigest(),ready=True,differences=sum(r.get("status")=="差异" for r in rows))
    return {"rows":rows,"quarantine":[],"metrics":metrics}
