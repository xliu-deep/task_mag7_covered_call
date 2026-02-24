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

## Requirements

Python 3.10+ recommended.

Install common dependencies:

```bash
pip install numpy pandas scipy requests yfinance
```

If you run scripts that rely on ThetaData API, ensure ThetaData local gateway is available at:

`http://127.0.0.1:25503`

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
