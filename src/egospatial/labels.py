"""31 accepted spellings, representing 19 order-independent actions."""
import json

NAV = ["forward", "backward", "left", "right", "up", "down"]
OPPOSITE = dict(zip(NAV, ["backward", "forward", "right", "left", "down", "up"]))
LABELS = NAV + ["interact"] + [a+"+"+b for a in NAV for b in NAV
                            if b != a and b != OPPOSITE[a]]

def normalize(items):
    if not isinstance(items, list) or len(items) != 1 or items[0] not in LABELS:
        raise ValueError("Exactly one legal label string is required")
    return frozenset(items[0].split("+"))

def encode(parts):
    if not parts:
        return []
    value = ["+".join(parts)]
    normalize(value)
    return value

def schema():
    return {"type":"object", "properties":{
        "action_semantics":{"type":"string"},
        "action_labels":{"type":"array", "items":{"type":"string","enum":LABELS},
                         "minItems":1,"maxItems":1}},
        "required":["action_semantics","action_labels"],"additionalProperties":False}

def score(raw, expected):
    target = normalize(expected)
    try:
        text = raw.strip() if isinstance(raw, str) else json.dumps(raw)
        try:
            obj = json.loads(text)
        except ValueError:
            obj = json.loads(text[text.index("{"):text.rindex("}")+1])
        if not isinstance(obj, dict):
            raise ValueError("JSON object required")
        predicted = obj.get("action_labels")
        norm = normalize(predicted)
        valid = True
        fmt = set(obj) == {"action_semantics","action_labels"} and isinstance(obj["action_semantics"], str)
    except (ValueError, TypeError, KeyError):
        predicted, norm, valid, fmt = [], frozenset(), False, False
    return {"correct":valid and norm == target, "label_valid":valid, "format_valid":fmt,
            "predicted_labels":predicted if valid else [], "expected_labels":expected,
            "normalized_predicted_components":sorted(norm),
            "normalized_expected_components":sorted(target), "eligible":True,
            "error":None if valid else "invalid_json_or_compound_label"}
