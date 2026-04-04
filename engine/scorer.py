WEIGHTS = {"topology": 0.30, "gex": 0.25, "reserves_rrp": 0.20, "oas": 0.10, "walcl": 0.10, "auction": 0.05}

def score(topology, entropy, walcl, reserves_rrp, oas, gex, auctions):
    if entropy.get("status") == "CRITICAL":
        return _kill("CRITICAL entropy — edge is gone, no new positions.")
    regime = topology.get("regime", "UNKNOWN")
    if regime == "UNCHARTED":
        return _kill("Topology UNCHARTED — close or hedge everything.")
    entropy_factor = entropy.get("size_factor", 1.0)
    dist_factor = topology.get("dist_factor", 1.0)
    mom_factor = 1.0 if topology.get("aligned", True) else 0.5
    auction_mod = 0.5 if auctions.get("warning") else 1.0
    size_factor = entropy_factor * dist_factor * mom_factor * auction_mod
    if size_factor >= 0.9:
        size_rule = "FULL SIZE"
    elif size_factor >= 0.45:
        size_rule = "HALF SIZE"
    elif size_factor > 0:
        size_rule = "QUARTER SIZE"
    else:
        size_rule = "NO TRADE"
    pca1 = topology.get("pca1", 0)
    topo_vote = max(-1.0, min(1.0, pca1 * (1.0 if topology.get("aligned", True) else 0.5)))
    if gex and not gex.get("error"):
        above = gex.get("above_vol_trigger", False)
        pos = gex.get("positive_gamma", False)
        gex_vote = 0.5 if (above and pos) else -1.0 if (not above and not pos) else -0.5 if (above and not pos) else 0.5
    else:
        gex_vote = 0.0
    res_vote = max(-1.0, min(1.0, reserves_rrp.get("direction", 0) * reserves_rrp.get("strength", 1.0)))
    oas_vote = float(oas.get("direction", 0))
    walcl_vote = float(walcl.get("direction", 0))
    auction_vote = -0.5 if auctions.get("warning") else 0.0
    votes = {"topology": topo_vote, "gex": gex_vote, "reserves_rrp": res_vote,
             "oas": oas_vote, "walcl": walcl_vote, "auction": auction_vote}
    raw = sum(votes[k] * WEIGHTS[k] for k in votes) * entropy_factor
    score_val = max(-1.0, min(1.0, raw))
    conviction = round(abs(score_val) * 100, 1)
    if score_val > 0.25:
        direction = "BULLISH"
    elif score_val < -0.25:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    return {
        "direction": direction, "conviction": conviction, "size_rule": size_rule,
        "size_factor": round(size_factor, 2), "score": round(score_val, 3), "votes": votes,
        "narrative": _narrative(direction, conviction, regime, entropy.get("status"), gex, reserves_rrp),
        "killed": False, "kill_reason": None,
    }

def _kill(reason):
    return {"direction": "NO TRADE", "conviction": 0, "size_rule": "NO TRADE",
            "size_factor": 0.0, "score": 0, "votes": {}, "narrative": reason,
            "killed": True, "kill_reason": reason}

def _narrative(direction, conviction, regime, entropy_status, gex, reserves_rrp):
    parts = []
    strength = "strongly" if conviction >= 70 else "leaning" if conviction >= 45 else "weakly"
    parts.append(f"{strength} {direction.lower()}")
    labels = {"BULL TREND": "trend is your friend", "BEAR TREND": "sellers in structural control",
              "CONSOLIDATION": "no real direction — fade the edges", "EXTENDED": "extended — don't chase"}
    if regime in labels:
        parts.append(labels[regime])
    if gex and not gex.get("error"):
        parts.append("below vol trigger — moves amplify" if not gex.get("above_vol_trigger") else "above vol trigger — expect pinning")
    if reserves_rrp.get("direction") == 1 and reserves_rrp.get("strength") == 1.0:
        parts.append("max bullish liquidity")
    elif reserves_rrp.get("direction") == -1 and reserves_rrp.get("strength") == 1.0:
        parts.append("max bearish liquidity")
    if entropy_status == "ELEVATED":
        parts.append("entropy elevated — half size")
    return ", ".join(parts).capitalize() + "."
