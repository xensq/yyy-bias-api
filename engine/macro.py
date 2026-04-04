import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

def fred(series_id, n=20):
    try:
        r = requests.get(FRED.format(series_id), timeout=15)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("date").tail(n)
    except Exception:
        return pd.DataFrame(columns=["date", "value"])

def get_walcl():
    df = fred("WALCL", 12)
    if len(df) < 4:
        return {"direction": 0, "note": "unavailable", "value": None, "change_pct": 0}
    current = float(df["value"].iloc[-1])
    avg = float(df["value"].iloc[-5:-1].mean()) if len(df) >= 5 else float(df["value"].iloc[0])
    chg = (current - avg) / avg * 100
    if chg > 0.15:
        return {"direction": 1, "note": f"Fed expanding (+{chg:.2f}% vs 4wk avg)", "value": round(current / 1e3, 1), "change_pct": round(chg, 2)}
    elif chg < -0.15:
        return {"direction": -1, "note": f"Fed draining ({chg:.2f}% vs 4wk avg)", "value": round(current / 1e3, 1), "change_pct": round(chg, 2)}
    return {"direction": 0, "note": f"Fed balance sheet flat ({chg:+.2f}%)", "value": round(current / 1e3, 1), "change_pct": round(chg, 2)}

def get_reserves_rrp():
    res = fred("WRESBAL", 4)
    rrp = fred("RRPONTSYD", 4)
    if len(res) < 2 or len(rrp) < 2:
        return {"direction": 0, "strength": 0, "note": "unavailable", "res_chg": 0, "rrp_chg": 0}
    res_up = float(res["value"].iloc[-1]) > float(res["value"].iloc[-2])
    rrp_up = float(rrp["value"].iloc[-1]) > float(rrp["value"].iloc[-2])
    res_chg = round(float(res["value"].iloc[-1]) - float(res["value"].iloc[-2]), 1)
    rrp_chg = round(float(rrp["value"].iloc[-1]) - float(rrp["value"].iloc[-2]), 1)
    if res_up and not rrp_up:
        return {"direction": 1, "strength": 1.0, "note": "Reserves ↑ RRP ↓ — max bullish", "res_chg": res_chg, "rrp_chg": rrp_chg}
    if not res_up and rrp_up:
        return {"direction": -1, "strength": 1.0, "note": "Reserves ↓ RRP ↑ — max bearish", "res_chg": res_chg, "rrp_chg": rrp_chg}
    if res_up and rrp_up:
        return {"direction": 1, "strength": 0.5, "note": "Reserves ↑ RRP ↑ — mixed bullish", "res_chg": res_chg, "rrp_chg": rrp_chg}
    return {"direction": -1, "strength": 0.5, "note": "Reserves ↓ RRP ↓ — mixed bearish", "res_chg": res_chg, "rrp_chg": rrp_chg}

def get_oas():
    df = fred("BAMLH0A0HYM2", 10)
    if len(df) < 2:
        return {"direction": 0, "note": "unavailable", "value": None, "stress": "UNKNOWN", "wk_change": 0}
    current = float(df["value"].iloc[-1])
    prior = float(df["value"].iloc[-2])
    wk_ago = float(df["value"].iloc[-6]) if len(df) >= 6 else prior
    rising = current > prior
    wk_chg = round(current - wk_ago, 3)
    if current < 3.0:
        d, stress = 1, "HEALTHY"
        note = f"OAS {current:.2f}% — no stress"
    elif current < 4.0:
        d, stress = 0, "MILD CONCERN"
        note = f"OAS {current:.2f}% — mild concern"
    elif current < 5.0:
        d, stress = -1, "ELEVATED"
        note = f"OAS {current:.2f}% — elevated stress"
    else:
        d, stress = -1, "CRISIS"
        note = f"OAS {current:.2f}% — crisis mode"
    d = max(d - 1, -1) if rising else min(d + 1, 1)
    note += f" ({'↑' if rising else '↓'} {abs(wk_chg):.2f}% on week)"
    return {"direction": d, "note": note, "value": current, "stress": stress, "wk_change": wk_chg}

def get_auctions(days=5):
    try:
        r = requests.get("https://www.treasurydirect.gov/TA_WS/securities/upcoming", timeout=12)
        r.raise_for_status()
        data = r.json()
        today = datetime.now()
        cutoff = today + timedelta(days=days)
        found = []
        for item in data:
            term = item.get("term", "") or ""
            date_str = item.get("auctionDate", "") or ""
            if not any(t in term for t in ["10-Year", "20-Year", "30-Year"]):
                continue
            try:
                d = datetime.strptime(date_str[:10], "%Y-%m-%d")
                if today <= d <= cutoff:
                    found.append(f"{term} — {d.strftime('%a %b %d')}")
            except Exception:
                continue
        if found:
            return {"warning": True, "note": ", ".join(found) + " — size down", "auctions": found}
        return {"warning": False, "note": "no major auctions this week", "auctions": []}
    except Exception as e:
        return {"warning": False, "note": f"calendar unavailable", "auctions": []}
