"""
Module 1 - Battery-wise train/test split.

Why battery-wise?
Random row splits leak information: cycles from the same battery
appear in both train and test, so the model "sees" the battery it
is being tested on. Battery-wise splitting simulates the real world
where the model must predict RUL for a battery it has never seen.
"""

import pandas as pd
from pathlib import Path
import json

# ---------- Config ----------
DATA_DIR = Path("data")
SRC_CSV = DATA_DIR / "battery_cycle_level_dataset_CLEAN_FINAL.csv"

TRAIN_CSV = DATA_DIR / "train.csv"
TEST_CSV = DATA_DIR / "test.csv"
SPLIT_JSON = DATA_DIR / "split_info.json"

TEST_BATTERY_FRACTION = 0.20   # 20% of batteries go to test
RANDOM_SEED = 42               # for reproducibility

# ---------- Load ----------
print(f"Loading {SRC_CSV} ...")
df = pd.read_csv(SRC_CSV)
print(f"  shape: {df.shape}")
print(f"  batteries: {df['battery_id'].nunique()}")

# ---------- Validate columns ----------
expected = {"battery_id", "cycle", "voltage", "temperature",
            "capacity", "soh", "rul"}
missing = expected - set(df.columns)
if missing:
    raise ValueError(f"Missing columns: {missing}")

# ---------- Split by battery ----------
batteries = sorted(df["battery_id"].unique())
n_test = max(1, int(round(len(batteries) * TEST_BATTERY_FRACTION)))
n_train = len(batteries) - n_test

rng = pd.Series(batteries).sample(frac=1, random_state=RANDOM_SEED)
test_batteries = sorted(rng.iloc[:n_test].tolist())
train_batteries = sorted(rng.iloc[n_test:].tolist())

train_df = df[df["battery_id"].isin(train_batteries)].copy()
test_df  = df[df["battery_id"].isin(test_batteries)].copy()

# ---------- Sanity checks ----------
assert set(train_batteries).isdisjoint(set(test_batteries)), \
    "Battery IDs overlap between train and test!"
assert len(train_df) + len(test_df) == len(df), \
    "Row count mismatch after split!"

print()
print("=" * 50)
print(f"TRAIN : {len(train_batteries):>2} batteries, {len(train_df):>5} rows")
print(f"TEST  : {len(test_batteries):>2} batteries, {len(test_df):>5} rows")
print("=" * 50)
print(f"Test batteries (unseen): {test_batteries}")
print()

# ---------- Save ----------
train_df.to_csv(TRAIN_CSV, index=False)
test_df.to_csv(TEST_CSV, index=False)

split_info = {
    "n_batteries_total": len(batteries),
    "n_batteries_train": len(train_batteries),
    "n_batteries_test": len(test_batteries),
    "train_batteries": train_batteries,
    "test_batteries": test_batteries,
    "n_rows_train": len(train_df),
    "n_rows_test": len(test_df),
    "random_seed": RANDOM_SEED,
    "test_fraction": TEST_BATTERY_FRACTION,
}
with open(SPLIT_JSON, "w") as f:
    json.dump(split_info, f, indent=2)

print(f"Saved -> {TRAIN_CSV}")
print(f"Saved -> {TEST_CSV}")
print(f"Saved -> {SPLIT_JSON}")