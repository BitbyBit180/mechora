import csv
from pathlib import Path

from django.conf import settings

from .inference import predict


def evaluate_samples():
    root = Path(settings.BASE_DIR) / "round2_resources" / "Samples"
    rows = []
    counts = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    failed = []
    with (root / "labels.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            image_path = root / row["relative_path"]
            actual = row["label"]
            try:
                result = predict(image_path)
                predicted = result["predicted_class"]
                if actual == "Defective" and predicted == "Defective":
                    counts["TP"] += 1
                elif actual == "Normal" and predicted == "Normal":
                    counts["TN"] += 1
                elif actual == "Normal" and predicted == "Defective":
                    counts["FP"] += 1
                else:
                    counts["FN"] += 1
                rows.append({"image_id": row["image_id"], "actual": actual, "predicted": predicted, "confidence": result["confidence"]})
            except Exception as exc:
                failed.append({"image_id": row["image_id"], "error": str(exc)})
    processed = len(rows)
    total = processed + len(failed)
    accuracy = (counts["TP"] + counts["TN"]) / processed if processed else 0.0
    precision = counts["TP"] / (counts["TP"] + counts["FP"]) if counts["TP"] + counts["FP"] else 0.0
    recall = counts["TP"] / (counts["TP"] + counts["FN"]) if counts["TP"] + counts["FN"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "total_samples": total,
        "processed_samples": processed,
        "failed_predictions": len(failed),
        "true_positives": counts["TP"],
        "true_negatives": counts["TN"],
        "false_positives": counts["FP"],
        "false_negatives": counts["FN"],
        "accuracy": accuracy,
        "precision": precision,
        "defect_recall": recall,
        "f1_score": f1,
        "confusion_matrix": {"actual_normal": {"normal": counts["TN"], "defective": counts["FP"]}, "actual_defective": {"normal": counts["FN"], "defective": counts["TP"]}},
        "failures": failed,
        "results": rows,
        "limitations": [
            "The dataset contains synthetic images and only 60 samples.",
            "The model targets P-PLATE01 and fixed image framing.",
            "These results do not establish real-world industrial reliability.",
        ],
    }
