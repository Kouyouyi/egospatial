import json
import shutil
import subprocess
from pathlib import Path
import pytest
from egospatial.evaluation import evaluate
from egospatial.export import export
from egospatial.io import read,verify
from egospatial.package import package

def test_complete_export_and_portable_archive(dataset,tmp_path):
    def fake(*args):
        return {"answer":'{"action_semantics":"test","action_labels":["interact"]}'}
    run=tmp_path/"run"
    evaluate(dataset.path,run,"fake",retries=0,adapter=fake)
    out=tmp_path/"review"
    result=export(dataset.path,run,out)
    assert result["completed"]==3
    index=read(out/"index.json")
    assert index["total"]==3 and index["summary"]["all"]["correct"]==1
    assert len((out/"all-results.jsonl").read_text().splitlines())==3
    assert verify(out)["verified_files"]>0
    if shutil.which("node"):
        smoke=Path(__file__).with_name("review_smoke.cjs")
        subprocess.run(["node",str(smoke),str(out)],check=True,capture_output=True,text=True)
    archive=package(out,tmp_path/"bundle.zip")
    assert archive["bytes"]>0
    with pytest.raises(ValueError,match="empty"):
        export(dataset.path,run,out)
