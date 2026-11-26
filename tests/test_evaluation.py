from pathlib import Path
import json
import pytest
from egospatial.evaluation import evaluate
from egospatial.io import read,write

def test_skip_resume_retry_and_reject_changed_inputs(dataset,tmp_path):
    calls=[]
    def model(req,images):
        assert "reference" not in req
        calls.append(req["sample_id"])
        assert len(images)==len(req["image_sha256"])
        if len(calls)==1:
            raise ConnectionError("transient")
        return {"answer":'{"action_semantics":"test","action_labels":["interact"]}',"model":"fake"}
    out=tmp_path/"runs"
    result=evaluate(dataset.path,out,"fake",retries=1,adapter=model)
    assert result["all"]["completed"]==3
    assert len(calls)==4
    evaluate(dataset.path,out,"fake",adapter=model)
    assert len(calls)==4
    # A wrong answer was saved once, not retried.
    assert result["all"]["correct"]==1
    with pytest.raises(ValueError,match="config changed"):
        evaluate(dataset.path,out,"another",adapter=model)
    dataset.image(5).write_bytes(b"changed")
    with pytest.raises(ValueError,match="Input bytes"):
        evaluate(dataset.path,out,"fake",adapter=model)

def test_failed_calls_remain_failed_and_are_resumable(dataset,tmp_path):
    def fail(*args):
        raise TimeoutError()
    out=tmp_path/"failure"
    result=evaluate(dataset.path,out,"fake",retries=0,adapter=fail)
    assert result["all"]["completed"]==0
    def success(*args):
        return {"answer":'{"action_semantics":"ok","action_labels":["up"]}'}
    result=evaluate(dataset.path,out,"fake",retries=0,adapter=success)
    assert result["all"]["completed"]==3
