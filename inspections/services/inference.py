import importlib.util
from pathlib import Path

from django.conf import settings


_REFERENCE_PATH = Path(settings.BASE_DIR) / "round2_resources" / "Model" / "inference.py"
_MODEL_PATH = Path(settings.BASE_DIR) / "round2_resources" / "Model" / "classifier.npz"
_SPEC = importlib.util.spec_from_file_location("mechora_round2_inference", _REFERENCE_PATH)
_REFERENCE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_REFERENCE)


def predict(image_path):
    """Delegate preprocessing and prediction to the supplied reference helper."""
    return _REFERENCE.predict(str(image_path), model_path=_MODEL_PATH)
