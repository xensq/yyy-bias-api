import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from engine.iv import get_iv_surface

STORE = Path(os.environ.get("DATA_DIR", "/tmp")) / "net_iv_history.json"

def _load() -> dict:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text())
        except Exception:
            pass
    return {}

def _save(data: dict):
    STORE.write_text(json.dumps(data))

def snapshot_iv(ticker: str = "SPX"):
    raw = get_iv_surface(ticker)
    if raw.get("error") or not raw.get("points"):
        return {"error": raw.get("error", "no data")}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    store = _load()
    if ticker not in store:
        store[ticker] = {}
    by_strike = {}
    for p in raw["points"]:
        strike = str(int(p["strike"]))
        if strike not in by_strike:
            by_strike[strike] = []
        by_strike[strike].append(p["iv"])
    store[ticker][today] = {
        strike: round(sum(ivs) / len(ivs), 4)
        for strike, ivs in by_strike.items() if ivs
    }
    _save(store)
    return {"ok": True, "date": today, "strikes": len(store[ticker][today])}

def get_net_iv(ticker: str = "SPX"):
    store = _load()
    ticker_data = store.get(ticker, {})
    if len(ticker_data) < 2:
        snapshot_iv(ticker)
        ticker_data = _load().get(ticker, {})
        if len(ticker_data) < 2:
            return {"dates": [], "rows": [], "spot": 0, "status": "building_history"}
    dates = sorted(ticker_data.keys())[-10:]
    all_strikes = set()
    for d in dates:
        all_strikes.update(int(s) for s in ticker_data[d].keys())
    raw = get_iv_surface(ticker)
    spot = raw.get("spot", 0)
    atm_strikes = sorted(
        s for s in all_strikes
        if spot == 0 or abs(s / spot - 1.0) <= 0.05
    )
    rows = []
    for strike in atm_strikes:
        row = {"strike": strike, "values": {}}
        prev_iv = None
        for date in dates:
            iv = ticker_data[date].get(str(strike))
            if iv is not None and prev_iv is not None:
                row["values"][date] = {"iv": iv, "change": round(iv - prev_iv, 4)}
            elif iv is not None:
                row["values"][date] = {"iv": iv, "change": None}
            else:
                row["values"][date] = None
            if iv is not None:
                prev_iv = iv
        rows.append(row)
    return {"dates": dates, "rows": rows, "spot": spot, "status": "ok"}
