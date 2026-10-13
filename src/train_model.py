"""
Module 2 - Train and compare RUL prediction models.
Target: rul (remaining useful life in cycles)
Features: cycle, voltage, temperature, capacity, soh
"""

import pandas as pd
import numpy as np
import joblib
import json
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

DATA_DIR = Path("data")
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)

FEATURES = ["cycle", "voltage", "temperature", "capacity", "soh"]
TARGET = "rul"

print("Loading train/test splits ...")
train = pd.read_csv(DATA_DIR / "train.csv")
test  = pd.read_csv(DATA_DIR / "test.csv")
print(f"  train: {train.shape} | test: {test.shape}")

X_train = train[FEATURES].values
y_train = train[TARGET].values
X_test  = test[FEATURES].values
y_test  = test[TARGET].values

results = {}

def evaluate(name, model):
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    mae  = mean_absolute_error(y_test, pred)
    rmse = np.sqrt(mean_squared_error(y_test, pred))
    r2   = r2_score(y_test, pred)
    results[name] = {"MAE": mae, "RMSE": rmse, "R2": r2, "model": model}
    print(f"\n{name}")
    print(f"  MAE : {mae:.2f} cycles")
    print(f"  RMSE: {rmse:.2f} cycles")
    print(f"  R2  : {r2:.3f}")
    return model

print("\nTraining Random Forest ...")
rf = RandomForestRegressor(
    n_estimators=300, max_depth=None,
    random_state=42, n_jobs=-1
)
evaluate("Random Forest", rf)

print("\nTraining XGBoost ...")
xgb = XGBRegressor(
    n_estimators=500, learning_rate=0.05, max_depth=6,
    subsample=0.9, colsample_bytree=0.9,
    random_state=42, n_jobs=-1
)
evaluate("XGBoost", xgb)

best_name = min(results, key=lambda k: results[k]["MAE"])
best = results[best_name]["model"]
print(f"\nBest model: {best_name} (MAE = {results[best_name]['MAE']:.2f})")

joblib.dump({"model": best, "features": FEATURES, "name": best_name},
            MODEL_DIR / "rul_model.pkl")
print(f"Saved -> models/rul_model.pkl")

summary = {
    name: {k: float(v) for k, v in res.items() if k != "model"}
    for name, res in results.items()
}
summary["best_model"] = best_name
with open(MODEL_DIR / "results.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"Saved -> models/results.json")

print("\nGenerating feature importance plot ...")
if best_name == "Random Forest":
    importances = best.feature_importances_
else:
    importances = best.feature_importances_

fig, ax = plt.subplots(figsize=(7, 4))
idx = np.argsort(importances)
ax.barh([FEATURES[i] for i in idx], importances[idx], color="steelblue")
ax.set_xlabel("Importance")
ax.set_title(f"Feature importance - {best_name}")
plt.tight_layout()
plt.savefig(MODEL_DIR / "feature_importance.png", dpi=120)
print(f"Saved -> models/feature_importance.png")