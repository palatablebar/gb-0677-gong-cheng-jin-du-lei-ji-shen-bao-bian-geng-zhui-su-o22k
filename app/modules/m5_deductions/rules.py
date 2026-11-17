from decimal import Decimal, ROUND_FLOOR
from app.values import number, money
from app.errors import DomainError

CENT = Decimal("0.01")


def _percent(rate):
    text = format(rate * 100, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text + "%"


def _allocate(amounts, target):
    """把target按amounts比例摊到各项，逐项量化到分且合计恰好等于target。

    只缩不放：target<=sum(amounts)。每项实摊不超过自身算额，
    不会为凑总额把一项的扣回挪给另一项。
    """
    total = sum(amounts, Decimal(0))
    if total <= 0:
        return [Decimal("0.00") for _ in amounts]
    raw = [a * target / total for a in amounts]
    floors = [r.quantize(CENT, rounding=ROUND_FLOOR) for r in raw]
    remainder = int((target - sum(floors, Decimal(0))) / CENT)
    order = sorted(range(len(amounts)), key=lambda i: (raw[i] - floors[i], amounts[i]), reverse=True)
    for i in order[:remainder]:
        floors[i] += CENT
    return floors


def evaluate(rows, context):
    p = context.get("parameters", {})
    retention = number(p.get("retention_rate", "0.05"))
    advance = number(p.get("advance_rate", "0.10"))
    if not Decimal(0) <= retention <= 1 or not Decimal(0) <= advance <= 1 or retention + advance > 1:
        raise DomainError("BAD_DEDUCTION", "扣回比例无效")
    cap = total_advance = recovered_before = None
    if p.get("advance_total") is not None:
        total_advance = number(p.get("advance_total"))
        recovered_before = number(p.get("advance_recovered", "0"))
        if total_advance < 0 or recovered_before < 0:
            raise DomainError("BAD_ADVANCE", "预付款参数不能为负")
        if recovered_before > total_advance:
            raise DomainError("BAD_ADVANCE", "已扣回超过预付款总额")
        cap = number(money(total_advance - recovered_before))
    computed = []
    for row in rows:
        gross = number(row["gross_amount"])
        ret = number(money(gross * retention))
        adv = number(money(gross * advance))
        computed.append({"row": row, "gross": gross, "ret": ret, "basis": adv, "applied": adv, "capped": False})
    if cap is not None:
        positives = [c for c in computed if c["applied"] > 0]
        reversals = sum((c["applied"] for c in computed if c["applied"] < 0), Decimal(0))
        period_total = sum((c["applied"] for c in computed), Decimal(0))
        if period_total > cap:
            target = number(money(cap - reversals))
            for c, value in zip(positives, _allocate([c["applied"] for c in positives], target)):
                c["applied"] = value
                c["capped"] = True
    good = []
    for c in computed:
        gross, ret, adv = c["gross"], c["ret"], c["applied"]
        net = gross - ret - adv
        basis = f"{money(gross)}×{_percent(advance)}={money(c['basis'])}"
        if adv < 0:
            basis += "（已批冲回回补）"
        if c["capped"]:
            basis += f"→限额摊减为{money(adv)}"
        good.append({**c["row"], "retention": money(ret), "advance_recovery": money(adv), "advance_basis": basis, "expected": money(net)})
    metrics = {
        "gross_total": money(sum((c["gross"] for c in computed), Decimal(0))),
        "net_total": money(sum((number(r["expected"]) for r in good), Decimal(0))),
        "advance_deducted": money(sum((c["applied"] for c in computed), Decimal(0))),
    }
    if cap is not None:
        metrics.update(
            advance_total=money(total_advance),
            advance_recovered_before=money(recovered_before),
            advance_cap=money(cap),
            advance_remaining=money(cap - number(metrics["advance_deducted"])),
            capped_rows=sum(1 for c in computed if c["capped"]),
        )
    return {"rows": good, "quarantine": [], "metrics": metrics}
