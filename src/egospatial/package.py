"""Build a shareable zip with file-level SHA-256 and no implicit external symlinks."""
from pathlib import Path
import zipfile
from .io import write, manifest, sha, verify

def package(directory, output):
    root = Path(directory).resolve()
    dest = Path(output).resolve()
    if dest.is_relative_to(root):
        raise ValueError("Archive must be outside the bundle directory")
    for p in root.rglob("*"):
        if p.is_symlink():
            raise ValueError("Bundle must contain regular files, no external symlinks")
    write(root/"SHA256SUMS.json",manifest(root))
    verified = verify(root)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=5,
                         allowZip64=True) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                z.write(p,root.name+"/"+str(p.relative_to(root)))
    with zipfile.ZipFile(dest) as z:
        bad = z.testzip()
        if bad:
            raise ValueError("ZIP CRC mismatch: "+bad)
    checksum = sha(dest)
    dest.with_suffix(dest.suffix+".sha256").write_text(checksum+"  "+dest.name+"\n")
    return {"archive":str(dest),"bytes":dest.stat().st_size,"sha256":checksum,**verified}
