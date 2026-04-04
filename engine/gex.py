import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm
from datetime import datetime

RF = 0.053

def gamma(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    try:
        d1 = (np.log(S / K) + (RF + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return float(norm.pdf(d1) / (S * sigma * np.sqrt(T)))
    except Exception:
        return 0.0

def dte(exp_str):
    try:
        return max((datetime.strptime(exp_str, "%Y-%m-%d") - datetime.now()).days, 0)
    except Exception:
        return 0

def calculate_gex(n_exp=3):
    try:
        spx = yf.Ticker("^SPX")
        hist = spx.history(period="2d", interval="5m")
        if hist.empty:
            return {"error": "no price data"}
        spot = float(hist["Close"].iloc[-1])
        exps = spx.options[:n_exp]
        if not exps:
            return {"error": "no options data"}
        calls_list, puts_list = [], []
        for exp in exps:
            try:
                T = max(dte(exp), 1/1440) / 365.0
                chain = spx.option_chain(exp)
                for side, lst in [(chain.calls, calls_list), (chain.puts, puts_list)]:
                    df = side[["strike", "impliedVolatility", "openInterest"]].copy()
                    df["T"] = T
                    df["impliedVolatility"] = pd.to_numeric(df["impliedVolatility"], errors="coerce").fillna(0.2)
                    df["openInterest"] = pd.to_numeric(df["openInterest"], errors="coerce").fillna(0)
                    lst.append(df)
            except Exception:
                continue
        if not calls_list:
            return {"error": "could not load chains"}
        calls = pd.concat(calls_list, ignore_index=True)
        puts = pd.concat(puts_list, ignore_index=True)
        lo, hi = spot * 0.92, spot * 1.08
        calls = calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)].copy()
        puts = puts[(puts["strike"] >= lo) & (puts["strike"] <= hi)].copy()
        scale = spot**2 * 0.01 * 100
        calls["gex"] = calls.apply(lambda r: gamma(spot, r["strike"], r["T"], r["impliedVolatility"]) * r["openInterest"] * scale, axis=1)
        puts["gex"] = puts.apply(lambda r: -gamma(spot, r["strike"], r["T"], r["impliedVolatility"]) * r["openInterest"] * scale, axis=1)
        ca = calls.groupby("strike").agg(gex=("gex", "sum"), oi=("openInterest", "sum")).reset_index()
        pa = puts.groupby("strike").agg(gex=("gex", "sum"), oi=("openInterest", "sum")).reset_index()
        gdf = pd.merge(
            ca.rename(columns={"gex": "cgex", "oi": "coi"}),
            pa.rename(columns={"gex": "pgex", "oi": "poi"}),
            on="strike", how="outer").fillna(0).sort_values("strike").reset_index(drop=True)
        gdf["net"] = gdf["cgex"] + gdf["pgex"]
        gdf["cum"] = gdf["net"].cumsum()
        prev = np.sign(gdf["cum"].shift(1, fill_value=gdf["cum"].iloc[0]))
        curr = np.sign(gdf["cum"])
        cross = gdf[(prev != curr) & (curr != 0)]
        vol_trigger = float(cross.iloc[0]["strike"]) if len(cross) else spot
        call_wall = float(ca.loc[ca["oi"].idxmax(), "strike"]) if len(ca) else spot
        put_wall = float(pa.loc[pa["oi"].idxmax(), "strike"]) if len(pa) else spot
        strikes = sorted(set(ca["strike"].tolist()) | set(pa["strike"].tolist()))
        pain = []
        for s in strikes:
            cp = float(((s - ca[ca["strike"] < s]["strike"]) * ca[ca["strike"] < s]["oi"]).sum())
            pp = float(((pa[pa["strike"] > s]["strike"] - s) * pa[pa["strike"] > s]["oi"]).sum())
            pain.append(cp + pp)
        max_pain = float(strikes[int(np.argmin(pain))]) if pain else spot
        net_total = float(gdf["net"].sum())
        above = bool(float(spot) > float(vol_trigger))
        pos = bool(float(net_total) > 0)

        # Per-strike data for butterfly chart
        all_strikes = sorted(set(ca["strike"].tolist()) | set(pa["strike"].tolist()))
        strike_data = []
        for s in all_strikes:
            call_g = float(ca[ca["strike"] == s]["gex"].sum()) if s in ca["strike"].values else 0.0
            put_g  = float(pa[pa["strike"] == s]["gex"].sum()) if s in pa["strike"].values else 0.0
            call_o = float(ca[ca["strike"] == s]["oi"].sum()) if s in ca["strike"].values else 0.0
            put_o  = float(pa[pa["strike"] == s]["oi"].sum()) if s in pa["strike"].values else 0.0
            strike_data.append({
                "strike": round(float(s), 0),
                "call_gex": round(float(call_g) / 1e9, 4),
                "put_gex": round(float(put_g) / 1e9, 4),
                "call_oi": round(float(call_o), 0),
                "put_oi": round(float(put_o), 0),
            })

        return {
            "spot": round(float(spot), 2),
            "vol_trigger": round(float(vol_trigger), 0),
            "call_wall": round(float(call_wall), 0),
            "put_wall": round(float(put_wall), 0),
            "max_pain": round(float(max_pain), 0),
            "net_gex_bn": round(float(net_total) / 1e9, 3),
            "above_vol_trigger": above,
            "positive_gamma": pos,
            "gamma_env": "POSITIVE" if pos else "NEGATIVE",
            "pain_pts": round(float(max_pain - spot), 0),
            "strike_data": strike_data,
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "spot": 0, "vol_trigger": 0, "call_wall": 0,
                "put_wall": 0, "max_pain": 0, "net_gex_bn": 0,
                "above_vol_trigger": False, "positive_gamma": False,
                "gamma_env": "UNKNOWN", "pain_pts": 0, "strike_data": []}
