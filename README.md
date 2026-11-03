# Did the Denver Campaign Work? A Quasi-Experimental Impact Analysis

Measuring the revenue impact of a single-market marketing campaign, using Bayesian structural time series (Google's CausalImpact), difference-in-differences, and synthetic control.

> **All data are simulated.** "BrewwwwHaven Coffee & Home Brewing" is a fictional company. Market names are real US metros for realism only. No real company data is used.

## The business question

BrewwwwHaven operates stores in 13 US metro markets. From **2025-09-08 to 2025-10-19** it ran a 6-week TV, digital and out-of-home campaign in **Denver only** ($200,000 media spend). There was no randomized holdout. Leadership wants to know:

1. How much additional revenue did the campaign cause in Denver?
2. Did it pay back its cost? (58% gross margin on incremental sales, so break-even is **$344,828** of incremental revenue.
3. Should the campaign run in other markets?

## Payback assumptions

The break-even point rests on two inputs that come from the project setup, not from the analysis:

| Input | Value | Source |
|---|---|---|
| Media spend | $200,000 | Stated campaign cost |
| Gross margin on incremental sales | 58% | Simplifying assumption (not estimated from the data) |

**Break-even = spend ÷ margin = $200,000 ÷ 0.58 = $344,828 of incremental revenue.** Each extra dollar of revenue keeps only 58 cents as gross profit, so the campaign needs about $344,828 of extra revenue to earn back $200,000. Net profit throughout this README is calculated as incremental revenue × 58% − $200,000.

- **Sensitivity:** the break-even moves with the margin. At a 50% margin it would be $400,000, and at 65% it would be $307,692.
- **Scope:** only media spend is counted as cost. Creative production, staff time and other campaign costs are not included.

## Why not just compare before and after?

Denver's revenue rose **15.1%** across the campaign window versus the six weeks before it. But the other markets, which saw no campaign, rose **5.0%** over the same weeks because of seasonality, weather and a chain-wide promotion that overlapped the last two weeks. A raw before/after comparison credits the campaign with changes that happened everywhere. The goal is to estimate what Denver would have done *without* the campaign (the counterfactual) and compare it with what actually happened.

## Data

Synthetic daily revenue for 13 markets (generated using Claude), 2024-01-01 to 2025-12-31 (the analysis uses data through 2025-10-19).

| File | Contents |
|---|---|
| `data/sales_daily_long.csv` | One row per market per day: revenue, transactions, store count, temperature, precipitation, local promo flag, ad spend |
| `data/sales_daily_wide_revenue.csv` | Daily revenue, one column per market (Denver first) |
| `data/markets.csv` | Market metadata: region, store count, distance from Denver |
| `data/national_calendar.csv` | Holidays, chain-wide promotions, consumer confidence index |
| `data/ci_primary.csv`, `ci_broad.csv`, `ci_strict.csv` | Model-ready datasets written by the script (Denver in the first column) |

The data include realistic confounders: weekly and annual seasonality, named holidays, chain-wide promos, local promos, weather, macro drift, and a campaign effect that builds and fades gradually rather than switching on and off.

## Approach

| Step | What was done |
|---|---|
| **1. Frame** | Defined the treated unit (Denver), outcome (daily revenue), pre-period (2024-01-01 to 2025-09-07), primary post-period (the 42 campaign days), and the break-even |
| **2. Explore** | Checked data quality, compared Denver with controls week by week, listed events overlapping the campaign |
| **3. Choose controls** | Applied four questions to each market: could the campaign have touched it, is its data intact, did it track Denver before, is it clean during the campaign window? |
| **4. CausalImpact** | Fit a Bayesian structural time-series model (weekly seasonality, regression on controls) on three control sets |
| **5. Tune** | Tested how much the answer depends on how freely the model lets Denver's baseline drift |
| **6. Cross-check** | Difference-in-differences and synthetic control, plus a placebo-in-space test (each control treated as if it had the campaign) |

### Control selection

| Market | Decision | Reason |
|---|---|---|
| CMH, BNA, CLT, SMF, MCI, MSP | Kept | No issues found on any of the four questions |
| SLC | Kept | A 5-day data outage (2025-05-12 to 05-16) was linearly interpolated |
| COS (Colorado Springs) | Excluded from Primary | Adjacent to Denver, so spillover is plausible. A check of its campaign-window lift was inconclusive (+1.3% average, 4th of 11 markets), and it can only detect spillover above about 6%, so it could not be cleared. Excluding it costs little |
| PDX (Portland) | Excluded everywhere | A new store opened 2025-03-17, creating a break in its revenue that neither raw nor per-store revenue repairs |
| IND, PHX, PIT | Excluded from Primary | Ran their own local promotions inside the campaign window (about 0.5% to 1.2% of window revenue) |

Three control sets were used: **Primary** (SLC, MCI, MSP, CMH, BNA, CLT, SMF), **Broad** (all 11 markets except Denver and Portland), and **Strict** (CMH, BNA, CLT, SMF).

## Results

The campaign **very likely raised revenue** (about +8% to +12% in the campaign window) and **probably paid for itself, but the margin is thin**. Estimates of incremental revenue run from about $340k to $490k against a $344,828 break-even.

### By method (campaign window, Primary controls unless noted)

| Method | Incremental revenue | Lift | Net profit at 58% margin |
|---|---|---|---|
| **CausalImpact (Primary)** | **$465k** (95% interval $302k to $649k) | 11.4% | about +$70k |
| CausalImpact (Broad) | $405k ($272k to $538k) | 9.8% | about +$35k |
| CausalImpact (Strict) | $487k ($320k to $661k) | 12.0% | about +$82k |
| Difference-in-differences | $362k | 8.6% | about +$10k |
| Difference-in-differences (last 26 pre-weeks) | $343k | 8.1% | about -$1k |
| Synthetic control | $369k | 8.8% | about +$14k |

- CausalImpact's posterior probability of a real effect is above 99.9%.
- Every method's range contains the others' point estimates, so they agree on the big picture.
- Synthetic control weights (Primary): SLC 0.02, MCI 0.18, MSP 0.16, CMH 0.28, BNA 0.06, CLT 0.19, SMF 0.11. Pre-campaign fit error is about 2.8% per week.

### Sensitivity to the baseline setting (CausalImpact, Primary)

CausalImpact lets the baseline level drift over time, controlled by `prior_level_sd`. The answer is sensitive to it:

| Setting | Incremental revenue | 95% interval |
|---|---|---|
| Default (0.01), two repeat runs | $471k and $479k | $275k to $660k, $302k to $667k |
| Stiffer baseline (0.001) | $343k | $269k to $416k |
| Looser baseline (0.05), two runs | $494k and $506k | about $209k to $791k and $216k to $805k |

Run-to-run noise in the default setting is about $8k for the point estimate and about $27k for the lower bound, so differences smaller than that are not meaningful. A stiffer baseline narrows the interval by about 60% and puts the estimate almost exactly on the break-even line, which is why payback is reported as "likely" and not "certain."

### Placebo in space (fake datasets for comparison)

Each Primary control was treated as if it had received the campaign, using the remaining six as its comparison.

| | Fake-treated controls | Denver (real) |
|---|---|---|
| Difference-in-differences | -3.9% to +3.0% | **+8.6%** |
| Synthetic control | -2.3% to +2.6% | **+8.8%** |

Denver ranks first of eight under both methods, roughly three times the largest fake effect, and the fake effects average out to about zero. With only eight units this is evidence that Denver stands out, not a formal significance test.

## Recommendation

The evidence supports a **conditional yes**: the campaign paid back modestly in Denver, but the margin is thin and the estimate depends on modeling choices. Before spending more, run the next market launch with a **randomized holdout** (some stores or regions deliberately left out) to measure the effect cleanly.

## Limitations

- **The baseline setting changes the conclusion.** Only the default and two alternatives were compared, and I did not verify which is best calibrated, so the result is reported as a range.
- **The campaign window only.** The primary post-period is the 42 campaign days. Carryover after the campaign ended is not estimated here, so the primary window is conservative.
- **One treated market and one campaign.** The result is evidence for Denver, not a forecast for other markets with different size, demographics and media mix.
- **Simulated data.** Real data would bring messier confounders, and the controls' independence from the campaign cannot be fully verified in practice.

## What this project demonstrates

- Framing a business question as a causal estimand, with a decision rule (break-even) defined before modeling
- Choosing controls with explicit, documented criteria instead of relying on correlation alone
- Estimating a counterfactual with a Bayesian structural time-series model, and checking how sensitive it is to its own settings
- Cross-checking with two independent methods and a placebo-in-space test
- Translating statistical output into a profit-based recommendation
