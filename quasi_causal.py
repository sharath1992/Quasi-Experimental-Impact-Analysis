### import packages ###

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from causalimpact import CausalImpact
import os, time
from scipy.optimize import minimize


### Read all the data ###

# Daily long format data

long = pd.read_csv("data/sales_daily_long.csv", parse_dates=["date"])

# Markets

markets = pd.read_csv("data/markets.csv")

# Calendar (Holidays)

cal = pd.read_csv("data/national_calendar.csv", parse_dates=["date"])

# Wide format daily data

wide = pd.read_csv("data/sales_daily_wide_revenue.csv", parse_dates=["date"]).set_index("date")


### Define campaign dates ###

# End of Pre Period

PRE_END = pd.Timestamp("2025-09-07")

# Campaign Start

CAMP_START = pd.Timestamp("2025-09-08")

# Campaign End

CAMP_END = pd.Timestamp("2025-10-19")


### Quick Data Exploration ###

# Shape and structure

print(f"Shape: {long.shape}")
print(f"Min Date: {long.date.min().date()} and Max Date: {long.date.max().date()}")
print(f"What are the markets? {markets}")
print(f"Markets length - are they same? {long.groupby("market").size()}")
print(f"Any missing values? {long.isna().sum()}")

# Resample daily data to weekly and visualize to see how Denver differs from controls (meaning other markets)

weekly = wide.resample("W").sum()

pre_mean = weekly[weekly.index <= PRE_END].mean()
x = weekly / pre_mean * 100

controls = [c for c in x.columns if c != "DEN"]

fig, ax  = plt.subplots(figsize=(12,6))
ax.plot(x.index, x[controls].mean(axis=1), label="Avg of Controls", color="gray")
ax.plot(x.index, x["DEN"], label="Denver", color="blue", lw=3)
ax.axvspan(CAMP_START, CAMP_END, alpha=0.15, color="orange", label="Campaign")
ax.set_ylabel("Weekly revenue")
ax.legend()
plt.show()


# Campaign Period Change - Denver vs Others

prior_start = CAMP_START - pd.Timedelta(days=42)

prior = wide.loc[prior_start:CAMP_START - pd.Timedelta(days=1)].sum()

camp = wide.loc[CAMP_START:CAMP_END].sum()

chg = (camp / prior - 1) * 100

print(f"Denver change: {chg['DEN']:.2f}%")
print(f"Controls change: {chg[controls].mean():.2f}%")

# Correlation between Denver and other controls

pre = np.log(wide.loc[:PRE_END].interpolate())

corr_level = pre.corr()["DEN"].drop("DEN")

corr_chg = pre.diff(7).dropna().corr()["DEN"].drop("DEN")

print(pd.DataFrame({"level": corr_level, "7d change": corr_chg}).sort_values("7d change", ascending=False).round(2))

# Events overlapping with campaign dates

print(cal[cal.national_promo_flag == 1].groupby("national_promo_name").date.agg(["min", "max"]))

den = long[long.market == "DEN"]

print(den[den.local_promo_flag == 1].date.agg(["min", "max"]))


### Produce clean and model-ready data ###
 
# COS being close to DEN, we check if COS saw a lift relative to the other controls (Spillover)

wide["SLC"] = wide["SLC"].interpolate(limit = 7)

BASE_EXCLUDE = ["DEN", "PDX"]   # remove PDX because a new store was opened here right at the beginning of the campaign which might alter its results

def rel_to_rest(market, exclude):
    rest = [c for c in weekly.columns if c not in exclude + [market]]
    r = np.log(weekly[market] / weekly[rest].mean(axis=1))
    return r - r[:PRE_END].mean(), rest


# COS vs rest

cos, pool = rel_to_rest("COS", BASE_EXCLUDE + ["COS"])
print("Comparison pool for COS:", pool)

# DEN vs rest

rest = [c for c in weekly.columns if c not in BASE_EXCLUDE + ["COS"]]
den = np.log(weekly["DEN"] / weekly[rest].mean(axis=1))
den = den - den[:PRE_END].mean()

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(den["2025-01-01":].index, den["2025-01-01":], label="Denver", color="tab:blue", lw=2)
ax.plot(cos["2025-01-01":].index, cos["2025-01-01":], label="Colorado Springs", color="tab:red", lw=2)
ax.axhline(0, color="gray", lw=1)
ax.axvspan(CAMP_START, CAMP_END, alpha=0.15, color="tab:orange", label="Campaign")
ax.set_ylabel("Weekly revenue relative to other controls\n(log ratio, 0 = pre-period norm)")
ax.legend()
plt.tight_layout()
plt.show()

def summarize(series):
    pre_sd = series[:PRE_END].std()
    camp = series[CAMP_START:CAMP_END]
    return pd.Series(
        {
            "pre_weekly_sd": pre_sd,
            "camp_avg_shift": camp.mean(),
            "shift_in_sd_units": camp.mean() / pre_sd,
            "first3wk_shift": camp.iloc[:3].mean(),
            "last3wk_shift": camp.iloc[3:].mean()
        }
    )

print("Weekly values during the campaign DEN vs COS")
print(pd.DataFrame(
    {
        "DEN": den[CAMP_START:CAMP_END],
        "COS": cos[CAMP_START:CAMP_END]
    }
).round(3))

# Does COS stand out given its proximity to DEN

rows = {}
for m in [c for c in weekly.columns if c not in BASE_EXCLUDE]:
    s, _ = rel_to_rest(m, BASE_EXCLUDE + (["COS"] if m != "COS" else []))
    rows[m] = summarize(s)
table = pd.DataFrame(rows).T.sort_values("shift_in_sd_units", ascending=False)
print("\nCampaign-window shift for every control (each vs. the rest):")
print(table.round(3))
print("\nDenver for reference:")
print(summarize(den).round(3))

# Create 3 datasets

rev = long.pivot(index="date", columns="market", values="revenue")
rev["SLC"] = rev["SLC"].interpolate(limit=7)

PRIMARY = ["SLC","MCI", "MSP", "CMH", "BNA", "CLT", "SMF"]
STRICT = ["CMH", "BNA", "CLT", "SMF"]
BROAD = [c for c in rev.columns if c not in ("DEN", "PDX")]

def make(controls):
    return pd.concat([rev["DEN"], rev[controls]], axis=1).loc[:CAMP_END]

sets = {"primary": make(PRIMARY), "strict": make(STRICT), "broad": make(BROAD)}

for k, df in sets.items():
    df.reset_index().to_csv(f"data/ci_{k}.csv", index=False)


### Causal Impact Runs on the created datasets ###

PRE  = ["2024-01-01", "2025-09-07"]
POST = ["2025-09-08", "2025-10-19"]

BASE_ARGS  = {"n_seasons": 7}

BREAK_EVEN = 344828

# Primary

prim = pd.read_csv("data/ci_primary.csv", parse_dates=["date"]).set_index("date")

ci = CausalImpact(prim, PRE, POST, model_args={"n_seasons":7})

print("CI Results on Primary Dataset\n")

ci.plot()

print(ci.summary())

# Broad

broad = pd.read_csv("data/ci_broad.csv", parse_dates=["date"]).set_index("date")

ci = CausalImpact(broad, PRE, POST, model_args={"n_seasons":7})

print("CI Results on Broad Dataset\n")

ci.plot()

print(ci.summary())

# Strict

strict = pd.read_csv("data/ci_strict.csv", parse_dates=["date"]).set_index("date")

ci = CausalImpact(strict, PRE, POST, model_args={"n_seasons":7})

print("CI Results on Strict Dataset\n")

ci.plot()

print(ci.summary())

# Test against stiffer and looser baselines to see how it impacts the primary dataset results

results = []

def run(data, label, **model_args):
    ci = CausalImpact(data, PRE, POST, model_args=model_args or None)

    print(f"\n=== {label} ===")

    print(ci.summary())

    inf = ci.inferences

    try:
        eff = inf["post_cum_effects_means"].iloc[-1]
        lo = inf["post_cum_effects_lower"].iloc[-1]
        hi = inf["post_cum_effects_upper"].iloc[-1]
        results.append(
            {"run": label, "effect": eff, "lower": lo, "upper": hi, "width": hi-lo, "lower_above_break_even": lo > BREAK_EVEN}
        )

    except KeyError:
        print("Could not return numbers")

    return ci

# Baseline

run(prim, "1a. Baseline",**BASE_ARGS)

# Stiffer Baseline

run(prim, "2. Stiffer baseline (0.001)", **BASE_ARGS, prior_level_sd=0.001)

# Looser baseline

run(prim, "3. Looser baseline (0.05)",   **BASE_ARGS, prior_level_sd=0.05)


### Difference in Difference ###

wk = rev[["DEN"] + PRIMARY].loc[:CAMP_END].resample("W").sum()

pr = wk.loc[:PRE_END]

def did(treated, controls, pre_weeks=None):
    rel = np.log(wk[treated]) - np.log(wk[controls]).mean(axis=1)
    base = rel.loc[:PRE_END]

    if pre_weeks:
        base = base.iloc[-pre_weeks:]

    lift = rel.loc[CAMP_START:CAMP_END].mean() - base.mean()

    actual = wk[treated].loc[CAMP_START:CAMP_END].sum()

    cf = actual / np.exp(lift)

    return {"effect": actual - cf, "rel": actual / cf -1}

print("DiD, all pre-period weeks :", {k: round(v, 3) for k, v in did("DEN", PRIMARY).items()})
print("DiD, last 26 pre-weeks    :", {k: round(v, 3) for k, v in did("DEN", PRIMARY, 26).items()})

rel = np.log(wk["DEN"]) - np.log(wk[PRIMARY]).mean(axis=1)
rel = rel - rel.loc[:PRE_END].mean()
ax = rel.plot(figsize=(11, 4), title="Denver vs. average control (log and centered on pre-period mean)")
ax.axvspan(CAMP_START, CAMP_END, alpha=0.15, color="orange")
ax.axhline(0, color="gray")
plt.show()


### Synthetic Control ###

def synth(treated, controls):

    # put every market on the same cale

    x = wk[[treated] + controls] / pr[[treated] + controls].mean()

    # Look at values before the campaign

    y, X = x[treated].loc[:PRE_END].values, x[controls].loc[:PRE_END].values

    k = len(controls)

    # find the best weights for each market

    res = minimize(lambda w: np.sum((y - X @ w) ** 2), np.ones(k) / k, method="SLSQP",
                   bounds=[(0, 1)] * k, constraints={"type": "eq", "fun": lambda w: w.sum() - 1})
    
    w = res.x

    # use the weights for data during the campaign

    cf = (x[controls].loc[CAMP_START:CAMP_END].values @ w) * pr[treated].mean()   

    actual = wk[treated].loc[CAMP_START:CAMP_END].values

    # make the real Denver comparison to the fake set created using weights

    return w, {"effect": (actual - cf).sum(), "rel": actual.sum() / cf.sum() - 1,
               "pre_fit_error": np.sqrt(res.fun / len(y))}, cf

w, out, cf = synth("DEN", PRIMARY)

print("Synthetic controls weights:", dict(zip(PRIMARY, w.round(2))))
print("Synthetic control result:", {k: round(v,3) for k,v in out.items()})

# compare DiD to Synthetic Control

ctrls = [c for c in PRIMARY]
plc = pd.DataFrame({
    "DiD": {m: did(m, [c for c in ctrls if c != m])["rel"] for m in ctrls},
    "SC":  {m: synth(m, [c for c in ctrls if c != m])[1]["rel"] for m in ctrls}})
plc.loc["DEN (real)"] = [did("DEN", PRIMARY)["rel"], out["rel"]]
print("\nRelative effect, fake-treated controls vs. Denver:\n", plc.round(3))