import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

# In-memory baseline — stores opening IV for the day
# First call sets the baseline, subsequent calls compute Net IV = current - baseline
_baseline: dict = {}
_baseline_date: str = ""


def _fetch_chains():
    spx = yf.Ticker("^SPX")
    hist = spx.history(period="2d", interval="5m")
    if hist.empty:
        return None, None
    spot = float(hist["Close"].iloc[-1])
    exps = spx.options[:14]  # pull up to 14 expirations
    rows = {}  # {strike: {exp: mid_iv}}
    for exp in exps:
        try:
            chain = spx.option_chain(exp)
            calls = chain.calls[["strike", "impliedVolatility", "openInterest"]].copy()
            puts  = chain.puts[["strike",  "impliedVolatility", "openInterest"]].copy()
            calls["iv"] = pd.to_numeric(calls["impliedVolatility"], errors="coerce")
            puts["iv"]  = pd.to_numeric(puts["impliedVolatility"],  errors="coerce")
            calls = calls[(calls["strike"] >= spot * 0.93) & (calls["strike"] <= spot * 1.07)]
            puts  = puts[ (puts["strike"]  >= spot * 0.93) & (puts["strike"]  <= spot * 1.07)]
            merged = pd.merge(
                calls[["strike", "iv", "openInterest"]].rename(columns={"iv": "call_iv", "openInterest": "call_oi"}),
                puts[["strike",  "iv", "openInterest"]].rename(columns={"iv": "put_iv",  "openInterest": "put_oi"}),
                on="strike", how="outer"
            )
            for _, row in merged.iterrows():
                s = float(row["strike"])
                call_iv = float(row["call_iv"]) if pd.notna(row["call_iv"]) else None
                put_iv  = float(row["put_iv"])  if pd.notna(row["put_iv"])  else None
                if call_iv is not None and put_iv is not None:
                    mid = (call_iv + put_iv) / 2
                elif call_iv is not None:
                    mid = call_iv
                elif put_iv is not None:
                    mid = put_iv
                else:
                    continue
                call_oi = float(row["call_oi"]) if pd.notna(row["call_oi"]) else 0
                put_oi  = float(row["put_oi"])  if pd.notna(row["put_oi"])  else 0
                # only include strikes with some open interest
                if call_oi + put_oi < 10:
                    continue
                if s not in rows:
                    rows[s] = {}
                rows[s][exp] = round(mid * 100, 3)  # as percentage
        except Exception:
            continue
    return spot, rows, exps


def get_iv_surface():
    global _baseline, _baseline_date
    try:
        result = _fetch_chains()
        if result is None or result[0] is None:
            return {"error": "could not fetch options data"}
        spot, current_ivs, exps = result
        today = datetime.now().strftime("%Y-%m-%d")
        # Reset baseline each new day
        if _baseline_date != today or not _baseline:
            _baseline = {s: dict(exps_dict) for s, exps_dict in current_ivs.items()}
            _baseline_date = today
        # Build Net IV table: current - baseline
        all_strikes = sorted(set(current_ivs.keys()) | set(_baseline.keys()), reverse=True)
        all_exps = list(exps)
        table = []
        for strike in all_strikes:
            row = {"strike": int(strike), "values": {}}
            for exp in all_exps:
                curr = current_ivs.get(strike, {}).get(exp)
                base = _baseline.get(strike, {}).get(exp)
                if curr is not None and base is not None:
                    net = round(curr - base, 2)
                    row["values"][exp] = net
                else:
                    row["values"][exp] = None
            table.append(row)
        return {
            "spot": round(spot, 2),
            "expirations": all_exps,
            "table": table,
            "baseline_time": _baseline_date,
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}
