import yfinance as yf
import numpy as np
from datetime import datetime
from engine.iv_surface import get_iv_surface

def get_expected_move(ticker: str = "SPX"):
    import math
    surface = get_iv_surface(ticker)
    if surface.get("error"):
        return {"error": surface["error"]}

    spot = surface["spot"]
    points = surface["points"]
    if not points:
        return {"error": "no options data"}

    # Get VIX
    try:
        vix = float(yf.Ticker("^VIX").fast_info["lastPrice"])
    except:
        vix = None

    # ATM IV buckets
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

    # VIX daily move
    vix_move_pts = round(spot * (vix / 100) * math.sqrt(1 / 252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None

    atm = [p["iv"] for p in points if abs(p["strike"] - spot) / spot < 0.02]
    atm_iv = round(float(np.median(atm)) * 100, 2) if atm else None

    return {
        "ticker": ticker,
        "spot": spot,
        "atm_iv": atm_iv,
        "vix": round(vix, 2) if vix else None,
        "vix_move_pts": vix_move_pts,
        "vix_upper": vix_upper,
        "vix_lower": vix_lower,
        "moves": {
            "1d": bucket_iv(1, 2),
            "1w": bucket_iv(3, 9),
            "1m": bucket_iv(10, 35),
        }
    }
