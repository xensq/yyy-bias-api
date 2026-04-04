import yfinance as yf
import numpy as np
from datetime import datetime
from scipy.stats import norm

RF = 0.053

TICKER_MAP = {"SPX": "^SPX", "NDX": "^NDX", "SPY": "SPY", "QQQ": "QQQ"}

def _bs_delta(S, K, T, sigma, is_call=True):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    try:
        d1 = (np.log(S / K) + (RF + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return float(norm.cdf(d1)) if is_call else float(norm.cdf(d1) - 1)
    except Exception:
        return 0.0

def _bs_gamma(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    try:
        d1 = (np.log(S / K) + (RF + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return float(norm.pdf(d1) / (S * sigma * np.sqrt(T)))
    except Exception:
        return 0.0

def _bs_charm(S, K, T, sigma, is_call=True):
    """dDelta/dTime — how much delta changes per day"""
    if T <= 0 or sigma <= 0:
        return 0.0
    try:
        d1 = (np.log(S / K) + (RF + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        charm = -norm.pdf(d1) * (2 * RF * T - d2 * sigma * np.sqrt(T)) / (2 * T * sigma * np.sqrt(T))
        return float(charm) if is_call else float(-charm)
    except Exception:
        return 0.0

def _bs_vanna(S, K, T, sigma):
    """dDelta/dVol — how much delta changes per vol unit"""
    if T <= 0 or sigma <= 0:
        return 0.0
    try:
        d1 = (np.log(S / K) + (RF + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return float(-norm.pdf(d1) * d2 / sigma)
    except Exception:
        return 0.0

def get_zero_dte(ticker="SPX"):
    try:
        sym = TICKER_MAP.get(ticker.upper(), "^SPX")
        t = yf.Ticker(sym)
        hist = t.history(period="2d", interval="5m")
        if hist.empty:
            return {"error": "no price data"}
        spot = float(hist["Close"].iloc[-1])
        exps = t.options
        if not exps:
            return {"error": "no options data"}

        today_str = datetime.now().strftime("%Y-%m-%d")
        # Use today or nearest expiry
        target_exp = exps[0]
        today = datetime.now()

        try:
            chain = t.option_chain(target_exp)
        except Exception as e:
            return {"error": f"chain fetch failed: {e}"}

        dte_days = max((datetime.strptime(target_exp, "%Y-%m-%d") - today).days, 0)
        T = max(dte_days, 1/1440) / 365.0
        T_hours = max(dte_days * 24, 0.5)  # hours to expiry

        calls = chain.calls.copy()
        puts = chain.puts.copy()

        # ATM IV for expected move
        atm_calls = calls[abs(calls["strike"] - spot) / spot < 0.02]
        atm_puts = puts[abs(puts["strike"] - spot) / spot < 0.02]
        atm_iv_vals = []
        for _, row in atm_calls.iterrows():
            iv = float(row.get("impliedVolatility", 0) or 0)
            if 0 < iv < 3:
                atm_iv_vals.append(iv)
        for _, row in atm_puts.iterrows():
            iv = float(row.get("impliedVolatility", 0) or 0)
            if 0 < iv < 3:
                atm_iv_vals.append(iv)

        atm_iv = float(np.median(atm_iv_vals)) if atm_iv_vals else 0.20
        T_frac = T_hours / (252 * 6.5)  # fraction of trading year
        expected_move_1s = round(spot * atm_iv * np.sqrt(T_frac), 2)
        expected_move_2s = round(expected_move_1s * 2, 2)

        # Per-strike analysis
        strike_rows = []
        total_call_oi = 0
        total_put_oi = 0
        charm_sum = 0.0
        vanna_sum = 0.0

        atm_range = spot * 0.03  # ±3% strikes only

        for _, row in calls.iterrows():
            K = float(row["strike"])
            if abs(K - spot) > atm_range:
                continue
            iv = float(row.get("impliedVolatility", 0) or 0)
            oi = float(row.get("openInterest", 0) or 0)
            if iv <= 0 or iv > 3 or oi < 1:
                continue
            g = _bs_gamma(spot, K, T, iv)
            gex = g * oi * spot * spot * 0.01 / 1e9
            charm = _bs_charm(spot, K, T, iv, True) * oi * 100
            vanna = _bs_vanna(spot, K, T, iv) * oi * 100
            strike_rows.append({"strike": K, "side": "call", "oi": oi, "iv": round(iv, 4), "gex": round(gex, 4), "charm": round(charm, 2), "vanna": round(vanna, 2)})
            total_call_oi += oi
            charm_sum += charm
            vanna_sum += vanna

        for _, row in puts.iterrows():
            K = float(row["strike"])
            if abs(K - spot) > atm_range:
                continue
            iv = float(row.get("impliedVolatility", 0) or 0)
            oi = float(row.get("openInterest", 0) or 0)
            if iv <= 0 or iv > 3 or oi < 1:
                continue
            g = _bs_gamma(spot, K, T, iv)
            gex = -g * oi * spot * spot * 0.01 / 1e9
            charm = _bs_charm(spot, K, T, iv, False) * oi * 100
            vanna = _bs_vanna(spot, K, T, iv) * oi * 100
            strike_rows.append({"strike": K, "side": "put", "oi": oi, "iv": round(iv, 4), "gex": round(gex, 4), "charm": round(charm, 2), "vanna": round(vanna, 2)})
            total_put_oi += oi
            charm_sum += charm
            vanna_sum += vanna

        # Key levels
        call_strikes = [r for r in strike_rows if r["side"] == "call"]
        put_strikes = [r for r in strike_rows if r["side"] == "put"]

        gamma_wall_call = max(call_strikes, key=lambda x: x["gex"], default={"strike": spot})["strike"] if call_strikes else spot
        gamma_wall_put = min(put_strikes, key=lambda x: x["gex"], default={"strike": spot})["strike"] if put_strikes else spot

        # Intraday gamma flip
        net_by_strike = {}
        for r in strike_rows:
            s = r["strike"]
            net_by_strike[s] = net_by_strike.get(s, 0) + r["gex"]

        sorted_strikes = sorted(net_by_strike.keys())
        cum = 0.0
        gamma_flip = spot
        for s in sorted_strikes:
            prev = cum
            cum += net_by_strike[s]
            if prev < 0 <= cum or prev > 0 >= cum:
                gamma_flip = s
                break

        # PC ratio
        pc_ratio = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0
        pc_sentiment = "bearish" if pc_ratio > 1.2 else "bullish" if pc_ratio < 0.8 else "neutral"

        # Charm/vanna direction
        charm_direction = "bullish" if charm_sum > 0 else "bearish"
        vanna_direction = "bullish" if vanna_sum > 0 else "bearish"

        charm_note = (
            "dealers buying into close (positive charm)" if charm_sum > 0
            else "dealers selling into close (negative charm)"
        )
        vanna_note = (
            "vol drop helps bulls — vanna flow bullish" if vanna_sum > 0
            else "vol spike hurts bulls — vanna flow bearish"
        )

        return {
            "spot": round(spot, 2),
            "expiry": target_exp,
            "dte_hours": round(T_hours, 1),
            "atm_iv": round(atm_iv * 100, 2),
            "expected_move_1s": expected_move_1s,
            "expected_move_2s": expected_move_2s,
            "range_1s_low": round(spot - expected_move_1s, 2),
            "range_1s_high": round(spot + expected_move_1s, 2),
            "range_2s_low": round(spot - expected_move_2s, 2),
            "range_2s_high": round(spot + expected_move_2s, 2),
            "pc_ratio": pc_ratio,
            "pc_sentiment": pc_sentiment,
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "gamma_wall_call": round(gamma_wall_call, 0),
            "gamma_wall_put": round(gamma_wall_put, 0),
            "gamma_flip": round(gamma_flip, 0),
            "charm_sum": round(charm_sum, 0),
            "vanna_sum": round(vanna_sum, 0),
            "charm_direction": charm_direction,
            "vanna_direction": vanna_direction,
            "charm_note": charm_note,
            "vanna_note": vanna_note,
            "strike_data": strike_rows,
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}
