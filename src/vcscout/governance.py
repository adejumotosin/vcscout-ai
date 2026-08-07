from __future__ import annotations

from typing import Any, Mapping

MIN_AUC_LIFT = 0.02
MIN_AP_LIFT = 0.01


def _metric(metrics: Mapping[str, Any] | None, name: str) -> float:
    if not metrics:
        return float("nan")
    try:
        return float(metrics[name])
    except (KeyError, TypeError, ValueError):
        return float("nan")


def select_production_candidate(
    incumbent_metrics: Mapping[str, Any] | None,
    candidates: Mapping[str, Mapping[str, Any]],
    *,
    min_auc_lift: float = MIN_AUC_LIFT,
    min_ap_lift: float = MIN_AP_LIFT,
) -> dict[str, Any]:
    """Choose whether a validated challenger is allowed to replace production.

    A challenger must improve both ROC-AUC and average precision by material
    minimums and must be compatible with the live inference feature set. If no
    incumbent exists, the strongest live-compatible candidate is selected.
    """
    incumbent_auc = _metric(incumbent_metrics, "roc_auc")
    incumbent_ap = _metric(incumbent_metrics, "average_precision")
    incumbent_exists = incumbent_auc == incumbent_auc and incumbent_ap == incumbent_ap

    evaluated: dict[str, dict[str, Any]] = {}
    eligible: list[tuple[str, float, float]] = []

    for name, candidate in candidates.items():
        metrics = candidate.get("metrics") or {}
        auc = _metric(metrics, "roc_auc")
        ap = _metric(metrics, "average_precision")
        live_compatible = bool(candidate.get("live_compatible", False))

        auc_lift = auc - incumbent_auc if incumbent_exists else None
        ap_lift = ap - incumbent_ap if incumbent_exists else None
        passes_metrics = (
            not incumbent_exists
            or (
                auc_lift is not None
                and ap_lift is not None
                and auc_lift >= min_auc_lift
                and ap_lift >= min_ap_lift
            )
        )
        promotion_eligible = bool(live_compatible and passes_metrics)

        evaluated[name] = {
            "roc_auc": auc,
            "average_precision": ap,
            "auc_lift_vs_incumbent": round(auc_lift, 4) if auc_lift is not None else None,
            "ap_lift_vs_incumbent": round(ap_lift, 4) if ap_lift is not None else None,
            "live_compatible": live_compatible,
            "passes_material_lift": bool(passes_metrics),
            "promotion_eligible": promotion_eligible,
        }
        if promotion_eligible:
            eligible.append((name, auc, ap))

    if eligible:
        selected_name, _, _ = max(eligible, key=lambda item: (item[1], item[2]))
        return {
            "promote": True,
            "selected_model": selected_name,
            "reason": "Challenger cleared material ROC-AUC and average-precision lift thresholds and is live-compatible.",
            "policy": {
                "minimum_auc_lift": min_auc_lift,
                "minimum_average_precision_lift": min_ap_lift,
                "requires_both": True,
                "requires_live_feature_compatibility": True,
            },
            "incumbent": {
                "roc_auc": incumbent_auc if incumbent_exists else None,
                "average_precision": incumbent_ap if incumbent_exists else None,
            },
            "candidates": evaluated,
        }

    return {
        "promote": False,
        "selected_model": "incumbent" if incumbent_exists else None,
        "reason": (
            "No challenger cleared the material lift and live-compatibility gates."
            if incumbent_exists
            else "No live-compatible candidate is available for initial production selection."
        ),
        "policy": {
            "minimum_auc_lift": min_auc_lift,
            "minimum_average_precision_lift": min_ap_lift,
            "requires_both": True,
            "requires_live_feature_compatibility": True,
        },
        "incumbent": {
            "roc_auc": incumbent_auc if incumbent_exists else None,
            "average_precision": incumbent_ap if incumbent_exists else None,
        },
        "candidates": evaluated,
    }
