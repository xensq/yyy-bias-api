import yfinance as yf
import numpy as np
from datetime import datetime

TICKER_MAP = {"SPX": "^SPX", "NDX": "^NDX", "SPY": "SPY", "QQQ": "QQQ"}

def get_iv_surface(ticker="SPX"):
    try:
        sym = TICKER_MAP.get(ticker.upper(), ticker)
        t = yf.Ticker(sym)
        hist = t.history(period="2d")
        if hist.empty:
            return {"error": "no price data"}
        spot = float(hist["Close"].iloc[-1])
        exps = t.options
        if not exps:
            return {"error": "no options"}
        points = []
        today = datetime.now()
        atm_ivs = []
        for exp in exps[:8]:
            try:
                dte = max((datetime.strptime(exp, "%Y-%m-%d") - today).days, 0)
                if dte > 60:
                    continue
                chain = t.option_chain(exp)
                for side in [chain.calls, chain.puts]:
                    for _, row in side.iterrows():
                        strike = float(row["strike"])
                        iv = float(row["impliedVolatility"]) if row["impliedVolatility"] else 0
                        oi = float(row.get("openInterest", 0) or 0)
                        moneyness = round(strike / spot, 4)
                        if iv <= 0 or iv > 5 or oi < 10:
                            continue
                        if moneyness < 0.8 or moneyness > 1.2:
                            continue
                        if abs(moneyness - 1.0) < 0.02:
                            atm_ivs.append(iv)
                        points.append({"strike": round(strike, 0), "dte": int(dte), "iv": round(float(iv), 4), "moneyness": round(float(moneyness), 4)})
            except Exception:
                continue
        atm_iv = float(np.median(atm_ivs)) if atm_ivs else 0.0
        return {"points": points, "spot": round(spot, 2), "atm_iv": round(atm_iv, 4), "error": None}
    except Exception as e:
        return {"error": str(e)}
