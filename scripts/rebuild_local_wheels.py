"""Offline fallback: repackage installed pure Python distributions as local wheels.

Run with the host Python. These are local snapshots, not downloaded vendor wheels.
Only used when network access prevents installing the pinned dependencies.
"""
import base64
import csv
import hashlib
import importlib.metadata as metadata
import io
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
dest = root / ".wheelhouse"
dest.mkdir(exist_ok=True)
for name in ("pytest", "pluggy", "iniconfig", "packaging", "pygments", "setuptools", "wheel"):
    dist = metadata.distribution(name)
    info = f"{name}-{dist.version}.dist-info"
    content = {}
    if name == "iniconfig" and not dist.files:
        import iniconfig
        package = Path(iniconfig.__file__).parent
        for source in package.rglob("*.py"):
            content[str(Path("iniconfig") / source.relative_to(package))] = source.read_bytes()
    for entry in dist.files or []:
        path = Path(str(entry))
        if ".." in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.parts[0].endswith((".egg-info", ".dist-info")):
            continue
        source = Path(dist.locate_file(entry))
        if source.is_file():
            content[str(path)] = source.read_bytes()
    content[f"{info}/METADATA"] = (dist.read_text("METADATA") or dist.read_text("PKG-INFO")).encode()
    content[f"{info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: orderflow-offline-snapshot\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    ep = dist.read_text("entry_points.txt")
    if ep:
        content[f"{info}/entry_points.txt"] = ep.encode()
    for license_file in Path(dist._path).rglob("*"):
        if license_file.is_file() and any(s in license_file.name.lower() for s in ("license", "copying")):
            content[f"{info}/licenses/{license_file.name}"] = license_file.read_bytes()
    rows = []
    for path, value in content.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b"=").decode()
        rows.append((path, f"sha256={digest}", len(value)))
    rows.append((f"{info}/RECORD", "", ""))
    record = io.StringIO()
    csv.writer(record).writerows(rows)
    content[f"{info}/RECORD"] = record.getvalue().encode()
    wheel = dest / f"{name}-{dist.version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, value in content.items():
            archive.writestr(path, value)
    print(wheel.name)
