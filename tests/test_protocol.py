import copy
import json
import pytest
from egospatial.protocol import compile_request
from egospatial.dataset import Dataset
from egospatial.io import write

def test_anchor_memory_and_gt_prefix(dataset):
    e=dataset.episodes[0]
    first=compile_request(dataset,e,0)
    assert first["image_source_frames"] == [1,5]
    second=compile_request(dataset,e,1)
    assert second["image_source_frames"] == [1,5,8]
    assert "SECRET_NEXT_REFERENCE" not in json.dumps(second)
    assert second["messages"][0]["role"] == "system"
    assert "interact" in second["messages"][1]["content"][-4]["text"]
    assert 12 not in second["image_source_frames"]

def test_pending_history_observation_is_not_a_fabricated_label(dataset):
    req=compile_request(dataset,dataset.episodes[0],3)
    assert req["image_source_frames"] == [1,5,8,12,15]
    assert "标签待复核" in json.dumps(req,ensure_ascii=False)
    assert len(list(dataset.cases())) == 3

def test_future_memory_and_gapped_boundaries_rejected(dataset):
    d=copy.deepcopy(dataset.data)
    d["episodes"][0]["spatial_memory"][0]["frame"]["source_frame"]=6
    write(dataset.path,d)
    with pytest.raises(ValueError,match="memory"):
        Dataset(dataset.path)
    d=copy.deepcopy(dataset.data)
    d["episodes"][0]["steps"][1]["before_frame"]=9
    write(dataset.path,d)
    with pytest.raises(ValueError,match="boundaries"):
        Dataset(dataset.path)
