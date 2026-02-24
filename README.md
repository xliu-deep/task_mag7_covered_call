# Mag7 Covered Call Research

Backtesting and analysis toolkit for a covered call overlay strategy on the Magnificent 7 stocks:

- `AAPL`
- `MSFT`
- `GOOGL`
- `AMZN`
- `NVDA`
- `META`
- `TSLA`

The project focuses on monthly covered calls from 2021 to 2025, comparing:

- Buy-and-hold return
- Option premium income
- Assignment cost
- Net covered-call overlay contribution
- Delta optimization by stock

## Motivation

This project starts from personal interest in the covered call strategy and a practical question:

- Can covered calls generate a stable cash flow on top of long-term Mag7 holdings?
- Is that cash flow meaningful after assignment costs, not just gross premium?
- What parameter set (especially target delta) is most effective for each stock?

In short, the research goal is to test whether "earning cash flow via CC" is truly feasible in a full market cycle, and to identify the best parameters rather than relying on a one-size-fits-all rule.

## Project Structure

Core scripts:

- `cc_backtest_real_data.py`: Main real-data backtest using ThetaData option chain data plus Yahoo Finance stock prices.
- `mag7_cc_overlay.py`: Deterministic covered-call overlay engine with built-in monthly data and Black-Scholes pricing.
- `mag7_optimal_strategy.py`: Delta optimization and best-parameter exploration.
- `mag7_delta_backtest.py`, `mag7_delta_sweep.py`: Delta-focused scenario and parameter sweeps.
- `covered_call_backtest.py`, `cc_backtest_v2.py`, `cc_backtest_v3.py`: Earlier/alternative backtest versions.

Reports and outputs:

- `Mag7_CC_Report_Visual.md`: Detailed strategy report and interpretation.
- `Mag7_CC_Final.html`, `Mag7_CC_Final_RealData.html`, `Mag7_CC_Dashboard.html`, `Mag7_CC_报告.html`: HTML reports and dashboard views.
- `cc_real_data_results.json`, `cc_real_data_results_v2.json`, `cc_real_data_results_v3.json`: Saved result datasets.
- `cc_v2_cache.json`, `cc_v3_cache.json`: Cache files used by some scripts.

## Strategy Model

The model treats covered calls as an **overlay** on a long equity position:

1. Buy and hold stock shares.
2. Sell monthly OTM call options at target delta.
3. Track net contribution:

`Net CC Overlay = Premiums Collected - Assignment Costs`

The total strategy return is:

`Total Return = Buy & Hold Return + Net CC Overlay`

## Backtest Results (2021-2025)

### Main conclusion

Yes, generating CC cash flow is feasible, but effectiveness is stock-dependent and parameter-dependent.

- At optimized delta, all 7 stocks show positive net CC overlay in this backtest window.
- CC works best in flat/bear or mild-bull regimes; strong rallies can hurt due to assignment cost.
- "Best delta" is not universal and should be calibrated per stock.

### Best parameter and outcome by stock

| Stock | Optimal Delta | Net CC Overlay | Combined Return (B&H + CC) |
|-------|---------------|----------------|------------------------------|
| AAPL  | 0.08          | +12.0%         | +97.3%                       |
| MSFT  | 0.18          | +13.6%         | +118.0%                      |
| GOOGL | 0.10          | +23.5%         | +134.3%                      |
| AMZN  | 0.35          | +37.7%         | +71.7%                       |
| NVDA  | 0.18          | +119.1%        | +1056.3%                     |
| META  | 0.18          | +23.7%         | +139.6%                      |
| TSLA  | 0.25          | +4.0%          | +58.4%                       |

### Practical interpretation

- Strong candidate: `AMZN` (high CC efficiency in this sample).
- High income but high variance: `NVDA`.
- Limited incremental benefit: `TSLA` (high premium but also high assignment drag).
- More conservative profile: `AAPL` / `MSFT` with relatively lower target delta.


## Quick Start

Run the real-data backtest:

```bash
python cc_backtest_real_data.py
```

Run the model-based overlay backtest:

```bash
python mag7_cc_overlay.py
```

## Notes

- This repository is for research/education and strategy exploration.
- Historical results do not guarantee future performance.
- Real trading requires transaction-cost, liquidity, and execution-risk handling.
