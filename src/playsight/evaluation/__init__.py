"""Offline evaluation tooling for detection / tracking / identification quality.

These utilities are **offline tooling** for engineers benchmarking pipeline
quality against hand-labeled ground truth. They are not part of the runtime
match pipeline and require only core dependencies (numpy/pandas), never the
``[cv]`` extra.
"""

from playsight.evaluation.metrics import (
    count_id_switches,
    detection_precision_recall,
    evaluate_run,
    identification_accuracy,
    track_summary,
)

__all__ = [
    "count_id_switches",
    "detection_precision_recall",
    "evaluate_run",
    "identification_accuracy",
    "track_summary",
]
