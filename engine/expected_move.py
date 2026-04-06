import yfinance as yf
import numpy as np
from datetime import datetime
from engine.iv_surface import get_iv_surface

def get_expected_move(ticker="SPX"):
    try:
        surface = get_iv_surface(ticker)
        if surface.get("error"):
            vix_move_pts = round(spot * (vix / 100) * _math.sqrt(1/252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None
    return {"error": surface["error"]}
        spot = surface["spot"]
        points = surface["points"]
        if not points:
            vix_move_pts = round(spot * (vix / 100) * _math.sqrt(1/252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None
    return {"error": "no options data"}
        buckets = {"1d": [], "1w": [], "1m": []}
        for p in points:
            dte = p["dte"]
            mon = p["moneyness"]
            iv = p["iv"]
            if abs(mon - 1.0) > 0.03:
                continue
            if dte <= 2:
                buckets["1d"].append(iv)
            elif dte <= 9:
                buckets["1w"].append(iv)
            elif dte <= 35:
                buckets["1m"].append(iv)
        def sigma(ivs, days):
            if not ivs:
                return None
            atm = float(np.median(ivs))
            move = spot * atm * np.sqrt(days / 252)
            vix_move_pts = round(spot * (vix / 100) * _math.sqrt(1/252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None
    return {"iv": round(atm * 100, 2), "move_pts": round(move, 2), "move_pct": round(atm * np.sqrt(days / 252) * 100, 2), "upper": round(spot + move, 2), "lower": round(spot - move, 2)}
        moves = {"1d": sigma(buckets["1d"], 1), "1w": sigma(buckets["1w"], 5), "1m": sigma(buckets["1m"], 21)}
        atm_iv = surface.get("atm_iv", 0)
        for label, days in [("1d", 1), ("1w", 5), ("1m", 21)]:
            if moves[label] is None and atm_iv > 0:
                move = spot * atm_iv * np.sqrt(days / 252)
                moves[label] = {"iv": round(atm_iv * 100, 2), "move_pts": round(move, 2), "move_pct": round(atm_iv * np.sqrt(days / 252) * 100, 2), "upper": round(spot + move, 2), "lower": round(spot - move, 2)}
        vix_move_pts = round(spot * (vix / 100) * _math.sqrt(1/252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None
    return {"ticker": ticker, "spot": spot, "atm_iv": round(atm_iv * 100, 2), "moves": moves, "error": None}
    except Exception as e:
        vix_move_pts = round(spot * (vix / 100) * _math.sqrt(1/252), 2) if vix else None
    vix_upper = round(spot + vix_move_pts, 2) if vix_move_pts else None
    vix_lower = round(spot - vix_move_pts, 2) if vix_move_pts else None
    return {"error": str(e)}
