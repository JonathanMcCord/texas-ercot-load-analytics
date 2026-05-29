"""
ERCOT Hourly Load Data — Cleaning Pipeline
===========================================

Reads ERCOT "Native_Load_YYYY.xlsx" files from data/raw/, normalizes
schema differences across years, converts ERCOT's hour-ending convention
to standard datetimes, handles DST rows, and writes a clean unified
dataset to data/processed/.

Key cleaning steps:
  1. Handle inconsistent column naming (some years use 'HourEnding',
     others 'Hour Ending').
  2. Convert ERCOT's "24:00" hour-ending notation to midnight of the
     following day (standard Python datetime convention).
  3. Identify and flag the annual DST fall-back duplicate hour.
  4. Reshape from wide (one column per weather zone) to long (one row
     per zone per hour) for easier downstream analysis.

Author: Jonathan McCord
Source: https://www.ercot.com/gridinfo/load/load_hist
"""

from pathlib import Path
import pandas as pd
import re

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ERCOT weather zones (8 zones + total). Order matches the source files.
WEATHER_ZONES = ["COAST", "EAST", "FWEST", "NORTH",
                 "NCENT", "SOUTH", "SCENT", "WEST"]
ERCOT_TOTAL = "ERCOT"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def parse_ercot_timestamp(ts):
    """
    Convert an ERCOT 'Hour Ending' value to a pandas Timestamp.

    ERCOT uses hour-ending notation 1:00-24:00, where '24:00' means
    midnight starting the next day. It also annotates the DST fall-back
    duplicate hour with a 'DST' suffix.

    Most rows arrive as strings, but some cells are occasionally
    interpreted by Excel as native datetime objects. We handle both.

    Returns a tuple of (timestamp, is_dst_duplicate_flag).
    """
    # Case 1: already a datetime-like object (datetime, pd.Timestamp, np.datetime64)
    if not isinstance(ts, str):
        try:
            return pd.Timestamp(ts), False
        except Exception:
            pass  # fall through to string parsing as a last resort

    s = str(ts).strip()
    is_dst = False

    # Strip any DST flag (varies by year — 'DST', '*DST*', etc.)
    if "DST" in s.upper():
        is_dst = True
        s = re.sub(r"\s*\*?DST\*?\s*", "", s, flags=re.IGNORECASE).strip()

    # ERCOT's standard format: MM/DD/YYYY HH:MM with HH in 01..24
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})$", s)
    if not m:
        raise ValueError(f"Unrecognized timestamp format: {ts!r}")

    month, day, year, hour, minute = (int(x) for x in m.groups())

    # Handle the 24:00 → midnight-of-next-day conversion
    if hour == 24:
        base = pd.Timestamp(year=year, month=month, day=day) + pd.Timedelta(days=1)
        return base, is_dst
    return pd.Timestamp(year=year, month=month, day=day,
                        hour=hour, minute=minute), is_dst


def load_yearly_file(filepath: Path) -> pd.DataFrame:
    """Load a single Native_Load_YYYY.xlsx file and normalize its schema."""
    df = pd.read_excel(filepath, sheet_name=0)

    # Normalize the timestamp column name across years
    rename_map = {"HourEnding": "Hour Ending"}
    df = df.rename(columns=rename_map)

    if "Hour Ending" not in df.columns:
        raise ValueError(f"{filepath.name}: no recognized timestamp column")

    # Parse timestamps and flag DST rows
    parsed = df["Hour Ending"].apply(parse_ercot_timestamp)
    df["timestamp"] = parsed.apply(lambda x: x[0])
    df["is_dst_duplicate"] = parsed.apply(lambda x: x[1])

    # Reorder columns; drop the raw text timestamp
    cols = ["timestamp", "is_dst_duplicate"] + WEATHER_ZONES + [ERCOT_TOTAL]
    return df[cols]


def to_long_format(df_wide: pd.DataFrame) -> pd.DataFrame:
    """Reshape from one-column-per-zone (wide) to one-row-per-zone (long)."""
    zone_cols = WEATHER_ZONES + [ERCOT_TOTAL]
    long_df = df_wide.melt(
        id_vars=["timestamp", "is_dst_duplicate"],
        value_vars=zone_cols,
        var_name="zone",
        value_name="load_mw",
    )
    return long_df.sort_values(["timestamp", "zone"]).reset_index(drop=True)


# ---------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------

def main():
    files = sorted(RAW_DIR.glob("Native_Load_*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No Native_Load_*.xlsx files found in {RAW_DIR}")

    print(f"Found {len(files)} file(s):")
    for f in files:
        print(f"  - {f.name}")

    # Load and concatenate
    yearly_frames = []
    for f in files:
        print(f"\nProcessing {f.name}...")
        df = load_yearly_file(f)
        print(f"  Rows: {len(df):,}")
        print(f"  Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
        print(f"  DST rows: {df['is_dst_duplicate'].sum()}")
        yearly_frames.append(df)

    combined = pd.concat(yearly_frames, ignore_index=True).sort_values("timestamp")
    combined = combined.reset_index(drop=True)

    # Sanity checks
    print("\n" + "=" * 50)
    print("CLEANING SUMMARY")
    print("=" * 50)
    print(f"Total hourly records: {len(combined):,}")
    print(f"Full date range: {combined['timestamp'].min()} → {combined['timestamp'].max()}")
    print(f"Total DST duplicate rows: {combined['is_dst_duplicate'].sum()}")
    print(f"Null load values (ERCOT total): {combined[ERCOT_TOTAL].isna().sum()}")
    print(f"\nERCOT load summary (MW):")
    print(combined[ERCOT_TOTAL].describe().round(0))

    # Save wide-format clean output (good for time-series analysis)
    wide_out = OUT_DIR / "ercot_hourly_load_wide.csv"
    combined.to_csv(wide_out, index=False)
    print(f"\n✓ Wide-format output written: {wide_out}")

    # Save long-format clean output (good for SQL / dashboard analysis)
    long_df = to_long_format(combined)
    long_out = OUT_DIR / "ercot_hourly_load_long.csv"
    long_df.to_csv(long_out, index=False)
    print(f"✓ Long-format output written: {long_out}")
    print(f"  ({len(long_df):,} rows × {len(long_df.columns)} columns)")


if __name__ == "__main__":
    main()
