import yfinance as yf
import numpy as np
from datetime import datetime
from engine.iv_surface import get_iv_surface

TICKER_MAP = {"SPX": "^GSPC", "NDX": "^NDX", "SPY": "SPY", "QQQ": "QQQ"}

def get_expected_move(ticker: str = "SPX"):
    import math
    surface = get_iv_surface(ticker)
    if surface.get("error"):
        return {"error": surface["error"]}

    spot = surface["spot"]
    points = surface["points"]
    if not points:
        return {"error": "no options data"}

    # VIX
    try:
        vix = float(yf.Ticker("^VIX").fast_info["lastPrice"])
    except:
        vix = None

    # IV percentile from 1y history
    try:
        yf_sym = TICKER_MAP.get(ticker, ticker)
        hist = yf.Ticker(yf_sym).history(period="1y")
        if len(hist) > 20:
            returns = hist["Close"].pct_change().dropna()
            realized_vols = returns.rolling(20).std() * math.sqrt(252) * 100
            realized_vols = realized_vols.dropna()
            atm_iv_raw = [p["iv"] for p in points if abs(p["strike"] - spot) / spot < 0.02]
            current_iv = float(np.median(atm_iv_raw)) * 100 if atm_iv_raw else None
            if current_iv:
                iv_percentile = round(float((realized_vols < current_iv).mean()) * 100, 1)
            else:
                iv_percentile = None
        else:
            iv_percentile = None
    except:
        iv_percentile = None

    def bucket_iv(min_dte, max_dte):
        bucket = [p["iv"] for p in points if min_dte <= p["dte"] <= max_dte and abs(p["strike"] - spot) / spot < 0.03]
        if not bucket:
            return None
        iv = float(np.median(bucket))
        days = (min_dte + max_dte) / 2
        move_pct = round(iv * math.sqrt(days / 252) * 100, 2)
        move_pts = round(spot * iv * math.sqrt(days / 252), 2)
        return {"iv": round(iv * 100, 2), "move_pct": move_pct, "move_pts": move_pts,
                "upper": round(spot + move_pts, 2), "lower": round(spot - move_pts, 2)}

    vix_move_pts = round(spot * (vix / 100) * math.sqrt(1 / 252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None

    atm = [p["iv"] for p in points if abs(p["strike"] - spot) / spot < 0.02]
    atm_iv = round(float(np.median(atm)) * 100, 2) if atm else None

    m1d = bucket_iv(1, 2)
    m1w = bucket_iv(3, 9)
    m1m = bucket_iv(10, 35)

    # Radar scores (0-1)
    iv_score = min((atm_iv or 0) / 60, 1.0)
    vix_score = min((vix or 0) / 40, 1.0)
    move_score = min((m1d["move_pct"] if m1d else 0) / 3.0, 1.0)
    confidence = 1.0 - min(abs((m1d["move_pts"] if m1d else 0) - (vix_move_pts or 0)) / max(m1d["move_pts"] if m1d else 1, 1), 1.0) if vix_move_pts and m1d else 0.5
    expansion_dw = min((m1w["move_pct"] / m1d["move_pct"]) / 3.0, 1.0) if m1d and m1w and m1d["move_pct"] > 0 else 0.5
    expansion_wm = min((m1m["move_pct"] / m1w["move_pct"]) / 3.0, 1.0) if m1w and m1m and m1w["move_pct"] > 0 else 0.5

    return {
        "ticker": ticker,
        "spot": spot,
        "atm_iv": atm_iv,
        "iv_percentile": iv_percentile,
        "vix": round(vix, 2) if vix else None,
        "vix_move_pts": vix_move_pts,
        "vix_upper": vix_upper,
        "vix_lower": vix_lower,
        "moves": {"1d": m1d, "1w": m1w, "1m": m1m},
        "radar": {
            "iv_level": round(iv_score, 3),
            "vix_level": round(vix_score, 3),
            "move_size": round(move_score, 3),
            "confidence": round(confidence, 3),
            "expansion_dw": round(expansion_dw, 3),
            "expansion_wm": round(expansion_wm, 3),
        }
    }
