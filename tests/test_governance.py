from vcscout.governance import select_production_candidate


def test_small_auc_gain_with_ap_loss_does_not_promote() -> None:
    decision = select_production_candidate(
        {"roc_auc": 0.6252, "average_precision": 0.6583},
        {
            "expanded": {
                "metrics": {"roc_auc": 0.6274, "average_precision": 0.6321},
                "live_compatible": False,
            }
        },
    )
    assert decision["promote"] is False
    assert decision["selected_model"] == "incumbent"


def test_material_improvement_promotes_live_compatible_challenger() -> None:
    decision = select_production_candidate(
        {"roc_auc": 0.62, "average_precision": 0.64},
        {
            "candidate": {
                "metrics": {"roc_auc": 0.66, "average_precision": 0.67},
                "live_compatible": True,
            }
        },
    )
    assert decision["promote"] is True
    assert decision["selected_model"] == "candidate"


def test_incompatible_challenger_cannot_promote_even_if_metrics_improve() -> None:
    decision = select_production_candidate(
        {"roc_auc": 0.62, "average_precision": 0.64},
        {
            "candidate": {
                "metrics": {"roc_auc": 0.70, "average_precision": 0.72},
                "live_compatible": False,
            }
        },
    )
    assert decision["promote"] is False
    assert decision["candidates"]["candidate"]["promotion_eligible"] is False
