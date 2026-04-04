import numpy as np
from .topology import fetch_5min, build_features
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

def get_chart_data(n_bars=200):
    try:
        raw = fetch_5min(14)
        df, cols = build_features(raw)
        X_c = StandardScaler(with_std=False).fit_transform(df[cols].values)
        scores = PCA(n_components=3).fit_transform(X_c)
        df["entropy"] = df["r"].rolling(20).std() * (252 ** 0.5)
        df["threshold"] = df["entropy"].rolling(100).mean()
        df = df.dropna()
        n = min(n_bars, len(df), len(scores))
        pca1 = [round(float(x), 4) for x in scores[-n:, 0]]
        pca2 = [round(float(x), 4) for x in scores[-n:, 1]]
        vol_z_raw = df["r"].rolling(20).std().values
        vol_mean = float(np.nanmean(vol_z_raw))
        vol_std = float(np.nanstd(vol_z_raw))
        vol_z = [round(float((x - vol_mean) / vol_std) if vol_std > 0 else 0, 4) for x in vol_z_raw[-n:]]
        entropy = [round(float(x), 6) for x in df["entropy"].values[-n:]]
        threshold = [round(float(x), 6) for x in df["threshold"].values[-n:]]
        return {"pca1": pca1, "pca2": pca2, "vol_z": vol_z, "entropy": entropy, "threshold": threshold, "n": n, "error": None}
    except Exception as e:
        return {"error": str(e)}
