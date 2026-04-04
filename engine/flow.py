import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

TICKER_MAP = {"SPX": "^SPX", "NDX": "^NDX", "SPY": "SPY", "QQQ": "QQQ"}

def get_flow(ticker="SPX"):
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

        today = datetime.now()

        # ── 1. IV SKEW across strikes ─────────────────────────────────────────
        # Use nearest 2 expirations for skew
        skew_data = []
        atm_iv_by_exp = {}

        for exp in exps[:3]:
            try:
                dte = max((datetime.strptime(exp, "%Y-%m-%d") - today).days, 0)
                if dte > 45:
                    continue
                chain = t.option_chain(exp)
                calls = chain.calls
                puts = chain.puts

                # Build skew: put IV - call IV by moneyness
                for moneyness in [0.92, 0.94, 0.96, 0.97, 0.98, 0.99, 1.00, 1.01, 1.02, 1.03, 1.04, 1.06, 1.08]:
                    target = spot * moneyness
                    c_row = calls.iloc[(calls["strike"] - target).abs().argsort()[:1]]
                    p_row = puts.iloc[(puts["strike"] - target).abs().argsort()[:1]]
                    if c_row.empty or p_row.empty:
                        continue
                    c_iv = float(c_row["impliedVolatility"].values[0] or 0)
                    p_iv = float(p_row["impliedVolatility"].values[0] or 0)
                    strike = float(c_row["strike"].values[0])
                    if c_iv <= 0 or p_iv <= 0 or c_iv > 3 or p_iv > 3:
                        continue
                    if abs(moneyness - 1.0) < 0.005:
                        atm_iv_by_exp[dte] = round((c_iv + p_iv) / 2 * 100, 2)
                    skew_data.append({
                        "dte": dte, "expiry": exp,
                        "moneyness": round(moneyness, 2),
                        "strike": round(strike, 0),
                        "call_iv": round(c_iv * 100, 2),
                        "put_iv": round(p_iv * 100, 2),
                        "skew": round((p_iv - c_iv) * 100, 3),
                    })
            except Exception:
                continue

        # Skew regime
        atm_skew_pts = [d for d in skew_data if abs(d["moneyness"] - 1.0) < 0.015]
        avg_skew = float(np.mean([d["skew"] for d in atm_skew_pts])) if atm_skew_pts else 0
        put_25d = [d for d in skew_data if abs(d["moneyness"] - 0.97) < 0.015]
        call_25d = [d for d in skew_data if abs(d["moneyness"] - 1.03) < 0.015]
        avg_put_skew = float(np.mean([d["skew"] for d in put_25d])) if put_25d else 0
        avg_call_skew = float(np.mean([d["skew"] for d in call_25d])) if call_25d else 0

        if avg_skew > 3:
            skew_regime = "FEAR"
            skew_note = "put skew elevated — institutional hedging active, downside tail is being priced"
        elif avg_skew > 1.5:
            skew_regime = "CAUTION"
            skew_note = "mild put premium — some defensive positioning but not panic"
        elif avg_skew < 0:
            skew_regime = "GREED"
            skew_note = "calls bid over puts — unusual, upside demand dominant, watch for squeeze"
        else:
            skew_regime = "NEUTRAL"
            skew_note = "skew balanced — no strong directional lean from options market"

        # ── 2. OPTIONS SENTIMENT — IV change by strike ────────────────────────
        sentiment_data = []
        try:
            exp = exps[0]
            chain = t.option_chain(exp)
            calls = chain.calls
            puts = chain.puts

            # ATM range ±4%
            for _, row in calls.iterrows():
                K = float(row["strike"])
                if abs(K / spot - 1) > 0.04:
                    continue
                iv = float(row.get("impliedVolatility", 0) or 0)
                vol = float(row.get("volume", 0) or 0)
                oi = float(row.get("openInterest", 0) or 0)
                if iv <= 0 or iv > 3:
                    continue
                # IV vs 30-day mean approximation: use put-call parity proxy
                # positive = IV bid up = buying pressure
                iv_zscore = (iv - 0.18) / 0.06  # rough normalization
                sentiment_data.append({
                    "strike": round(K, 0),
                    "side": "call",
                    "iv": round(iv * 100, 2),
                    "volume": int(vol),
                    "oi": int(oi),
                    "iv_zscore": round(float(iv_zscore), 2),
                    "above_spot": K > spot
                })

            for _, row in puts.iterrows():
                K = float(row["strike"])
                if abs(K / spot - 1) > 0.04:
                    continue
                iv = float(row.get("impliedVolatility", 0) or 0)
                vol = float(row.get("volume", 0) or 0)
                oi = float(row.get("openInterest", 0) or 0)
                if iv <= 0 or iv > 3:
                    continue
                iv_zscore = (iv - 0.20) / 0.07
                sentiment_data.append({
                    "strike": round(K, 0),
                    "side": "put",
                    "iv": round(iv * 100, 2),
                    "volume": int(vol),
                    "oi": int(oi),
                    "iv_zscore": round(float(iv_zscore), 2),
                    "above_spot": K > spot
                })
        except Exception:
            pass

        # Overall sentiment score
        call_ivs = [d["iv"] for d in sentiment_data if d["side"] == "call"]
        put_ivs = [d["iv"] for d in sentiment_data if d["side"] == "put"]
        avg_call_iv = float(np.mean(call_ivs)) if call_ivs else 0
        avg_put_iv = float(np.mean(put_ivs)) if put_ivs else 0
        iv_ratio = avg_put_iv / avg_call_iv if avg_call_iv > 0 else 1.0

        if iv_ratio > 1.15:
            sentiment = "BEARISH"
            sentiment_note = "put IV significantly elevated vs calls — hedging flow dominant"
        elif iv_ratio > 1.05:
            sentiment = "MILD BEAR"
            sentiment_note = "slight put premium — mild defensive tone"
        elif iv_ratio < 0.90:
            sentiment = "BULLISH"
            sentiment_note = "call IV elevated — unusual upside demand"
        else:
            sentiment = "NEUTRAL"
            sentiment_note = "call/put IV balanced — no strong flow signal"

        # ── 3. PCR HISTORY proxy ──────────────────────────────────────────────
        # Use VIX as PCR proxy since yfinance PCR isn't available
        try:
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="30d")
            vix_closes = vix_hist["Close"].tolist()
            vix_dates = [str(d.date()) for d in vix_hist.index]
            current_vix = float(vix_closes[-1]) if vix_closes else 20.0
            vix_mean = float(np.mean(vix_closes)) if vix_closes else 20.0
            vix_regime = "FEAR" if current_vix > 25 else "ELEVATED" if current_vix > 18 else "CALM"
        except Exception:
            vix_closes = []
            vix_dates = []
            current_vix = 20.0
            vix_mean = 20.0
            vix_regime = "UNKNOWN"

        # PCR from OI ratio across near-term chain
        total_call_oi = sum(d["oi"] for d in sentiment_data if d["side"] == "call")
        total_put_oi = sum(d["oi"] for d in sentiment_data if d["side"] == "put")
        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0
        pcr_signal = "contrarian bull" if pcr > 1.3 else "contrarian bear" if pcr < 0.7 else "neutral"

        return {
            "spot": round(spot, 2),
            "ticker": ticker,
            # Skew
            "skew_data": skew_data,
            "skew_regime": skew_regime,
            "skew_note": skew_note,
            "avg_skew": round(avg_skew, 3),
            "put_25d_skew": round(avg_put_skew, 3),
            "call_25d_skew": round(avg_call_skew, 3),
            "atm_iv_by_exp": atm_iv_by_exp,
            # Sentiment
            "sentiment_data": sentiment_data,
            "sentiment": sentiment,
            "sentiment_note": sentiment_note,
            "avg_call_iv": round(avg_call_iv, 2),
            "avg_put_iv": round(avg_put_iv, 2),
            "iv_ratio": round(iv_ratio, 3),
            # VIX / PCR
            "vix_history": [round(float(v), 2) for v in vix_closes],
            "vix_dates": vix_dates,
            "current_vix": round(current_vix, 2),
            "vix_mean_30d": round(vix_mean, 2),
            "vix_regime": vix_regime,
            "pcr": pcr,
            "pcr_signal": pcr_signal,
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}
