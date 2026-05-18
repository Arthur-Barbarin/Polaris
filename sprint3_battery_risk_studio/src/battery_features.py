"""
battery_features.py
-------------------
Utility functions for loading and processing the NASA PCoE
lithium-ion battery aging dataset (.mat format).

NASA dataset reference:
    Saha, B. and Goebel, K. (2007). "Battery Data Set", NASA Ames Prognostics
    Data Repository, NASA Ames Research Center, Moffett Field, CA.
    https://www.nasa.gov/content/prognostics-center-of-excellence-data-set-repository

Batteries covered: B0005, B0006, B0007, B0018 (2 Ah nominal, 4 V nominal)

Threshold conventions used in this project:
    - 80% SOH (1.6 Ah): operational warning threshold — flag for inspection
    - 70% SOH (~1.4 Ah): NASA-style end-of-life threshold — ground the vehicle
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio


# ── Constants ────────────────────────────────────────────────────────────────

NOMINAL_CAPACITY_AH   = 2.0   # Ah — datasheet rating for these NASA cells
SOH_WARNING_THRESHOLD = 0.80  # 80 % → flag for inspection
SOH_EOL_THRESHOLD     = 0.70  # 70 % / ~1.4 Ah → end of life (NASA convention)


# ── Loading ──────────────────────────────────────────────────────────────────

def load_battery_mat(filepath: str | Path) -> dict:
    """
    Load a NASA battery .mat file and return the raw battery dict.

    Parameters
    ----------
    filepath : str or Path

    Returns
    -------
    dict  — battery dict with key 'cycle' (list of cycle dicts).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Battery file not found: {filepath}")

    mat = sio.loadmat(str(filepath), simplify_cells=True)
    battery_keys = [k for k in mat.keys() if not k.startswith("_")]
    if not battery_keys:
        raise KeyError(f"No valid battery variable found in {filepath.name}")

    battery_key = battery_keys[0]
    print(f"  Loaded '{battery_key}' from {filepath.name}")
    return mat[battery_key]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_scalar(value) -> float:
    """Return a float scalar regardless of whether value is a scalar or array."""
    if value is None:
        return np.nan
    if hasattr(value, "__len__"):
        return float(value[-1]) if len(value) > 0 else np.nan
    return float(value)


def _safe_array(value) -> np.ndarray:
    """Return a 1-D float array, or an empty array if value is missing."""
    if value is None:
        return np.array([])
    arr = np.array(value, dtype=float).ravel()
    return arr


# ── Feature extraction ────────────────────────────────────────────────────────

def extract_cycle_features(
    battery: dict,
    initial_capacity: float | None = None,
) -> pd.DataFrame:
    """
    Extract a full feature matrix from a battery dict.

    Each row corresponds to one discharge cycle.  Features are derived from
    the raw time-series arrays stored in each cycle's 'data' sub-dict.

    Features produced
    -----------------
    cycle_index             : position in the full cycle list (1-based)
    discharge_num           : discharge-only counter (1-based)  ← used for RUL
    capacity                : measured Ah delivered in this discharge
    ambient_temp            : ambient temperature during the cycle (°C)
    mean_discharge_voltage  : average terminal voltage during discharge (V)
    min_discharge_voltage   : minimum voltage reached during discharge (V)
    max_temperature         : peak cell temperature during discharge (°C)
    mean_temperature        : average cell temperature during discharge (°C)
    discharge_duration      : total discharge time in seconds
    capacity_fade_rate      : capacity loss vs. previous cycle (Ah) — 0 for cycle 1
    soh                     : state of health = capacity / initial_capacity

    Parameters
    ----------
    battery : dict
        Output of `load_battery_mat`.
    initial_capacity : float, optional
        Reference capacity for SOH. Defaults to the first discharge cycle's
        measured capacity (preferred over the nominal 2 Ah datasheet value).

    Returns
    -------
    pd.DataFrame  — one row per discharge cycle.
    """
    cycles = battery["cycle"]
    records = []
    discharge_counter = 0

    for i, cycle in enumerate(cycles):
        if cycle.get("type", "").strip().lower() != "discharge":
            continue

        discharge_counter += 1
        data = cycle.get("data", {})

        # ── Capacity (scalar Ah) ──────────────────────────────────────────────
        capacity = _safe_scalar(data.get("Capacity"))

        # ── Time-series arrays ────────────────────────────────────────────────
        voltage     = _safe_array(data.get("Voltage_measured"))
        temperature = _safe_array(data.get("Temperature_measured"))
        time        = _safe_array(data.get("Time"))

        # ── Time-series derived features ──────────────────────────────────────
        mean_v    = float(np.mean(voltage))     if len(voltage) > 0     else np.nan
        min_v     = float(np.min(voltage))      if len(voltage) > 0     else np.nan
        max_temp  = float(np.max(temperature))  if len(temperature) > 0 else np.nan
        mean_temp = float(np.mean(temperature)) if len(temperature) > 0 else np.nan
        duration  = float(time[-1] - time[0])   if len(time) > 1        else np.nan

        records.append(
            {
                "cycle_index":            i + 1,
                "discharge_num":          discharge_counter,
                "capacity":               capacity,
                "ambient_temp":           float(cycle.get("ambient_temperature", np.nan)),
                "mean_discharge_voltage": mean_v,
                "min_discharge_voltage":  min_v,
                "max_temperature":        max_temp,
                "mean_temperature":       mean_temp,
                "discharge_duration":     duration,
            }
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # ── SOH ───────────────────────────────────────────────────────────────────
    if initial_capacity is None:
        initial_capacity = df["capacity"].iloc[0]
        print(f"  Initial capacity: {initial_capacity:.4f} Ah")

    df["soh"] = df["capacity"] / initial_capacity

    # ── Capacity fade rate (Ah lost since previous cycle) ─────────────────────
    # Positive value = capacity dropped; first cycle gets 0
    df["capacity_fade_rate"] = df["capacity"].diff().mul(-1).fillna(0)

    return df


# ── RUL targets ───────────────────────────────────────────────────────────────

def add_rul_targets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add remaining-useful-life (RUL) columns as regression targets.

    We compute labels retrospectively from the full SOH sequence:
        rul_warning = cycles remaining until SOH first crosses 80 %
        rul_eol     = cycles remaining until SOH first crosses 70 %

    A value of 0 means the threshold has already been crossed.
    NaN means the battery never reached that threshold in the dataset.

    Why retrospective?
    ------------------
    Because we have the full aging history of each cell, we know exactly
    when each threshold was crossed.  A model trained on these labels learns
    to reproduce that countdown from features alone — without seeing the future.

    Parameters
    ----------
    df : pd.DataFrame  — output of `extract_cycle_features`.

    Returns
    -------
    pd.DataFrame  — same df with 'rul_warning' and 'rul_eol' columns added.
    """
    df = df.copy()

    for col, threshold in [("rul_warning", SOH_WARNING_THRESHOLD),
                           ("rul_eol",     SOH_EOL_THRESHOLD)]:
        crossed = df.index[df["soh"] <= threshold]
        if len(crossed) == 0:
            df[col] = np.nan
        else:
            crossing_discharge_num = df.loc[crossed[0], "discharge_num"]
            df[col] = (crossing_discharge_num - df["discharge_num"]).clip(lower=0)

    return df


# ── Multi-battery dataset builder ─────────────────────────────────────────────

def build_dataset(
    battery_files: list[str | Path],
    data_dir: str | Path = ".",
) -> pd.DataFrame:
    """
    Build the full feature dataset by processing multiple battery files.

    Adds a 'battery_id' column so records from different cells can be
    distinguished during training / cross-validation.

    Parameters
    ----------
    battery_files : list of filenames (e.g. ['B0005.mat', 'B0006.mat'])
    data_dir      : directory where the .mat files live.

    Returns
    -------
    pd.DataFrame  — all batteries concatenated, one row per discharge cycle.
    """
    data_dir = Path(data_dir)
    frames = []

    for filename in battery_files:
        filepath = data_dir / filename
        try:
            battery = load_battery_mat(filepath)
        except FileNotFoundError as e:
            print(f"  WARNING: {e} — skipping.")
            continue

        df = extract_cycle_features(battery)
        df = add_rul_targets(df)
        df.insert(0, "battery_id", Path(filename).stem)
        frames.append(df)
        print(f"  {Path(filename).stem}: {len(df)} discharge cycles extracted.")

    if not frames:
        raise RuntimeError("No battery files could be loaded.")

    combined = pd.concat(frames, ignore_index=True)
    print(f"\n  Total rows: {len(combined)} across {len(frames)} batteries.")
    return combined


# ── Backwards-compatible helpers kept from Step 1 ────────────────────────────

def extract_discharge_cycles(battery: dict) -> list[dict]:
    """Lightweight version — returns a list of dicts with capacity and SOH only.
    Used by the validation notebook. For full features use extract_cycle_features."""
    df = extract_cycle_features(battery)
    return df[["cycle_index", "discharge_num", "capacity", "ambient_temp"]].to_dict("records")


def compute_soh(discharge_records: list[dict], initial_capacity: float | None = None) -> list[dict]:
    if not discharge_records:
        return discharge_records
    if initial_capacity is None:
        initial_capacity = discharge_records[0]["capacity"]
    for rec in discharge_records:
        rec["soh"] = rec["capacity"] / initial_capacity
    return discharge_records


def find_threshold_crossing(
    discharge_records: list[dict],
    threshold: float,
    column: str = "soh",
) -> int | None:
    for rec in discharge_records:
        if rec.get(column, np.nan) <= threshold:
            return rec["discharge_num"]
    return None


def summarise_degradation(discharge_records: list[dict]) -> dict:
    if not discharge_records:
        return {}
    warning_cycle = find_threshold_crossing(discharge_records, SOH_WARNING_THRESHOLD)
    eol_cycle     = find_threshold_crossing(discharge_records, SOH_EOL_THRESHOLD)
    return {
        "total_discharge_cycles": len(discharge_records),
        "initial_capacity_ah":    discharge_records[0]["capacity"],
        "final_capacity_ah":      discharge_records[-1]["capacity"],
        "final_soh":              discharge_records[-1]["soh"],
        "warning_cycle":          warning_cycle,
        "eol_cycle":              eol_cycle,
        "crossed_warning":        warning_cycle is not None,
        "crossed_eol":            eol_cycle is not None,
    }
