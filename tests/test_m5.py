from app.modules.m5_deductions.rules import evaluate
from decimal import Decimal
import pytest
from app.errors import DomainError
def test_real_net_total(result): assert result["stages"][4]["metrics"]["net_total"]=="68425.00"
def test_retention_advance_separate():
    row=evaluate([{"gross_amount":"3000"}],{})["rows"][0];assert (row["retention"],row["advance_recovery"],row["expected"])==("150.00","300.00","2550.00")
def test_negative_deduction_reverses(): assert evaluate([{"gross_amount":"-100"}],{})["rows"][0]["expected"]=="-85.00"
def test_fraction_rounds_to_cent():
    "TRAP-10"
    row=evaluate([{"gross_amount":"0.13"}],{})["rows"][0];assert row["retention"]=="0.01" and row["advance_recovery"]=="0.01" and row["expected"]=="0.11"
def test_money_conservation_real_sample(result):
    assert all(Decimal(r["gross_amount"])==Decimal(r["retention"])+Decimal(r["advance_recovery"])+Decimal(r["expected"]) for r in result["stages"][4]["rows"])
def test_invalid_ratio_rejected():
    with pytest.raises(DomainError):evaluate([],{"parameters":{"retention_rate":"0.9","advance_rate":"0.2"}})
def test_empty_deductions_zero(): assert evaluate([],{})["metrics"]["net_total"]=="0.00"
def test_cap_scales_positive_items_proportionally():
    r=evaluate([{"gross_amount":"3000"},{"gross_amount":"2000"}],{"parameters":{"advance_total":"400"}})
    assert [x["advance_recovery"] for x in r["rows"]]==["240.00","160.00"]
    m=r["metrics"];assert (m["advance_cap"],m["advance_deducted"],m["advance_remaining"],m["capped_rows"])==("400.00","400.00","0.00",2)
def test_cap_not_binding_keeps_items():
    r=evaluate([{"gross_amount":"3000"}],{"parameters":{"advance_total":"99999"}})
    assert r["rows"][0]["advance_recovery"]=="300.00" and r["metrics"]["capped_rows"]==0
def test_no_cross_item_subsidy():
    "承包方要求：每项实扣不超过自身依据，不为凑总额把甲项扣回挪给乙项"
    r=evaluate([{"gross_amount":"3000"},{"gross_amount":"2000"}],{"parameters":{"advance_total":"400"}})
    for row,computed in zip(r["rows"],("300.00","200.00")): assert Decimal(row["advance_recovery"])<=Decimal(computed)
def test_reversal_rebalances_period_total():
    "冲回项原样回补，只压减正向扣回使净额落在上限内"
    rows=[{"gross_amount":"3000"},{"gross_amount":"-1000"}]
    assert [x["advance_recovery"] for x in evaluate(rows,{"parameters":{"advance_total":"250"}})["rows"]]==["300.00","-100.00"]
    capped=evaluate(rows,{"parameters":{"advance_total":"150"}})
    assert [x["advance_recovery"] for x in capped["rows"]]==["250.00","-100.00"]
    assert capped["metrics"]["advance_remaining"]=="0.00"
def test_cap_allocation_exact_to_cent():
    r=evaluate([{"gross_amount":"0.13"},{"gross_amount":"0.13"},{"gross_amount":"0.13"}],{"parameters":{"advance_total":"0.02"}})
    assert sum(Decimal(x["advance_recovery"]) for x in r["rows"])==Decimal("0.02")
def test_conservation_under_cap():
    r=evaluate([{"gross_amount":"3000"},{"gross_amount":"2000"}],{"parameters":{"advance_total":"400"}})
    assert all(Decimal(x["gross_amount"])==Decimal(x["retention"])+Decimal(x["advance_recovery"])+Decimal(x["expected"]) for x in r["rows"])
def test_fully_recovered_stops_deduction():
    r=evaluate([{"gross_amount":"3000"}],{"parameters":{"advance_total":"1000","advance_recovered":"1000"}})
    assert r["rows"][0]["advance_recovery"]=="0.00" and r["metrics"]["advance_remaining"]=="0.00"
def test_over_recovered_rejected():
    with pytest.raises(DomainError):evaluate([{"gross_amount":"1"}],{"parameters":{"advance_total":"100","advance_recovered":"101"}})
def test_basis_lands_on_each_item():
    row=evaluate([{"gross_amount":"3000","claim_id":"A"}],{"parameters":{"advance_total":"100"}})["rows"][0]
    assert "3000.00" in row["advance_basis"] and "300.00" in row["advance_basis"] and "100.00" in row["advance_basis"]
def test_real_sample_last_draw(sample):
    from app.pipeline import calculate
    r=calculate(sample,{"advance_total":"8050","advance_recovered":"7950"})
    m=r["stages"][4]["metrics"]
    assert (m["advance_cap"],m["advance_deducted"],m["advance_remaining"])==("100.00","100.00","0.00")
    assert all("advance_basis" in x for x in r["stages"][4]["rows"])
