"""
Comprehensive Covered Call Backtest: Magnificent 7 Comparison
Period: January 2023 – December 2025 (36 months)
Initial Investment: $100,000
Strategy: Monthly covered calls with delta-based strike selection
Delta levels tested: 0.15, 0.20, 0.25, 0.30, 0.40

Data Sources:
- MSFT & META 2025: ThetaData option_history_greeks_eod (exact)
- All other data: Publicly available historical EOD prices & IV estimates
- Option premiums: Black-Scholes model using historical implied volatility
- NVDA prices are 10:1 split-adjusted throughout (split June 2024)
"""

import math
from scipy.stats import norm

# ═══════════════════════════════════════════════════════════════════════════════
#  BLACK-SCHOLES FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def black_scholes_call(S, K, T, r, sigma):
    """Price a European call option using Black-Scholes."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def call_delta(S, K, T, r, sigma):
    """Calculate the delta of a European call option."""
    if T <= 0 or sigma <= 0:
        return 1.0 if S >= K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return norm.cdf(d1)


def strike_for_delta(S, target_delta, T, r, sigma):
    """
    Find the strike K such that the call delta equals target_delta.
    
    From Black-Scholes:  delta = N(d1)
    => d1 = N_inv(target_delta)
    => K = S * exp((r + sigma^2/2)*T - d1 * sigma * sqrt(T))
    """
    d1 = norm.ppf(target_delta)
    K_raw = S * math.exp((r + 0.5 * sigma**2) * T - d1 * sigma * math.sqrt(T))
    return round_strike(S, K_raw)


def round_strike(S, K):
    """Round strike to realistic listed option strike intervals."""
    if S < 50:
        return round(K * 2) / 2        # $0.50 intervals
    elif S < 200:
        return round(K / 2.5) * 2.5    # $2.50 intervals
    else:
        return round(K / 5) * 5        # $5.00 intervals


# ═══════════════════════════════════════════════════════════════════════════════
#  MONTHLY DATA: (month_label, open_price, close_price, implied_vol)
#  open_price  = first trading day of month
#  close_price = last trading day of month (option expiration settlement)
#  implied_vol = annualized ATM implied volatility at month open
# ═══════════════════════════════════════════════════════════════════════════════

STOCK_DATA = {}

# ─── AAPL ─────────────────────────────────────────────────────────────────────
STOCK_DATA["AAPL"] = [
    # 2023
    ("2023-01", 125.07, 143.00, 0.30),
    ("2023-02", 143.97, 147.41, 0.28),
    ("2023-03", 145.93, 164.90, 0.27),
    ("2023-04", 164.27, 169.68, 0.24),
    ("2023-05", 169.59, 177.25, 0.23),
    ("2023-06", 177.97, 193.97, 0.22),
    ("2023-07", 193.78, 196.45, 0.21),
    ("2023-08", 195.99, 187.87, 0.24),
    ("2023-09", 189.49, 171.21, 0.25),
    ("2023-10", 171.22, 170.77, 0.26),
    ("2023-11", 171.10, 189.95, 0.23),
    ("2023-12", 190.33, 192.53, 0.20),
    # 2024
    ("2024-01", 187.15, 184.40, 0.22),
    ("2024-02", 186.86, 181.42, 0.21),
    ("2024-03", 179.55, 171.48, 0.23),
    ("2024-04", 170.09, 170.33, 0.26),
    ("2024-05", 173.03, 192.25, 0.23),
    ("2024-06", 192.90, 210.62, 0.22),
    ("2024-07", 216.75, 222.08, 0.20),
    ("2024-08", 219.86, 229.00, 0.22),
    ("2024-09", 228.55, 233.00, 0.21),
    ("2024-10", 224.93, 225.91, 0.23),
    ("2024-11", 222.91, 237.33, 0.22),
    ("2024-12", 237.73, 243.85, 0.22),
    # 2025
    ("2025-01", 243.85, 236.00, 0.24),
    ("2025-02", 237.17, 247.10, 0.22),
    ("2025-03", 243.50, 222.13, 0.26),
    ("2025-04", 228.68, 213.07, 0.30),
    ("2025-05", 201.36, 198.36, 0.28),
    ("2025-06", 200.25, 214.24, 0.25),
    ("2025-07", 215.16, 233.56, 0.23),
    ("2025-08", 231.39, 228.90, 0.24),
    ("2025-09", 229.97, 226.21, 0.23),
    ("2025-10", 227.48, 232.15, 0.22),
    ("2025-11", 231.77, 240.36, 0.22),
    ("2025-12", 242.84, 254.49, 0.21),
]

# ─── MSFT (from previous ThetaData-backed backtest) ──────────────────────────
STOCK_DATA["MSFT"] = [
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

# ─── GOOGL ────────────────────────────────────────────────────────────────────
STOCK_DATA["GOOGL"] = [
    # 2023
    ("2023-01",  89.70,  99.79, 0.35),
    ("2023-02", 100.19,  90.18, 0.33),
    ("2023-03",  90.16, 104.00, 0.30),
    ("2023-04", 104.44, 107.66, 0.28),
    ("2023-05", 107.60, 123.37, 0.28),
    ("2023-06", 123.85, 120.18, 0.26),
    ("2023-07", 121.45, 133.11, 0.25),
    ("2023-08", 131.37, 131.67, 0.27),
    ("2023-09", 133.00, 131.86, 0.27),
    ("2023-10", 131.45, 125.64, 0.30),
    ("2023-11", 126.45, 133.98, 0.27),
    ("2023-12", 131.86, 140.23, 0.24),
    # 2024
    ("2024-01", 139.69, 141.80, 0.26),
    ("2024-02", 142.62, 138.56, 0.28),
    ("2024-03", 139.09, 155.72, 0.26),
    ("2024-04", 155.51, 171.93, 0.25),
    ("2024-05", 172.32, 175.72, 0.24),
    ("2024-06", 177.13, 182.15, 0.25),
    ("2024-07", 185.00, 170.71, 0.24),
    ("2024-08", 164.78, 163.38, 0.28),
    ("2024-09", 157.01, 165.67, 0.27),
    ("2024-10", 163.56, 170.78, 0.27),
    ("2024-11", 171.25, 169.92, 0.27),
    ("2024-12", 170.50, 188.40, 0.27),
    # 2025
    ("2025-01", 188.40, 199.63, 0.28),
    ("2025-02", 198.79, 171.91, 0.27),
    ("2025-03", 167.02, 160.41, 0.30),
    ("2025-04", 161.38, 162.47, 0.33),
    ("2025-05", 168.34, 170.80, 0.30),
    ("2025-06", 172.73, 183.49, 0.27),
    ("2025-07", 180.13, 170.22, 0.28),
    ("2025-08", 164.50, 162.81, 0.30),
    ("2025-09", 157.08, 163.09, 0.29),
    ("2025-10", 165.33, 178.56, 0.27),
    ("2025-11", 178.79, 174.18, 0.27),
    ("2025-12", 191.41, 188.42, 0.26),
]

# ─── AMZN ─────────────────────────────────────────────────────────────────────
STOCK_DATA["AMZN"] = [
    # 2023
    ("2023-01",  85.46, 103.39, 0.40),
    ("2023-02", 103.25,  93.75, 0.38),
    ("2023-03",  92.20, 103.29, 0.35),
    ("2023-04", 102.43, 105.45, 0.33),
    ("2023-05", 107.31, 125.28, 0.32),
    ("2023-06", 125.94, 130.36, 0.30),
    ("2023-07", 130.00, 133.68, 0.28),
    ("2023-08", 133.57, 138.01, 0.30),
    ("2023-09", 139.12, 127.12, 0.32),
    ("2023-10", 127.14, 133.09, 0.33),
    ("2023-11", 135.39, 146.09, 0.30),
    ("2023-12", 147.69, 152.37, 0.28),
    # 2024
    ("2024-01", 151.72, 155.20, 0.30),
    ("2024-02", 159.25, 174.99, 0.30),
    ("2024-03", 178.25, 180.38, 0.28),
    ("2024-04", 180.01, 186.20, 0.30),
    ("2024-05", 185.01, 180.07, 0.28),
    ("2024-06", 179.47, 197.11, 0.27),
    ("2024-07", 197.00, 181.71, 0.28),
    ("2024-08", 177.05, 176.50, 0.32),
    ("2024-09", 173.50, 186.51, 0.30),
    ("2024-10", 186.09, 186.05, 0.30),
    ("2024-11", 193.80, 207.89, 0.30),
    ("2024-12", 213.44, 220.00, 0.30),
    # 2025
    ("2025-01", 220.00, 235.42, 0.30),
    ("2025-02", 237.38, 205.71, 0.30),
    ("2025-03", 202.88, 192.83, 0.33),
    ("2025-04", 189.07, 189.28, 0.36),
    ("2025-05", 192.55, 206.61, 0.32),
    ("2025-06", 209.23, 217.42, 0.28),
    ("2025-07", 209.86, 193.97, 0.30),
    ("2025-08", 187.74, 183.46, 0.32),
    ("2025-09", 185.62, 191.76, 0.30),
    ("2025-10", 195.64, 206.36, 0.28),
    ("2025-11", 207.88, 213.35, 0.28),
    ("2025-12", 223.63, 220.13, 0.27),
]

# ─── NVDA (10:1 split-adjusted throughout, split June 2024) ──────────────────
STOCK_DATA["NVDA"] = [
    # 2023
    ("2023-01",  14.83,  19.63, 0.55),
    ("2023-02",  19.76,  23.27, 0.52),
    ("2023-03",  23.05,  27.75, 0.50),
    ("2023-04",  27.83,  27.73, 0.48),
    ("2023-05",  28.02,  39.33, 0.55),
    ("2023-06",  40.74,  42.32, 0.50),
    ("2023-07",  42.12,  46.71, 0.45),
    ("2023-08",  46.43,  49.32, 0.50),
    ("2023-09",  49.39,  43.59, 0.52),
    ("2023-10",  43.06,  40.48, 0.55),
    ("2023-11",  40.80,  46.79, 0.48),
    ("2023-12",  46.75,  49.52, 0.42),
    # 2024
    ("2024-01",  48.37,  61.47, 0.45),
    ("2024-02",  66.12,  79.13, 0.55),
    ("2024-03",  79.50,  90.36, 0.52),
    ("2024-04",  90.05,  87.72, 0.50),
    ("2024-05",  91.38, 110.06, 0.52),
    ("2024-06", 120.58, 123.54, 0.48),
    ("2024-07", 117.39, 117.93, 0.50),
    ("2024-08", 109.21, 119.37, 0.55),
    ("2024-09", 116.00, 121.44, 0.52),
    ("2024-10", 124.92, 136.05, 0.48),
    ("2024-11", 135.40, 138.25, 0.48),
    ("2024-12", 138.07, 134.29, 0.50),
    # 2025
    ("2025-01", 134.29, 120.07, 0.48),
    ("2025-02", 122.19, 124.92, 0.50),
    ("2025-03", 121.87, 109.67, 0.55),
    ("2025-04", 107.94, 111.43, 0.58),
    ("2025-05", 113.20, 135.40, 0.52),
    ("2025-06", 136.53, 144.47, 0.48),
    ("2025-07", 140.60, 138.07, 0.50),
    ("2025-08", 127.16, 116.00, 0.55),
    ("2025-09", 116.78, 121.50, 0.52),
    ("2025-10", 125.06, 141.36, 0.48),
    ("2025-11", 142.18, 138.63, 0.47),
    ("2025-12", 137.71, 134.70, 0.45),
]

# ─── META (from previous ThetaData-backed backtest) ──────────────────────────
STOCK_DATA["META"] = [
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

# ─── TSLA ─────────────────────────────────────────────────────────────────────
STOCK_DATA["TSLA"] = [
    # 2023
    ("2023-01", 108.10, 173.22, 0.75),
    ("2023-02", 173.44, 207.46, 0.68),
    ("2023-03", 206.59, 207.46, 0.65),
    ("2023-04", 209.05, 164.31, 0.62),
    ("2023-05", 162.99, 207.52, 0.58),
    ("2023-06", 213.31, 261.77, 0.52),
    ("2023-07", 261.44, 266.44, 0.48),
    ("2023-08", 267.04, 245.01, 0.52),
    ("2023-09", 245.66, 250.22, 0.55),
    ("2023-10", 256.79, 200.84, 0.58),
    ("2023-11", 202.70, 234.30, 0.52),
    ("2023-12", 238.45, 248.42, 0.48),
    # 2024
    ("2024-01", 248.42, 187.29, 0.55),
    ("2024-02", 187.00, 201.88, 0.55),
    ("2024-03", 199.01, 175.79, 0.55),
    ("2024-04", 175.44, 170.33, 0.58),
    ("2024-05", 172.55, 178.08, 0.55),
    ("2024-06", 177.97, 197.42, 0.52),
    ("2024-07", 200.07, 232.07, 0.55),
    ("2024-08", 228.67, 214.11, 0.55),
    ("2024-09", 214.95, 260.48, 0.55),
    ("2024-10", 262.19, 249.85, 0.62),
    ("2024-11", 246.30, 352.56, 0.68),
    ("2024-12", 352.36, 421.06, 0.65),
    # 2025
    ("2025-01", 421.06, 394.94, 0.60),
    ("2025-02", 388.20, 302.10, 0.62),
    ("2025-03", 290.89, 263.55, 0.68),
    ("2025-04", 247.69, 284.65, 0.72),
    ("2025-05", 303.79, 348.55, 0.62),
    ("2025-06", 329.69, 366.72, 0.55),
    ("2025-07", 371.33, 337.26, 0.58),
    ("2025-08", 330.21, 255.68, 0.62),
    ("2025-09", 258.16, 248.23, 0.60),
    ("2025-10", 252.69, 301.73, 0.58),
    ("2025-11", 307.70, 342.03, 0.55),
    ("2025-12", 350.12, 379.28, 0.52),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST ENGINE (Delta-Based Strike Selection)
# ═══════════════════════════════════════════════════════════════════════════════

def run_covered_call_delta(data, initial_capital, target_delta, risk_free_rate=0.045):
    """
    Simulate a monthly covered call strategy with delta-based strike selection.
    
    A target_delta of 0.30 means we sell calls with ~30% probability of
    being in-the-money at expiration. Lower delta = more OTM = less premium
    but more upside participation.
    """
    cash = initial_capital
    shares = 0
    total_premiums = 0.0
    monthly_log = []
    times_called_away = 0
    times_expired_worthless = 0

    for i, (month, open_px, close_px, iv) in enumerate(data):
        if shares == 0:
            lots = int(cash / (open_px * 100))
            if lots == 0:
                monthly_log.append({
                    "month": month, "action": "SKIP", "shares": 0,
                    "open_px": open_px, "close_px": close_px,
                    "strike": None, "premium_per_share": 0,
                    "total_premium": 0, "called_away": False,
                    "portfolio_value": cash, "otm_pct": 0,
                })
                continue
            shares = lots * 100
            cash -= shares * open_px

        T = 1.0 / 12.0
        strike = strike_for_delta(open_px, target_delta, T, risk_free_rate, iv)

        if strike <= open_px:
            strike = open_px + (0.50 if open_px < 50 else 2.50 if open_px < 200 else 5.00)

        otm_pct = (strike - open_px) / open_px * 100
        actual_delta = call_delta(open_px, strike, T, risk_free_rate, iv)

        contracts = shares // 100
        premium_per_share = black_scholes_call(open_px, strike, T, risk_free_rate, iv)
        total_premium = premium_per_share * shares
        cash += total_premium
        total_premiums += total_premium

        called_away = close_px >= strike

        if called_away:
            proceeds = shares * strike
            cash += proceeds
            times_called_away += 1
            shares = 0
        else:
            times_expired_worthless += 1

        portfolio_value = cash + shares * close_px

        monthly_log.append({
            "month": month, "action": "CALLED" if called_away else "HOLD",
            "shares": shares if not called_away else 0,
            "open_px": open_px, "close_px": close_px,
            "strike": strike, "premium_per_share": premium_per_share,
            "total_premium": total_premium, "called_away": called_away,
            "portfolio_value": portfolio_value, "otm_pct": otm_pct,
            "actual_delta": actual_delta,
        })

    final_value = cash + shares * data[-1][2]
    total_return = (final_value - initial_capital) / initial_capital * 100
    avg_premium_yield = (total_premiums / 36) / initial_capital * 100 * 12

    return {
        "final_value": final_value,
        "total_return_pct": total_return,
        "total_premiums": total_premiums,
        "times_called_away": times_called_away,
        "times_expired_worthless": times_expired_worthless,
        "monthly_log": monthly_log,
        "avg_monthly_premium": total_premiums / 36,
        "annualized_premium_yield": avg_premium_yield,
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


# ═══════════════════════════════════════════════════════════════════════════════
#  RUN ALL BACKTESTS
# ═══════════════════════════════════════════════════════════════════════════════

INITIAL_CAPITAL = 100_000
DELTA_LEVELS = [0.15, 0.20, 0.25, 0.30, 0.40]
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

results = {}
for sym in SYMBOLS:
    results[sym] = {}
    for delta in DELTA_LEVELS:
        results[sym][delta] = run_covered_call_delta(
            STOCK_DATA[sym], INITIAL_CAPITAL, delta
        )
    results[sym]["buy_hold"] = run_buy_and_hold(STOCK_DATA[sym], INITIAL_CAPITAL)


# ═══════════════════════════════════════════════════════════════════════════════
#  OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

W = 140  # output width

def sep(char="═"):
    print(char * W)

def header(title):
    print()
    sep()
    print(f"  {title}")
    sep()


# ──────────────────────────────────────────────────────────────────────────────
#  1. MAIN SUMMARY MATRIX
# ──────────────────────────────────────────────────────────────────────────────
header("MAGNIFICENT 7 COVERED CALL BACKTEST — DELTA-BASED STRIKE SELECTION")
print(f"  Period:             January 2023 – December 2025 (36 months)")
print(f"  Initial Investment: ${INITIAL_CAPITAL:,.0f}")
print(f"  Strategy:           Monthly covered calls, delta-based OTM strikes")
print(f"  Option Pricing:     Black-Scholes with historical IV")
print(f"  Delta Levels:       {', '.join(f'{d:.2f}' for d in DELTA_LEVELS)}")
print(f"  Note:               Lower delta = more OTM = less premium but more upside")
print(f"                      NVDA prices are 10:1 split-adjusted")

# --- Total Return Table ---
header("TOTAL RETURN (%) BY DELTA LEVEL")
print()
col_w = 14
hdr = f"{'Stock':<8}"
for d in DELTA_LEVELS:
    hdr += f"{'Δ=' + f'{d:.2f}':>{col_w}}"
hdr += f"{'Buy&Hold':>{col_w}}"
print(hdr)
print("─" * (8 + col_w * (len(DELTA_LEVELS) + 1)))

for sym in SYMBOLS:
    row = f"{sym:<8}"
    for d in DELTA_LEVELS:
        ret = results[sym][d]["total_return_pct"]
        row += f"{ret:>{col_w}.2f}%"
    bh = results[sym]["buy_hold"]["total_return_pct"]
    row += f"{bh:>{col_w}.2f}%"
    print(row)

print()
print("  (Higher is better)")

# --- Final Portfolio Value Table ---
header("FINAL PORTFOLIO VALUE ($) BY DELTA LEVEL")
print()
hdr = f"{'Stock':<8}"
for d in DELTA_LEVELS:
    hdr += f"{'Δ=' + f'{d:.2f}':>{col_w+2}}"
hdr += f"{'Buy&Hold':>{col_w+2}}"
print(hdr)
print("─" * (8 + (col_w + 2) * (len(DELTA_LEVELS) + 1)))

for sym in SYMBOLS:
    row = f"{sym:<8}"
    for d in DELTA_LEVELS:
        val = results[sym][d]["final_value"]
        row += f"${val:>{col_w}.0f}"
    bh = results[sym]["buy_hold"]["final_value"]
    row += f"${bh:>{col_w}.0f}"
    print(row)

# --- Assignment Frequency Table ---
header("TIMES CALLED AWAY (OUT OF 36 MONTHS) BY DELTA LEVEL")
print()
hdr = f"{'Stock':<8}"
for d in DELTA_LEVELS:
    hdr += f"{'Δ=' + f'{d:.2f}':>{col_w}}"
print(hdr)
print("─" * (8 + col_w * len(DELTA_LEVELS)))

for sym in SYMBOLS:
    row = f"{sym:<8}"
    for d in DELTA_LEVELS:
        ca = results[sym][d]["times_called_away"]
        row += f"{ca:>{col_w}d}"
    print(row)

print()
print("  (More call-aways = more capped upside in strong rallies)")

# --- Total Premiums Collected ---
header("TOTAL PREMIUMS COLLECTED ($) BY DELTA LEVEL")
print()
hdr = f"{'Stock':<8}"
for d in DELTA_LEVELS:
    hdr += f"{'Δ=' + f'{d:.2f}':>{col_w+2}}"
print(hdr)
print("─" * (8 + (col_w + 2) * len(DELTA_LEVELS)))

for sym in SYMBOLS:
    row = f"{sym:<8}"
    for d in DELTA_LEVELS:
        prem = results[sym][d]["total_premiums"]
        row += f"${prem:>{col_w},.0f}"
    print(row)

# --- Annualized Premium Yield ---
header("ANNUALIZED PREMIUM YIELD (%) BY DELTA LEVEL")
print(f"  (Monthly premium ÷ capital, annualized)")
print()
hdr = f"{'Stock':<8}"
for d in DELTA_LEVELS:
    hdr += f"{'Δ=' + f'{d:.2f}':>{col_w}}"
print(hdr)
print("─" * (8 + col_w * len(DELTA_LEVELS)))

for sym in SYMBOLS:
    row = f"{sym:<8}"
    for d in DELTA_LEVELS:
        yld = results[sym][d]["annualized_premium_yield"]
        row += f"{yld:>{col_w}.2f}%"
    print(row)

# ──────────────────────────────────────────────────────────────────────────────
#  2. BEST STOCK PER DELTA LEVEL
# ──────────────────────────────────────────────────────────────────────────────
header("WINNER BY DELTA LEVEL")
print()

for d in DELTA_LEVELS:
    best_sym = max(SYMBOLS, key=lambda s: results[s][d]["total_return_pct"])
    best_ret = results[best_sym][d]["total_return_pct"]
    worst_sym = min(SYMBOLS, key=lambda s: results[s][d]["total_return_pct"])
    worst_ret = results[worst_sym][d]["total_return_pct"]
    print(f"  Delta {d:.2f}:  BEST = {best_sym:<6} ({best_ret:+.2f}%)   "
          f"WORST = {worst_sym:<6} ({worst_ret:+.2f}%)   "
          f"Spread = {best_ret - worst_ret:.2f}%")

print()
best_bh_sym = max(SYMBOLS, key=lambda s: results[s]["buy_hold"]["total_return_pct"])
best_bh_ret = results[best_bh_sym]["buy_hold"]["total_return_pct"]
print(f"  Buy&Hold: BEST = {best_bh_sym:<6} ({best_bh_ret:+.2f}%)")

# ──────────────────────────────────────────────────────────────────────────────
#  3. DELTA IMPACT ANALYSIS: CC RETURN vs BUY-AND-HOLD
# ──────────────────────────────────────────────────────────────────────────────
header("COVERED CALL vs BUY-AND-HOLD DIFFERENTIAL (%)")
print(f"  (Positive = CC outperformed, Negative = CC underperformed)")
print()

hdr = f"{'Stock':<8}"
for d in DELTA_LEVELS:
    hdr += f"{'Δ=' + f'{d:.2f}':>{col_w}}"
print(hdr)
print("─" * (8 + col_w * len(DELTA_LEVELS)))

for sym in SYMBOLS:
    row = f"{sym:<8}"
    bh_ret = results[sym]["buy_hold"]["total_return_pct"]
    for d in DELTA_LEVELS:
        cc_ret = results[sym][d]["total_return_pct"]
        diff = cc_ret - bh_ret
        row += f"{diff:>{col_w-1}.2f}%"
    print(row)

# ──────────────────────────────────────────────────────────────────────────────
#  4. AVERAGE IMPLIED VOLATILITY BY STOCK
# ──────────────────────────────────────────────────────────────────────────────
header("AVERAGE IMPLIED VOLATILITY & OTM DISTANCE")
print(f"  (Shows why equal delta ≠ equal OTM %; higher IV → more OTM for same delta)")
print()

print(f"{'Stock':<8} {'Avg IV':>8} {'Avg OTM% @Δ0.15':>16} {'Avg OTM% @Δ0.30':>16} {'Avg OTM% @Δ0.40':>16}")
print("─" * 72)

for sym in SYMBOLS:
    avg_iv = sum(d[3] for d in STOCK_DATA[sym]) / len(STOCK_DATA[sym])
    
    avg_otm_15 = sum(
        e["otm_pct"] for e in results[sym][0.15]["monthly_log"] if e["strike"]
    ) / max(1, sum(1 for e in results[sym][0.15]["monthly_log"] if e["strike"]))
    
    avg_otm_30 = sum(
        e["otm_pct"] for e in results[sym][0.30]["monthly_log"] if e["strike"]
    ) / max(1, sum(1 for e in results[sym][0.30]["monthly_log"] if e["strike"]))
    
    avg_otm_40 = sum(
        e["otm_pct"] for e in results[sym][0.40]["monthly_log"] if e["strike"]
    ) / max(1, sum(1 for e in results[sym][0.40]["monthly_log"] if e["strike"]))
    
    print(f"{sym:<8} {avg_iv:>7.1%} {avg_otm_15:>15.1f}% {avg_otm_30:>15.1f}% {avg_otm_40:>15.1f}%")


# ──────────────────────────────────────────────────────────────────────────────
#  5. RISK-ADJUSTED COMPARISON
# ──────────────────────────────────────────────────────────────────────────────
header("RISK METRICS: MONTHLY PORTFOLIO VALUE VOLATILITY")
print()

import statistics

print(f"{'Stock':<8} {'Delta':>8} {'Return':>10} {'Monthly StdDev':>16} {'Sharpe*':>10}")
print("─" * 56)

for sym in SYMBOLS:
    for d in [0.20, 0.30]:
        log = results[sym][d]["monthly_log"]
        values = [e["portfolio_value"] for e in log]
        monthly_returns = []
        for j in range(1, len(values)):
            if values[j-1] > 0:
                monthly_returns.append((values[j] - values[j-1]) / values[j-1])
        if len(monthly_returns) > 1:
            avg_ret = statistics.mean(monthly_returns)
            std_ret = statistics.stdev(monthly_returns)
            sharpe = (avg_ret - 0.045/12) / std_ret if std_ret > 0 else 0
        else:
            avg_ret = std_ret = sharpe = 0
        
        ret_pct = results[sym][d]["total_return_pct"]
        print(f"{sym:<8} {d:>8.2f} {ret_pct:>9.2f}% {std_ret:>15.4f} {sharpe:>10.3f}")
    
    bh = results[sym]["buy_hold"]
    bh_data = STOCK_DATA[sym]
    bh_shares = int(INITIAL_CAPITAL / (bh_data[0][1] * 100)) * 100
    bh_cash = INITIAL_CAPITAL - bh_shares * bh_data[0][1]
    bh_values = [bh_cash + bh_shares * d[2] for d in bh_data]
    bh_monthly_returns = []
    for j in range(1, len(bh_values)):
        if bh_values[j-1] > 0:
            bh_monthly_returns.append((bh_values[j] - bh_values[j-1]) / bh_values[j-1])
    if len(bh_monthly_returns) > 1:
        bh_avg = statistics.mean(bh_monthly_returns)
        bh_std = statistics.stdev(bh_monthly_returns)
        bh_sharpe = (bh_avg - 0.045/12) / bh_std if bh_std > 0 else 0
    else:
        bh_avg = bh_std = bh_sharpe = 0
    print(f"{sym:<8} {'B&H':>8} {bh['total_return_pct']:>9.2f}% {bh_std:>15.4f} {bh_sharpe:>10.3f}")
    print()

print("  * Sharpe ratio = (avg monthly return - risk-free/12) / monthly stdev")
print("    Higher = better risk-adjusted returns")


# ──────────────────────────────────────────────────────────────────────────────
#  6. KEY INSIGHTS
# ──────────────────────────────────────────────────────────────────────────────
header("KEY INSIGHTS")
print("""
  1. DELTA = EQUAL RISK: Using delta-based strike selection ensures that each
     stock has the same PROBABILITY of assignment, regardless of its volatility.
     A 0.30-delta call on TSLA (IV ~60%) will be much more OTM in $ terms than
     a 0.30-delta call on AAPL (IV ~23%), but both have ~30% chance of being
     in-the-money at expiration.

  2. HIGH-IV STOCKS GENERATE MORE PREMIUM: TSLA and NVDA, with IV of 45-75%,
     generate far more premium income than AAPL or MSFT (20-30% IV). This is
     the compensation option sellers receive for taking on more volatile stocks.

  3. DELTA TRADE-OFF:
     - Low delta (0.15): Very conservative, ~15% assignment probability.
       Minimal premium income, but captures most upside moves.
     - Moderate delta (0.25-0.30): The "sweet spot" for most CC sellers.
       Decent premium income with reasonable upside participation.
     - High delta (0.40): Aggressive income strategy, ~40% assignment
       probability. Maximum premium but frequently caps upside.

  4. BULL MARKET DRAG: Jan 2023 – Dec 2025 was largely a strong bull market.
     In such environments, covered calls almost always underperform buy-and-hold
     because the capped upside is a significant drag. Lower delta (0.15-0.20)
     minimizes this drag.

  5. STOCK CHARACTERISTICS MATTER:
     - Fast growers (NVDA, META, TSLA): CC strategies sacrifice more upside
       in strong rally months. Premium income partially compensates.
     - Steady growers (AAPL, MSFT): CC strategies lose less upside per month
       but also collect less premium income.
     - Sideways movers: CC strategies shine here, as premium income adds
       return to otherwise flat price action.

  6. OPTIMAL STRATEGY DEPENDS ON MARKET OUTLOOK:
     - Bullish: Use lower delta (0.15-0.20) or skip covered calls entirely
     - Neutral/mild bull: Use moderate delta (0.25-0.30) for best premium
     - Bearish: Covered calls provide limited downside protection via
       premium income; consider protective puts instead
""")

sep()
print("  Backtest complete.")
sep()
