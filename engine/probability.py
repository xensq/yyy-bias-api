import yfinance as yf
import numpy as np
from scipy import stats
from datetime import datetime, timedelta

TICKER_MAP = {"SPX": "^SPX", "NDX": "^NDX", "SPY": "SPY", "QQQ": "QQQ"}

def get_probability(ticker="SPX"):
    try:
        sym = TICKER_MAP.get(ticker.upper(), "^SPX")
        t = yf.Ticker(sym)
        hist = t.history(period="2y")
        if hist.empty or len(hist) < 50:
            return {"error": "insufficient data"}

        closes = hist["Close"].values
        spot = float(closes[-1])

        # Daily log returns
        returns = np.diff(np.log(closes))
        mu = float(np.mean(returns))
        sigma = float(np.std(returns))
        skew = float(stats.skew(returns))
        kurt = float(stats.kurtosis(returns))

        # Annualized
        mu_ann = mu * 252
        sigma_ann = sigma * np.sqrt(252)

        # 1-day probability bands
        def bands_1d(spot, mu, sigma):
            return {
                "68": [round(spot * np.exp(mu - sigma), 2), round(spot * np.exp(mu + sigma), 2)],
                "90": [round(spot * np.exp(mu - 1.645*sigma), 2), round(spot * np.exp(mu + 1.645*sigma), 2)],
                "95": [round(spot * np.exp(mu - 2*sigma), 2), round(spot * np.exp(mu + 2*sigma), 2)],
                "99": [round(spot * np.exp(mu - 2.576*sigma), 2), round(spot * np.exp(mu + 2.576*sigma), 2)],
            }

        # 1-week probability bands (5 trading days)
        def bands_nd(spot, mu, sigma, n):
            mu_n = mu * n
            sigma_n = sigma * np.sqrt(n)
            return {
                "68": [round(spot * np.exp(mu_n - sigma_n), 2), round(spot * np.exp(mu_n + sigma_n), 2)],
                "90": [round(spot * np.exp(mu_n - 1.645*sigma_n), 2), round(spot * np.exp(mu_n + 1.645*sigma_n), 2)],
                "95": [round(spot * np.exp(mu_n - 2*sigma_n), 2), round(spot * np.exp(mu_n + 2*sigma_n), 2)],
                "99": [round(spot * np.exp(mu_n - 2.576*sigma_n), 2), round(spot * np.exp(mu_n + 2.576*sigma_n), 2)],
            }

        # Tail analysis
        n_days = len(returns)
        days_beyond_2s = int(np.sum(np.abs(returns) > 2 * sigma))
        fat_tail = days_beyond_2s / n_days > 0.046  # more than normal 4.6%

        # Forward probability heatmap — 5 trading days
        # For each day, compute probability density across price grid
        n_forward = 5
        n_price = 60
        price_range = spot * sigma * (5 ** 0.5) * 3.5  # ±3.5σ at day 5
        price_grid = np.linspace(spot - price_range, spot + price_range, n_price)

        heatmap = []
        sigma_bands = {"1s": [], "2s": [], "3s": [], "m1s": [], "m2s": [], "m3s": []}

        for day in range(1, n_forward + 1):
            mu_d = mu * day
            sigma_d = sigma * np.sqrt(day)
            # Log-normal density
            log_prices = np.log(price_grid / spot)
            density = stats.norm.pdf(log_prices, mu_d, sigma_d) / price_grid
            density = density / density.max()  # normalize
            heatmap.append([round(float(d), 4) for d in density])

            # Sigma bands
            sigma_bands["1s"].append(round(float(spot * np.exp(mu_d + sigma_d)), 2))
            sigma_bands["2s"].append(round(float(spot * np.exp(mu_d + 2*sigma_d)), 2))
            sigma_bands["3s"].append(round(float(spot * np.exp(mu_d + 3*sigma_d)), 2))
            sigma_bands["m1s"].append(round(float(spot * np.exp(mu_d - sigma_d)), 2))
            sigma_bands["m2s"].append(round(float(spot * np.exp(mu_d - 2*sigma_d)), 2))
            sigma_bands["m3s"].append(round(float(spot * np.exp(mu_d - 3*sigma_d)), 2))

        # Terminal distribution (day 5)
        mu_5 = mu * 5
        sigma_5 = sigma * np.sqrt(5)
        terminal_density = stats.norm.pdf(np.log(price_grid / spot), mu_5, sigma_5) / price_grid
        terminal_density = terminal_density / terminal_density.max()

        # Return distribution histogram
        ret_pct = returns * 100
        hist_counts, hist_edges = np.histogram(ret_pct, bins=60, density=True)
        hist_centers = [(hist_edges[i] + hist_edges[i+1]) / 2 for i in range(len(hist_counts))]

        # Normal fit
        x_fit = np.linspace(ret_pct.min(), ret_pct.max(), 200)
        normal_fit = stats.norm.pdf(x_fit, mu*100, sigma*100)

        return {
            "spot": round(spot, 2),
            "ticker": ticker,
            "mu_daily_pct": round(mu * 100, 4),
            "sigma_daily_pct": round(sigma * 100, 4),
            "mu_ann_pct": round(mu_ann * 100, 2),
            "sigma_ann_pct": round(sigma_ann * 100, 2),
            "skewness": round(skew, 4),
            "excess_kurtosis": round(kurt, 4),
            "n_days": n_days,
            "fat_tails": bool(fat_tail),
            "days_beyond_2s": days_beyond_2s,
            "days_beyond_2s_pct": round(days_beyond_2s / n_days * 100, 1),
            "normal_expect_2s_pct": 4.6,
            "bands_1d": bands_1d(spot, mu, sigma),
            "bands_1w": bands_nd(spot, mu, sigma, 5),
            "price_grid": [round(float(p), 2) for p in price_grid],
            "heatmap": heatmap,
            "sigma_bands": sigma_bands,
            "terminal_density": [round(float(d), 4) for d in terminal_density],
            "return_hist_centers": [round(float(c), 4) for c in hist_centers],
            "return_hist_counts": [round(float(c), 4) for c in hist_counts],
            "normal_fit_x": [round(float(x), 4) for x in x_fit],
            "normal_fit_y": [round(float(y), 4) for y in normal_fit],
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}
