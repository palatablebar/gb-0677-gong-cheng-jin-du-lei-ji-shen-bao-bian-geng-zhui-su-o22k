from app.modules.m7_certificates.rules import evaluate
from app.errors import DomainError
import pytest
def test_real_sample_archive_ready(result): assert result["stages"][6]["metrics"]["ready"] is True
def test_real_sample_archive_source_count(result): assert result["stages"][6]["metrics"]["source_lines"]==result["stages"][5]["metrics"]["accepted_inputs"]
def test_real_sample_seal_stable(result):
    rows=result["stages"][5]["rows"];assert evaluate(rows,{})["metrics"]["sha256"]==evaluate(rows,{})["metrics"]["sha256"]
def test_unbalanced_blocked():
    with pytest.raises(DomainError) as e:evaluate([],{"reconcile":{"metrics":{"balanced":False}}})
    assert e.value.code=="UNBALANCED"
def test_duplicate_archive_key():
    with pytest.raises(DomainError):evaluate([{"claim_id":"1"},{"claim_id":"1"}],{})
def test_real_sample_manifest_has_hash(result): assert len(result["manifest"]["input_sha256"])==64
def test_real_sample_export_rows_match(result): assert result["stages"][6]["rows"]==result["stages"][5]["rows"]
def test_certificate_blocks_over_advance():
    "签证不得让累计扣回超出原预付款"
    ctx={"deductions":{"metrics":{"advance_total":"100","advance_recovered_before":"90","advance_deducted":"20.00","advance_remaining":"-10.00"}}}
    with pytest.raises(DomainError) as e:evaluate([],ctx)
    assert e.value.code=="ADVANCE_EXCEEDED"
def test_certificate_carries_rebalanced_advance():
    ctx={"deductions":{"metrics":{"advance_total":"100","advance_recovered_before":"90","advance_deducted":"10.00","advance_remaining":"0.00"}}}
    m=evaluate([],ctx)["metrics"]
    assert m["advance_total"]=="100" and m["advance_remaining"]=="0.00" and m["ready"] is True
