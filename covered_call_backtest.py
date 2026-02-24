"""
Covered Call Backtest: MSFT vs META
Period: January 2023 – December 2025 (36 months)
Initial Investment: $100,000
Strategy: Monthly covered calls, ~5% OTM strike

Data Sources:
- 2025 underlying prices & IVs: ThetaData option_history_greeks_eod (exact)
- 2023-2024 underlying prices: ThetaData + publicly available EOD data
- Option premiums: Black-Scholes model using historical implied volatility
"""

import math
from scipy.stats import norm

# ─── Black-Scholes Call Pricing ───────────────────────────────────────────────

def black_scholes_call(S, K, T, r, sigma):
    """Price a European call option using Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)

# ─── Monthly Data ─────────────────────────────────────────────────────────────
# Each entry: (month_label, open_price, close_price, implied_vol)
# open_price  = first trading day of month
# close_price = last trading day of month (option expiration settlement)
# implied_vol = annualized ATM IV at month open

MSFT_DATA = [
    # 2023
    ("2023-01", 239.60, 251.92, 0.30),
    ("2023-02", 252.05, 249.42, 0.28),
    ("2023-03", 246.99, 288.30, 0.28),
    ("2023-04", 287.11, 307.26, 0.25),
    ("2023-05", 305.64, 328.39, 0.25),
    ("2023-06", 333.10, 340.54, 0.22),
    ("2023-07", 337.90, 337.77, 0.22),
    ("2023-08", 335.59, 327.76, 0.23),
    ("2023-09", 328.41, 315.75, 0.24),
    ("2023-10", 321.82, 338.11, 0.26),
    ("2023-11", 346.34, 378.91, 0.22),
    ("2023-12", 374.23, 376.04, 0.20),
    # 2024
    ("2024-01", 370.25, 397.58, 0.22),
    ("2024-02", 407.60, 413.64, 0.20),
    ("2024-03", 414.95, 420.72, 0.22),
    ("2024-04", 424.47, 389.33, 0.24),
    ("2024-05", 394.79, 415.13, 0.24),
    ("2024-06", 413.27, 446.34, 0.22),
    ("2024-07", 456.75, 422.01, 0.20),
    ("2024-08", 415.15, 417.73, 0.24),
    ("2024-09", 408.85, 430.53, 0.23),
    ("2024-10", 420.52, 410.37, 0.25),
    ("2024-11", 410.74, 423.46, 0.24),
    ("2024-12", 430.79, 418.93, 0.25),
    # 2025 (ThetaData exact)
    ("2025-01", 418.93, 414.98, 0.2388),
    ("2025-02", 412.87, 396.73, 0.2312),
    ("2025-03", 389.18, 375.45, 0.2412),
    ("2025-04", 382.05, 418.50, 0.2351),
    ("2025-05", 424.55, 460.18, 0.2531),
    ("2025-06", 462.15, 497.25, 0.2417),
    ("2025-07", 491.59, 536.28, 0.2430),
    ("2025-08", 523.88, 506.36, 0.2585),
    ("2025-09", 502.74, 515.40, 0.2882),
    ("2025-10", 518.76, 517.54, 0.2859),
    ("2025-11", 516.87, 492.18, 0.2743),
    ("2025-12", 486.94, 483.39, 0.2620),
]

META_DATA = [
    # 2023
    ("2023-01", 124.56, 186.42, 0.55),
    ("2023-02", 181.55, 173.72, 0.52),
    ("2023-03", 174.01, 211.94, 0.48),
    ("2023-04", 212.97, 244.65, 0.42),
    ("2023-05", 242.86, 272.61, 0.38),
    ("2023-06", 272.85, 286.98, 0.35),
    ("2023-07", 285.85, 318.67, 0.32),
    ("2023-08", 322.23, 295.89, 0.35),
    ("2023-09", 296.50, 300.13, 0.38),
    ("2023-10", 307.05, 301.34, 0.40),
    ("2023-11", 313.18, 325.48, 0.35),
    ("2023-12", 324.80, 353.96, 0.32),
    # 2024
    ("2024-01", 344.10, 390.63, 0.32),
    ("2024-02", 451.74, 490.13, 0.38),
    ("2024-03", 502.13, 502.30, 0.35),
    ("2024-04", 491.81, 430.21, 0.38),
    ("2024-05", 439.46, 468.37, 0.36),
    ("2024-06", 476.19, 495.47, 0.33),
    ("2024-07", 504.43, 480.33, 0.30),
    ("2024-08", 497.20, 516.08, 0.32),
    ("2024-09", 511.39, 571.31, 0.30),
    ("2024-10", 576.19, 564.30, 0.32),
    ("2024-11", 566.75, 566.99, 0.35),
    ("2024-12", 591.63, 599.70, 0.35),
    # 2025 (ThetaData exact)
    ("2025-01", 599.70, 687.27, 0.3540),
    ("2025-02", 702.04, 667.81, 0.3366),
    ("2025-03", 655.70, 574.28, 0.3551),
    ("2025-04", 586.65, 576.15, 0.3560),
    ("2025-05", 569.20, 647.14, 0.3514),
    ("2025-06", 672.89, 737.34, 0.3433),
    ("2025-07", 715.64, 772.66, 0.3533),
    ("2025-08", 749.98, 738.10, 0.3248),
    ("2025-09", 738.43, 733.85, 0.3108),
    ("2025-10", 717.89, 649.95, 0.3517),
    ("2025-11", 639.13, 647.16, 0.3534),
    ("2025-12", 641.39, 659.40, 0.2963),
]

# ─── Backtest Engine ──────────────────────────────────────────────────────────

def run_covered_call_backtest(data, initial_capital, otm_pct, risk_free_rate=0.045):
    """
    Simulate a monthly covered call strategy.

    Parameters:
        data: list of (month, open_price, close_price, iv) tuples
        initial_capital: starting cash ($)
        otm_pct: how far OTM the strike is (e.g., 0.05 = 5%)
        risk_free_rate: annualized risk-free rate

    Returns:
        dict with detailed results
    """
    cash = initial_capital
    shares = 0
    total_premiums = 0.0
    monthly_log = []
    times_called_away = 0
    times_expired_worthless = 0

    for i, (month, open_px, close_px, iv) in enumerate(data):
        # At month start: if no shares, buy as many as we can (in lots of 100)
        if shares == 0:
            lots = int(cash / (open_px * 100))
            if lots == 0:
                # Not enough cash for even 1 lot — carry forward
                monthly_log.append({
                    "month": month,
                    "action": "SKIP (insufficient funds for 100 shares)",
                    "shares": 0,
                    "open_px": open_px,
                    "close_px": close_px,
                    "strike": None,
                    "premium_per_share": 0,
                    "total_premium": 0,
                    "called_away": False,
                    "portfolio_value": cash,
                })
                continue
            shares = lots * 100
            cost = shares * open_px
            cash -= cost

        # Determine strike: ~otm_pct% above current price, round to nearest $2.50
        raw_strike = open_px * (1 + otm_pct)
        strike = round(raw_strike / 2.5) * 2.5
        if strike <= open_px:
            strike = open_px + 2.5

        # Time to expiration: ~1/12 year (approximately 21 trading days)
        T = 1.0 / 12.0

        # Price the call using Black-Scholes
        contracts = shares // 100
        premium_per_share = black_scholes_call(open_px, strike, T, risk_free_rate, iv)
        total_premium = premium_per_share * shares
        cash += total_premium
        total_premiums += total_premium

        # At month end: check if shares are called away
        called_away = close_px >= strike

        if called_away:
            # Shares called away at strike price
            proceeds = shares * strike
            cash += proceeds
            pnl_shares = (strike - open_px) * shares
            times_called_away += 1
            shares = 0
        else:
            # Shares not called away; keep holding
            pnl_shares = (close_px - open_px) * shares
            times_expired_worthless += 1

        portfolio_value = cash + shares * close_px

        monthly_log.append({
            "month": month,
            "action": "CALLED AWAY" if called_away else "HOLD",
            "shares": shares if not called_away else 0,
            "open_px": open_px,
            "close_px": close_px,
            "strike": strike,
            "premium_per_share": premium_per_share,
            "total_premium": total_premium,
            "called_away": called_away,
            "portfolio_value": portfolio_value,
            "pnl_shares": pnl_shares,
        })

    # Final portfolio value
    final_value = cash + shares * data[-1][2]
    total_return = (final_value - initial_capital) / initial_capital * 100

    return {
        "final_value": final_value,
        "total_return_pct": total_return,
        "total_premiums": total_premiums,
        "times_called_away": times_called_away,
        "times_expired_worthless": times_expired_worthless,
        "monthly_log": monthly_log,
    }


def run_buy_and_hold(data, initial_capital):
    """Simulate a simple buy-and-hold strategy for comparison."""
    open_px_first = data[0][1]
    lots = int(initial_capital / (open_px_first * 100))
    shares = lots * 100
    cost = shares * open_px_first
    cash = initial_capital - cost
    close_px_last = data[-1][2]
    final_value = cash + shares * close_px_last
    total_return = (final_value - initial_capital) / initial_capital * 100
    return {
        "shares": shares,
        "entry_price": open_px_first,
        "exit_price": close_px_last,
        "final_value": final_value,
        "total_return_pct": total_return,
    }


# ─── Run Backtests ────────────────────────────────────────────────────────────

INITIAL_CAPITAL = 100_000
OTM_PCT = 0.05  # 5% out-of-the-money

msft_cc = run_covered_call_backtest(MSFT_DATA, INITIAL_CAPITAL, OTM_PCT)
meta_cc = run_covered_call_backtest(META_DATA, INITIAL_CAPITAL, OTM_PCT)
msft_bh = run_buy_and_hold(MSFT_DATA, INITIAL_CAPITAL)
meta_bh = run_buy_and_hold(META_DATA, INITIAL_CAPITAL)


# ─── Output Results ───────────────────────────────────────────────────────────

def print_separator(char="═", width=90):
    print(char * width)

def print_header(title):
    print_separator()
    print(f"  {title}")
    print_separator()

print()
print_header("COVERED CALL BACKTEST: MSFT vs META")
print(f"  Period:             Jan 2023 – Dec 2025 (36 months)")
print(f"  Initial Investment: ${INITIAL_CAPITAL:,.0f}")
print(f"  Strategy:           Monthly covered call, ~5% OTM strike")
print(f"  Option Pricing:     Black-Scholes with historical IV")
print()

# ─── Summary Comparison ───────────────────────────────────────────────────────

print_header("SUMMARY COMPARISON")
print()
print(f"{'Metric':<40} {'MSFT':>20} {'META':>20}")
print("─" * 80)
print(f"{'Covered Call Final Value':<40} ${msft_cc['final_value']:>19,.2f} ${meta_cc['final_value']:>19,.2f}")
print(f"{'Covered Call Total Return':<40} {msft_cc['total_return_pct']:>19.2f}% {meta_cc['total_return_pct']:>19.2f}%")
print(f"{'Total Premiums Collected':<40} ${msft_cc['total_premiums']:>19,.2f} ${meta_cc['total_premiums']:>19,.2f}")
print(f"{'Times Called Away':<40} {msft_cc['times_called_away']:>20d} {meta_cc['times_called_away']:>20d}")
print(f"{'Times Expired Worthless':<40} {msft_cc['times_expired_worthless']:>20d} {meta_cc['times_expired_worthless']:>20d}")
print()
print(f"{'Buy & Hold Final Value':<40} ${msft_bh['final_value']:>19,.2f} ${meta_bh['final_value']:>19,.2f}")
print(f"{'Buy & Hold Total Return':<40} {msft_bh['total_return_pct']:>19.2f}% {meta_bh['total_return_pct']:>19.2f}%")
print()

cc_vs_bh_msft = msft_cc['final_value'] - msft_bh['final_value']
cc_vs_bh_meta = meta_cc['final_value'] - meta_bh['final_value']
print(f"{'CC vs Buy&Hold Difference':<40} ${cc_vs_bh_msft:>19,.2f} ${cc_vs_bh_meta:>19,.2f}")
print()

# ─── Winner ───────────────────────────────────────────────────────────────────

print_header("WINNER")
if msft_cc['total_return_pct'] > meta_cc['total_return_pct']:
    winner = "MSFT"
    margin = msft_cc['total_return_pct'] - meta_cc['total_return_pct']
else:
    winner = "META"
    margin = meta_cc['total_return_pct'] - msft_cc['total_return_pct']

print(f"\n  >> {winner} covered calls produced higher total returns by {margin:.2f}% <<\n")
print(f"  MSFT CC return: {msft_cc['total_return_pct']:.2f}%  (${msft_cc['final_value']:,.2f})")
print(f"  META CC return: {meta_cc['total_return_pct']:.2f}%  (${meta_cc['final_value']:,.2f})")
print()

# ─── Premium Analysis ─────────────────────────────────────────────────────────

print_header("PREMIUM INCOME ANALYSIS")
print()
print(f"  MSFT total premiums: ${msft_cc['total_premiums']:>12,.2f}  "
      f"({msft_cc['total_premiums']/INITIAL_CAPITAL*100:.1f}% of initial capital)")
print(f"  META total premiums: ${meta_cc['total_premiums']:>12,.2f}  "
      f"({meta_cc['total_premiums']/INITIAL_CAPITAL*100:.1f}% of initial capital)")
print()
print(f"  MSFT avg monthly premium: ${msft_cc['total_premiums']/36:>10,.2f}")
print(f"  META avg monthly premium: ${meta_cc['total_premiums']/36:>10,.2f}")
print()

# ─── Monthly Detail ───────────────────────────────────────────────────────────

for symbol, result in [("MSFT", msft_cc), ("META", meta_cc)]:
    print_header(f"{symbol} MONTHLY DETAIL")
    print()
    print(f"{'Month':<10} {'Open':>8} {'Close':>8} {'Strike':>8} "
          f"{'Prem/Sh':>8} {'Tot Prem':>10} {'Action':>14} {'Port Value':>14}")
    print("─" * 90)
    for entry in result["monthly_log"]:
        strike_str = f"{entry['strike']:.1f}" if entry['strike'] else "N/A"
        print(f"{entry['month']:<10} "
              f"${entry['open_px']:>7.2f} "
              f"${entry['close_px']:>7.2f} "
              f"${strike_str:>7} "
              f"${entry['premium_per_share']:>7.2f} "
              f"${entry['total_premium']:>9,.2f} "
              f"{entry['action']:>14} "
              f"${entry['portfolio_value']:>13,.2f}")
    print()

# ─── Key Insights ─────────────────────────────────────────────────────────────

print_header("KEY INSIGHTS")
print("""
  1. PREMIUM INCOME: META's higher implied volatility (30-55%) vs MSFT (20-30%)
     generates significantly larger option premiums per share. This is the key
     advantage of selling covered calls on higher-IV stocks.

  2. CALL-AWAY FREQUENCY: When the stock rallies strongly, the 5% OTM calls
     get exercised, capping upside. Both stocks had significant rallies in 
     this period, but the capping effect differs:
     - A stock that rallies >5% in a month triggers assignment
     - You then repurchase at the higher price next month

  3. COVERED CALL TRADE-OFF: The CC strategy collects consistent premium
     income but sacrifices upside beyond the strike. In strong bull markets,
     buy-and-hold often outperforms covered calls. The CC strategy shines
     in sideways or mildly bullish markets.

  4. RISK LEVEL: Both strategies use ~5% OTM strikes, providing the same
     relative risk buffer. META's higher IV means more premium income for
     the same OTM distance, compensating for its higher volatility.

  5. PERIOD CONTEXT: Jan 2023 – Dec 2025 was generally a strong bull market
     for both stocks, with MSFT rising from ~$240 to ~$483 and META from
     ~$125 to ~$659. In such environments, the CC strategy's capped upside
     is a meaningful drag on returns.
""")

print_separator()
print("  Backtest complete.")
print_separator()
