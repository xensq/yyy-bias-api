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

def get_dealer_delta(ticker="SPX"):
    try:
        sym = TICKER_MAP.get(ticker.upper(), "^SPX")
        t = yf.Ticker(sym)
        hist = t.history(period="5d")
        if hist.empty:
            return {"error": "no price data"}
        spot = float(hist["Close"].iloc[-1])
        exps = t.options
        if not exps:
            return {"error": "no options data"}

        today = datetime.now()
        all_strikes = {}  # strike -> net dealer delta

        total_call_delta = 0.0
        total_put_delta = 0.0
        strike_details = []

        for exp in exps[:2]:
            try:
                dte = max((datetime.strptime(exp, "%Y-%m-%d") - today).days, 0)
                T = max(dte, 1/1440) / 365.0
                chain = t.option_chain(exp)

                for _, row in chain.calls.iterrows():
                    K = float(row["strike"])
                    if abs(K / spot - 1) > 0.05:
                        continue
                    iv = float(row.get("impliedVolatility", 0) or 0)
                    oi = float(row.get("openInterest", 0) or 0)
                    if iv <= 0 or iv > 3 or oi < 1:
                        continue
                    # Dealers are SHORT calls to market makers → negative delta exposure
                    delta = _bs_delta(spot, K, T, iv, True)
                    dealer_delta = -delta * oi * 100  # dealer is short
                    all_strikes[K] = all_strikes.get(K, 0) + dealer_delta
                    total_call_delta += dealer_delta

                for _, row in chain.puts.iterrows():
                    K = float(row["strike"])
                    if abs(K / spot - 1) > 0.05:
                        continue
                    iv = float(row.get("impliedVolatility", 0) or 0)
                    oi = float(row.get("openInterest", 0) or 0)
                    if iv <= 0 or iv > 3 or oi < 1:
                        continue
                    # Dealers are SHORT puts → positive delta exposure
                    delta = _bs_delta(spot, K, T, iv, False)
                    dealer_delta = -delta * oi * 100  # dealer is short put = positive delta
                    all_strikes[K] = all_strikes.get(K, 0) + dealer_delta
                    total_put_delta += dealer_delta

            except Exception:
                continue

        if not all_strikes:
            return {"error": "no strike data in range"}

        # Build sorted strike list
        sorted_k = sorted(all_strikes.keys())
        net_deltas = [all_strikes[k] for k in sorted_k]
        cum_deltas = list(np.cumsum(net_deltas))

        # Delta flip — where cumulative dealer delta crosses zero
        delta_flip = spot
        for i in range(1, len(sorted_k)):
            if (cum_deltas[i-1] < 0 <= cum_deltas[i]) or (cum_deltas[i-1] > 0 >= cum_deltas[i]):
                delta_flip = sorted_k[i]
                break

        # Net dealer delta
        net_total = sum(net_deltas)
        dealer_lean = "long" if net_total > 0 else "short"

        # Pressure at price moves — how much dealers buy/sell if price moves 1/2/3%
        def pressure_at_move(pct):
            new_spot = spot * (1 + pct / 100)
            new_deltas = {}
            for exp in exps[:2]:
                try:
                    dte = max((datetime.strptime(exp, "%Y-%m-%d") - today).days, 0)
                    T = max(dte, 1/1440) / 365.0
                    chain = t.option_chain(exp)
                    for _, row in chain.calls.iterrows():
                        K = float(row["strike"])
                        if abs(K / spot - 1) > 0.05:
                            continue
                        iv = float(row.get("impliedVolatility", 0) or 0)
                        oi = float(row.get("openInterest", 0) or 0)
                        if iv <= 0 or iv > 3 or oi < 1:
                            continue
                        d_new = _bs_delta(new_spot, K, T, iv, True)
                        d_old = _bs_delta(spot, K, T, iv, True)
                        new_deltas[K] = new_deltas.get(K, 0) + (-(d_new - d_old) * oi * 100)
                    for _, row in chain.puts.iterrows():
                        K = float(row["strike"])
                        if abs(K / spot - 1) > 0.05:
                            continue
                        iv = float(row.get("impliedVolatility", 0) or 0)
                        oi = float(row.get("openInterest", 0) or 0)
                        if iv <= 0 or iv > 3 or oi < 1:
                            continue
                        d_new = _bs_delta(new_spot, K, T, iv, False)
                        d_old = _bs_delta(spot, K, T, iv, False)
                        new_deltas[K] = new_deltas.get(K, 0) + (-(d_new - d_old) * oi * 100)
                except Exception:
                    continue
            return round(sum(new_deltas.values()), 0)

        hedge_up1 = pressure_at_move(1)
        hedge_up2 = pressure_at_move(2)
        hedge_dn1 = pressure_at_move(-1)
        hedge_dn2 = pressure_at_move(-2)

        # Strike detail for chart
        for k in sorted_k:
            if abs(k / spot - 1) <= 0.03:
                strike_details.append({
                    "strike": round(k, 0),
                    "net_delta": round(all_strikes[k], 0),
                    "above_spot": k > spot
                })

        return {
            "spot": round(spot, 2),
            "net_dealer_delta": round(net_total, 0),
            "dealer_lean": dealer_lean,
            "delta_flip": round(delta_flip, 0),
            "above_delta_flip": bool(spot > delta_flip),
            "hedge_up_1pct": hedge_up1,
            "hedge_up_2pct": hedge_up2,
            "hedge_dn_1pct": hedge_dn1,
            "hedge_dn_2pct": hedge_dn2,
            "strike_data": strike_details,
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}
