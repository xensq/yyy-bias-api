import json, os
from datetime import datetime

HISTORY_FILE = "/tmp/yyy_bias_history.json"

def _load():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        return json.load(open(HISTORY_FILE))
    except:
        return []

def _save(data):
    json.dump(data, open(HISTORY_FILE, "w"), indent=2)

def log_bias(bias: dict, topology: dict, entropy: dict, gex: dict) -> dict:
    entries = _load()
    now = datetime.now()
    entry = {
        "id": now.strftime("%Y%m%d_%H%M%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "direction": bias.get("direction"),
        "score": bias.get("score"),
        "conviction": bias.get("conviction"),
        "size_rule": bias.get("size_rule"),
        "narrative": bias.get("narrative"),
        "regime": topology.get("regime"),
        "pca1": round(topology.get("pca1", 0), 3),
        "pca2": round(topology.get("pca2", 0), 3),
        "vol_z": round(topology.get("vol_z", 0), 3),
        "entropy_status": entropy.get("status"),
        "entropy_rho": round(entropy.get("rho", 0), 3),
        "above_vol_trigger": gex.get("above_vol_trigger") if gex and not gex.get("error") else None,
        "positive_gamma": gex.get("positive_gamma") if gex and not gex.get("error") else None,
        "vol_trigger": gex.get("vol_trigger") if gex and not gex.get("error") else None,
        "outcome": None,
        "correct": None,
        "notes": "",
    }
    # Don't duplicate same day entry — update instead
    existing = next((e for e in entries if e["date"] == entry["date"]), None)
    if existing:
        existing.update({k: entry[k] for k in entry if k not in ["outcome", "correct", "notes"]})
    else:
        entries.insert(0, entry)
    _save(entries)
    return entry

def set_outcome(entry_id: str, outcome: str, notes: str = "") -> dict:
    entries = _load()
    for e in entries:
        if e["id"] == entry_id:
            e["outcome"] = outcome  # BULL, BEAR, FLAT
            direction = e.get("direction", "NEUTRAL")
            if outcome == "FLAT" or direction == "NEUTRAL":
                e["correct"] = None
            else:
                e["correct"] = (
                    (outcome == "BULL" and direction == "BULLISH") or
                    (outcome == "BEAR" and direction == "BEARISH")
                )
            e["notes"] = notes
            _save(entries)
            return e
    return {"error": "entry not found"}

def get_history() -> dict:
    entries = _load()
    graded = [e for e in entries if e.get("correct") is not None]
    wins = sum(1 for e in graded if e["correct"])
    total = len(graded)
    win_rate = round(wins / total * 100, 1) if total else 0

    # Win rate by regime
    regimes = {}
    for e in graded:
        r = e.get("regime", "UNKNOWN")
        if r not in regimes:
            regimes[r] = {"wins": 0, "total": 0}
        regimes[r]["total"] += 1
        if e["correct"]:
            regimes[r]["wins"] += 1
    regime_rates = {r: round(v["wins"]/v["total"]*100, 1) for r, v in regimes.items()}

    # Win rate by conviction tier
    tiers = {"high (70+)": {"wins":0,"total":0}, "mid (45-70)": {"wins":0,"total":0}, "low (<45)": {"wins":0,"total":0}}
    for e in graded:
        c = e.get("conviction", 0)
        t = "high (70+)" if c >= 70 else "mid (45-70)" if c >= 45 else "low (<45)"
        tiers[t]["total"] += 1
        if e["correct"]:
            tiers[t]["wins"] += 1
    tier_rates = {t: round(v["wins"]/v["total"]*100, 1) if v["total"] else 0 for t, v in tiers.items()}

    # Win rate by entropy
    entropy_rates = {}
    for e in graded:
        es = e.get("entropy_status", "NORMAL")
        if es not in entropy_rates:
            entropy_rates[es] = {"wins": 0, "total": 0}
        entropy_rates[es]["total"] += 1
        if e["correct"]:
            entropy_rates[es]["wins"] += 1
    entropy_win = {k: round(v["wins"]/v["total"]*100, 1) for k, v in entropy_rates.items()}

    return {
        "entries": entries,
        "stats": {
            "total_graded": total,
            "wins": wins,
            "win_rate": win_rate,
            "by_regime": regime_rates,
            "by_conviction": tier_rates,
            "by_entropy": entropy_win,
        }
    }
