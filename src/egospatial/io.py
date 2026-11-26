"""Deterministic JSON, hashes, portable paths, atomic writes."""
import hashlib
import json
from pathlib import Path

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def resolve(root, relative):
    root = Path(root).resolve()
    p = (root / relative).resolve()
    if not p.is_relative_to(root):
        raise ValueError("Asset escapes its root")
    return p

def manifest(root):
    root = Path(root)
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*"))
            if p.is_file() and p != root / "SHA256SUMS.json"}

def verify(root):
    root = Path(root)
    entries = read(root / "SHA256SUMS.json")
    for name, expected in entries.items():
        if sha(resolve(root, name)) != expected:
            raise ValueError("SHA mismatch: " + name)
    return {"verified_files": len(entries)}
