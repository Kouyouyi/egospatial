import json
import pytest
from egospatial.labels import LABELS,normalize,score

def test_taxonomy_count():
    assert len(LABELS)==31
    assert len({normalize([x]) for x in LABELS})==19

@pytest.mark.parametrize("label",["left+right","forward+backward","up+down","left+left",
                                   "left+forward+up","interact+right"])
def test_invalid_compounds(label):
    with pytest.raises(ValueError):
        normalize([label])

def test_order_invariant_and_semantics_not_scored():
    sc=score('{"action_semantics":"different prose","action_labels":["forward+right"]}',["right+forward"])
    assert sc["correct"] and sc["format_valid"]
    assert not score('{"action_labels":["left","up"]}',["left+up"])["correct"]
    assert not score('no json',["up"])["label_valid"]
    assert not score('null',["up"])["correct"]
