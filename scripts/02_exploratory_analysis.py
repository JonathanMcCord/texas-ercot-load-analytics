"""
ERCOT Load — Exploratory Analysis & Winter Storm Uri Case Study
================================================================

Produces summary statistics and a featured visualization of the
Winter Storm Uri (Feb 13-19, 2021) load collapse.
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
VIS_DIR = Path(__file__).resolve().parent.parent / "visuals"
VIS_DIR.mkdir(parents=True, exist_ok=True)

# Load cleaned data
df = pd.read_csv(PROC_DIR / "ercot_hourly_load_wide.csv", parse_dates=["timestamp"])
df = df[~df["is_dst_duplicate"]].copy()  # drop DST duplicates for cleaner stats

# -------- Summary stats --------
print("=" * 60)
print("ERCOT LOAD — KEY STATISTICS")
print("=" * 60)
print(f"\nDate range: {df['timestamp'].min()} → {df['timestamp'].max()}")
print(f"Total hours: {len(df):,}")

print("\n--- Top 5 peak demand hours ---")
top = df.nlargest(5, "ERCOT")[["timestamp", "ERCOT"]]
print(top.to_string(index=False))

print("\n--- Bottom 5 demand hours ---")
low = df.nsmallest(5, "ERCOT")[["timestamp", "ERCOT"]]
print(low.to_string(index=False))

# -------- Winter Storm Uri analysis --------
uri_start = pd.Timestamp("2021-02-13")
uri_end = pd.Timestamp("2021-02-20")
uri = df[(df["timestamp"] >= uri_start) & (df["timestamp"] < uri_end)].copy()

print("\n" + "=" * 60)
print("WINTER STORM URI — Feb 13-19, 2021")
print("=" * 60)
print(f"Hours captured: {len(uri)}")
print(f"Peak load just before storm: {uri['ERCOT'].max():,.0f} MW")
print(f"Lowest load during forced outages: {uri['ERCOT'].min():,.0f} MW")
print(f"Drop: {uri['ERCOT'].max() - uri['ERCOT'].min():,.0f} MW "
      f"({(1 - uri['ERCOT'].min()/uri['ERCOT'].max())*100:.1f}%)")

# -------- Featured visualization --------
fig, ax = plt.subplots(figsize=(12, 6))

# Get a wider window for context (week before and after)
context = df[(df["timestamp"] >= pd.Timestamp("2021-02-08")) &
             (df["timestamp"] < pd.Timestamp("2021-02-25"))].copy()

ax.plot(context["timestamp"], context["ERCOT"] / 1000,
        color="#1E40AF", linewidth=1.4, label="ERCOT total load", zorder=3)

# Shade the Uri event window
ax.axvspan(uri_start, uri_end, alpha=0.15, color="red", label="Winter Storm Uri")

# Give ourselves a little headroom and footroom so labels aren't crowded
ax.set_ylim(20, 80)

# Mark the peak just before — label placed above the line in clear space
peak_idx = context["ERCOT"].idxmax()
peak_pt = context.loc[peak_idx]
ax.annotate(
    f"Peak demand: {peak_pt['ERCOT']:,.0f} MW  ({peak_pt['timestamp']:%b %d})",
    xy=(peak_pt["timestamp"], peak_pt["ERCOT"] / 1000),
    xytext=(peak_pt["timestamp"] - pd.Timedelta(days=4),
            (peak_pt["ERCOT"] / 1000) + 6),
    arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    fontsize=10, ha="left",
    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", lw=0.6),
)

# Mark the trough during outages — label placed below the line in clear space
trough_idx = uri["ERCOT"].idxmin()
trough_pt = uri.loc[trough_idx]
ax.annotate(
    f"Outage trough: {trough_pt['ERCOT']:,.0f} MW  ({trough_pt['timestamp']:%b %d})",
    xy=(trough_pt["timestamp"], trough_pt["ERCOT"] / 1000),
    xytext=(trough_pt["timestamp"] - pd.Timedelta(days=5),
            (trough_pt["ERCOT"] / 1000) - 8),
    arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
    fontsize=10, ha="left",
    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", lw=0.6),
)

ax.set_title("Texas Grid Load Collapse: Winter Storm Uri (February 2021)",
             fontsize=14, fontweight="bold", pad=12)
ax.set_ylabel("ERCOT Total Load (GW)", fontsize=11)
ax.set_xlabel("")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right", framealpha=0.9)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))

# Strip top/right spines for a cleaner look
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

plt.tight_layout()
out_path = VIS_DIR / "uri_load_collapse.png"
plt.savefig(out_path, dpi=160, bbox_inches="tight")
print(f"\n✓ Chart saved: {out_path}")