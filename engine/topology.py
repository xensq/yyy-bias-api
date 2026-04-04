import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

SYMBOL = "^NDX"
N_LAGS = 10
WINDOW = 20
ENTROPY_WINDOW = 20
THRESH_WINDOW = 100


def fetch_5min(days=7):
    df = yf.Ticker(SYMBOL).history(period=f"{days}d", interval="5m")
    df.index = df.index.tz_localize(None) if df.index.tzinfo else df.index
    return df


def build_features(df):
    df = df.copy()
    df["r"] = np.log(df["Close"] / df["Close"].shift(1))
    for i in range(1, N_LAGS + 1):
        df[f"lag{i}"] = df["r"].shift(i)
    df["mu"] = df["r"].rolling(WINDOW).mean()
    df["sig"] = df["r"].rolling(WINDOW).std()
    df["skew"] = df["r"].rolling(WINDOW).skew()
    df["kurt"] = df["r"].rolling(WINDOW).kurt()
    cols = [f"lag{i}" for i in range(1, N_LAGS + 1)] + ["mu", "sig", "skew", "kurt"]
    return df.dropna(), cols


def calculate_topology():
    try:
        raw = fetch_5min(7)
        if len(raw) < 60:
            raw = fetch_5min(14)
        df, cols = build_features(raw)
        X = df[cols].values
        X_c = StandardScaler(with_std=False).fit_transform(X)
        pca = PCA(n_components=3)
        scores = pca.fit_transform(X_c)
        pca1 = float(scores[-1, 0])
        pca2 = float(scores[-1, 1])
        roll_vol = df["r"].rolling(WINDOW).std() * np.sqrt(252)
        vol_mean = float(roll_vol.mean())
        vol_std = float(roll_vol.std())
        vol_z = (float(roll_vol.iloc[-1]) - vol_mean) / vol_std if vol_std > 0 else 0.0
        n = min(len(scores), 200)
        vz = ((roll_vol - vol_mean) / vol_std).fillna(0).values
        hist = np.column_stack([scores[-n:, 0], scores[-n:, 1], vz[-n:]])
        cov = np.cov(hist.T)
        try:
            cov_inv = np.linalg.inv(cov + np.eye(3) * 1e-8)
        except np.linalg.LinAlgError:
            cov_inv = np.eye(3)
        z = np.array([pca1, pca2, vol_z])
        dist = float(np.sqrt(max(0, z @ cov_inv @ z)))
        if dist >= 2.0:
            regime = "UNCHARTED"
        elif dist >= 1.5:
            regime = "EXTENDED"
        elif pca1 > 1.0:
            regime = "BULL TREND"
        elif pca1 < -1.0:
            regime = "BEAR TREND"
        else:
            regime = "CONSOLIDATION"
        aligned = (np.sign(pca1) == np.sign(pca2)) and pca1 != 0
        dist_factor = 1.0 if dist < 1.5 else (0.5 if dist < 2.0 else 0.0)
        mom_factor = 1.0 if aligned else 0.5
        return {
            "pca1": round(pca1, 3), "pca2": round(pca2, 3), "vol_z": round(vol_z, 3),
            "regime": regime, "dist": round(dist, 3), "aligned": aligned,
            "size_factor": round(dist_factor * mom_factor, 2), "dist_factor": dist_factor,
            "price": round(float(df["Close"].iloc[-1]), 2), "error": None,
        }
    except Exception as e:
        return {"error": str(e), "regime": "UNKNOWN", "pca1": 0, "pca2": 0,
                "vol_z": 0, "dist": 0, "aligned": False, "size_factor": 0, "dist_factor": 0, "price": 0}


def calculate_entropy():
    try:
        raw = fetch_5min(14)
        df = raw.copy()
        df["r"] = np.log(df["Close"] / df["Close"].shift(1))
        df = df.dropna()
        df["entropy"] = df["r"].rolling(ENTROPY_WINDOW).std() * np.sqrt(252)
        df["threshold"] = df["entropy"].rolling(THRESH_WINDOW).mean()
        df = df.dropna()
        if len(df) < 5:
            return {"error": "not enough data", "status": "UNKNOWN", "size_factor": 0,
                    "entropy": 0, "threshold": 0, "rho": 0}
        e = float(df["entropy"].iloc[-1])
        t = float(df["threshold"].iloc[-1])
        rho = e / t if t > 0 else 1.0
        if rho >= 1.2:
            status, size_factor = "CRITICAL", 0.0
        elif rho >= 1.0:
            status, size_factor = "ELEVATED", 0.5
        else:
            status, size_factor = "NORMAL", 1.0
        recent = df["entropy"].iloc[-6:].values
        trend = "rising" if recent[-1] > recent[0] else "falling"
        df2, cols = build_features(raw.copy())
        X_c = StandardScaler(with_std=False).fit_transform(df2[cols].values)
        s = PCA(n_components=2).fit_transform(X_c)
        return {
            "entropy": round(e, 6), "threshold": round(t, 6), "rho": round(rho, 3),
            "status": status, "size_factor": size_factor,
            "pca1": round(float(s[-1, 0]), 3), "pca2": round(float(s[-1, 1]), 3),
            "trend": trend, "error": None,
        }
    except Exception as ex:
        return {"error": str(ex), "status": "UNKNOWN", "size_factor": 0,
                "entropy": 0, "threshold": 0, "rho": 0, "pca1": 0, "pca2": 0, "trend": "unknown"}
