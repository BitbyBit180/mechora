import hashlib
from pathlib import Path

from django.conf import settings


def verify_model_integrity():
    """Verify the supplied model files against the published SHA-256 manifest."""
    root = Path(settings.BASE_DIR) / "round2_resources"
    manifest = root / "SHA256SUMS.txt"
    files = []
    missing = []
    if not manifest.exists():
        return {"valid": False, "checked": 0, "failed": [], "missing": ["SHA256SUMS.txt"], "files": []}

    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected, relative_path = line.split(maxsplit=1)
        relative_path = relative_path.strip()
        if not relative_path.startswith("Model/"):
            continue
        path = root / relative_path
        if not path.is_file():
            missing.append(relative_path)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": relative_path, "expected": expected, "actual": actual, "valid": actual == expected})

    failed = [item["path"] for item in files if not item["valid"]]
    return {"valid": not missing and not failed, "checked": len(files), "failed": failed, "missing": missing, "files": files}
