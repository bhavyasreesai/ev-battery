"""
Module 1 - Battery-wise train/test split.
"""

import pandas as pd
from pathlib import Path
import json

DATA_DIR = Path("data")
SRC_CSV = DATA_DIR / "battery_cycle_level_dataset_CLEAN_FINAL.csv"
TRAIN_CSV = DATA_DIR / "train.csv"
TEST_CSV = DATA_DIR / "test.csv"
SPLIT_JSON = DATA_DIR / "split_info.json"

TEST_BATTERY_FRACTION = 0.20
RANDOM_SEED = 42

print(f"Loading {SRC_CSV} ...")
df = pd.read_csv(SRC_CSV)
print(f"  shape: {df.shape}")
print(f"  batteries: {df['battery_id'].nunique()}")

expected = {"battery_id", "cycle", "voltage", "temperature",
            "capacity", "soh", "rul"}
missing = expected - set(df.columns)
if missing:
    raise ValueError(f"Missing columns: {missing}")

batteries = sorted(df["battery_id"].unique())
n_test = max(1, int(round(len(batteries) * TEST_BATTERY_FRACTION)))

rng = pd.Series(batteries).sample(frac=1, random_state=RANDOM_SEED)
test_batteries = sorted(rng.iloc[:n_test].tolist())
train_batteries = sorted(rng.iloc[n_test:].tolist())

train_df = df[df["battery_id"].isin(train_batteries)].copy()
test_df  = df[df["battery_id"].isin(test_batteries)].copy()

assert set(train_batteries).isdisjoint(set(test_batteries))
assert len(train_df) + len(test_df) == len(df)

print()
print("=" * 50)
print(f"TRAIN : {len(train_batteries):>2} batteries, {len(train_df):>5} rows")
print(f"TEST  : {len(test_batteries):>2} batteries, {len(test_df):>5} rows")
print("=" * 50)
print(f"Test batteries (unseen): {test_batteries}")
print()

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