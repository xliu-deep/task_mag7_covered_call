"""
Covered Call Backtest with REAL ThetaData Option Premiums — V2
==============================================================
Period: January 2021 – December 2025 (60 months)
Initial Investment: $100,000 per stock
Stocks: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA

Key improvements over V1:
  - Bypasses slow /option/list/strikes endpoint by calculating strikes mathematically
  - Proper rate limiting (0.5s between calls) to avoid 429 errors
  - Exponential backoff on 429/timeout errors
  - Saves intermediate results to JSON for resume capability
  - Uses mid price (avg bid/ask) for realistic premium estimates
"""

import json
import time
import math
import os
import requests
import pandas as pd
import yfinance as yf
from datetime import date, timedelta, datetime
from scipy.stats import norm

BASE_URL = "http://127.0.0.1:25503"
SESSION = requests.Session()
STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
INITIAL_CAPITAL = 100_000
TARGET_DELTAS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
SLEEP_BETWEEN_CALLS = 0.3
WORK_DIR = "/Users/rachel/Library/CloudStorage/OneDrive-Personal/Investment/RobotInvestment"
CACHE_FILE = os.path.join(WORK_DIR, "cc_v2_cache.json")
RESULTS_FILE = os.path.join(WORK_DIR, "cc_real_data_results_v2.json")


def third_friday(year, month):
    d = date(year, month, 1)
    day_of_week = d.weekday()
    first_friday = d + timedelta(days=(4 - day_of_week) % 7)
    return first_friday + timedelta(weeks=2)


def round_strike(stock_price, raw_strike):
    if stock_price < 50:
        return round(raw_strike * 2) / 2
    elif stock_price < 200:
        return round(raw_strike / 2.5) * 2.5
    else:
        return round(raw_strike / 5) * 5


def generate_candidate_strikes(stock_price):
    """Generate OTM call strikes from ATM to ~25% OTM."""
    strikes = set()
    if stock_price < 50:
        step = 0.5
    elif stock_price < 200:
        step = 2.5
    else:
        step = 5.0

    atm = round_strike(stock_price, stock_price)
    lower = atm
    upper = stock_price * 1.28

    s = lower
    while s <= upper:
        strikes.add(s)
        s += step

    return sorted(strikes)


def bs_strike_for_delta(S, target_delta, T, r, sigma):
    """Estimate the strike for a given delta using Black-Scholes."""
    if sigma <= 0 or T <= 0:
        return S * 1.05
    d1 = norm.ppf(target_delta)
    K = S * math.exp((r + 0.5 * sigma**2) * T - d1 * sigma * math.sqrt(T))
    return K


def api_call_with_retry(url, max_retries=3, timeout=20):
    """Make an API call with retry and backoff on 429/timeout."""
    for attempt in range(max_retries):
        try:
            resp = SESSION.get(url, timeout=timeout)
            text = resp.text.strip()

            if resp.status_code == 429 or 'too many requests' in text.lower():
                wait = 15 * (attempt + 1)
                print(f"    [429] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            if '<html>' in text.lower() or 'error' in text[:50].lower():
                if 'subscription' in text.lower():
                    return None
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue

            return text
        except requests.exceptions.Timeout:
            wait = 10 * (attempt + 1)
            print(f"    [Timeout] Attempt {attempt+1}, waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return None
    return None


def parse_greeks_response(text):
    """Parse a greeks/eod CSV response into a dict."""
    if not text:
        return None
    lines = text.split('\n')
    if len(lines) < 2:
        return None
    header = [h.strip().replace('"', '') for h in lines[0].split(',')]
    values = [v.strip().replace('"', '') for v in lines[1].split(',')]
    if len(values) < len(header):
        return None
    row = dict(zip(header, values))
    return row


def query_option_greeks(symbol, expiration, strike, query_date):
    """Query greeks for one specific contract on one date."""
    strike_str = f"{strike:.3f}" if strike == int(strike) else f"{strike}"
    url = (f"{BASE_URL}/v3/option/history/greeks/eod"
           f"?symbol={symbol}&expiration={expiration}"
           f"&strike={strike}&right=C"
           f"&start_date={query_date}&end_date={query_date}")

    time.sleep(SLEEP_BETWEEN_CALLS)
    text = api_call_with_retry(url)
    if not text:
        return None

    row = parse_greeks_response(text)
    if not row:
        return None

    try:
        delta = float(row.get('delta', 0))
        bid = float(row.get('bid', 0))
        ask = float(row.get('ask', 0))
        close_px = float(row.get('close', 0))
        iv = float(row.get('implied_vol', 0))
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else close_px
        if delta > 0 and mid > 0.01:
            return {
                'strike': strike,
                'delta': delta,
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'close': close_px,
                'iv': iv,
            }
    except (ValueError, TypeError):
        pass
    return None


def get_expirations(symbol):
    """Get all available option expirations."""
    url = f"{BASE_URL}/v3/option/list/expirations?symbol={symbol}"
    text = api_call_with_retry(url, max_retries=5, timeout=30)
    if not text:
        return []
    lines = text.split('\n')[1:]
    exps = []
    for line in lines:
        parts = line.strip().replace('"', '').split(',')
        if len(parts) >= 2 and parts[1].strip():
            exps.append(parts[1].strip())
    return exps


def download_stock_prices():
    """Download all stock prices via yfinance."""
    print("Downloading stock prices from Yahoo Finance...")
    tickers = " ".join(STOCKS)
    data = yf.download(tickers, start="2020-12-28", end="2026-01-05", auto_adjust=True)
    close = data['Close']
    print(f"  Downloaded {len(close)} trading days for {len(STOCKS)} stocks")
    return close


def nearest_trading_day(prices_series, target_date, direction=1, max_tries=10):
    d = target_date
    for _ in range(max_tries):
        ts = pd.Timestamp(d)
        if ts in prices_series.index:
            val = prices_series.loc[ts]
            if not pd.isna(val):
                return d, float(val)
        d += timedelta(days=direction)
    return None, None


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)


def process_stock(symbol, stock_prices, cache):
    """Run the full CC backtest for one stock using real option data."""
    print(f"\n{'='*70}")
    print(f"  Processing {symbol}")
    print(f"{'='*70}")

    prices = stock_prices[symbol].dropna()

    all_exps = get_expirations(symbol)
    if not all_exps:
        print(f"  ERROR: No expirations found for {symbol}")
        return None
    exp_set = set(all_exps)

    monthly_exps = {}
    for year in range(2021, 2026):
        for month in range(1, 13):
            tf = third_friday(year, month)
            tf_str = tf.strftime('%Y-%m-%d')
            if tf_str in exp_set:
                monthly_exps[(year, month)] = tf_str
            else:
                for offset in [-1, 1, -2, 2, -3, 3, -7, 7]:
                    alt = (tf + timedelta(days=offset)).strftime('%Y-%m-%d')
                    if alt in exp_set:
                        monthly_exps[(year, month)] = alt
                        break

    print(f"  Found {len(monthly_exps)} monthly expirations")

    init_date, init_price = nearest_trading_day(prices, date(2021, 1, 4), direction=1)
    if init_price is None:
        print(f"  ERROR: No initial price for {symbol}")
        return None

    shares = (int(INITIAL_CAPITAL / init_price) // 100) * 100
    contracts = shares // 100
    remaining_cash = INITIAL_CAPITAL - shares * init_price

    print(f"  Init: ${init_price:.2f} on {init_date}, Shares: {shares}, Contracts: {contracts}")

    monthly_results = []
    delta_grid_results = {str(d): [] for d in TARGET_DELTAS}
    api_calls = 0
    skipped = 0

    for year in range(2021, 2026):
        for month in range(1, 13):
            key = (year, month)
            if key not in monthly_exps:
                continue

            expiration = monthly_exps[key]
            month_label = f"{year}-{month:02d}"

            sell_date, sell_price = nearest_trading_day(prices, date(year, month, 1), direction=1)
            if sell_price is None:
                continue

            exp_date_obj = datetime.strptime(expiration, '%Y-%m-%d').date()
            exp_date, exp_price = nearest_trading_day(prices, exp_date_obj, direction=-1)
            if exp_price is None:
                exp_date, exp_price = nearest_trading_day(prices, exp_date_obj, direction=1)
            if exp_price is None:
                continue

            sell_date_str = sell_date.strftime('%Y-%m-%d')
            cache_key = f"{symbol}_{expiration}_{sell_date_str}"

            if cache_key in cache:
                chain = cache[cache_key]
            else:
                candidates = generate_candidate_strikes(sell_price)
                chain = []
                for strike in candidates:
                    result = query_option_greeks(symbol, expiration, strike, sell_date_str)
                    api_calls += 1
                    if result:
                        chain.append(result)

                if not chain:
                    for offset_day in [1, 2, -1]:
                        alt_date = (sell_date + timedelta(days=offset_day)).strftime('%Y-%m-%d')
                        for strike in candidates[:5]:
                            result = query_option_greeks(symbol, expiration, strike, alt_date)
                            api_calls += 1
                            if result:
                                chain.append(result)
                        if chain:
                            break

                cache[cache_key] = chain
                if api_calls % 50 == 0:
                    save_cache(cache)

            if not chain:
                print(f"  {month_label}: No chain data (API calls: {api_calls})")
                skipped += 1
                continue

            for td in TARGET_DELTAS:
                td_str = str(td)
                best = min(chain, key=lambda c: abs(c['delta'] - td))
                if abs(best['delta'] - td) <= 0.15:
                    prem = best['mid']
                    strike = best['strike']
                    assigned = exp_price > strike
                    assign_cost = max(0, (exp_price - strike)) * shares if assigned else 0
                    total_prem = prem * shares

                    delta_grid_results[td_str].append({
                        'month': month_label, 'year': year,
                        'sell_price': sell_price, 'exp_price': exp_price,
                        'strike': strike, 'delta': best['delta'],
                        'iv': best['iv'], 'bid': best['bid'], 'ask': best['ask'],
                        'premium_per_share': prem, 'total_premium': total_prem,
                        'assigned': assigned, 'assignment_cost': assign_cost,
                        'net_cc': total_prem - assign_cost,
                    })

            primary = min(chain, key=lambda c: abs(c['delta'] - 0.20))
            if abs(primary['delta'] - 0.20) <= 0.12:
                prem = primary['mid']
                strike = primary['strike']
                assigned = exp_price > strike
                assign_cost = max(0, (exp_price - strike)) * shares if assigned else 0
                total_prem = prem * shares
                net = total_prem - assign_cost

                monthly_results.append({
                    'month': month_label, 'year': year,
                    'sell_date': sell_date_str, 'expiration': expiration,
                    'sell_price': round(sell_price, 2),
                    'exp_price': round(exp_price, 2),
                    'strike': strike, 'delta': round(primary['delta'], 4),
                    'iv': round(primary['iv'], 4),
                    'bid': round(primary['bid'], 2),
                    'ask': round(primary['ask'], 2),
                    'premium_per_share': round(prem, 2),
                    'total_premium': round(total_prem, 2),
                    'assigned': assigned,
                    'assignment_cost': round(assign_cost, 2),
                    'net_cc': round(net, 2),
                })

                status = "ASSIGNED" if assigned else "expired"
                print(f"  {month_label}: S=${sell_price:.0f} K=${strike:.0f} "
                      f"Δ={primary['delta']:.3f} bid=${primary['bid']:.2f} "
                      f"ask=${primary['ask']:.2f} mid=${prem:.2f} "
                      f"exp=${exp_price:.0f} [{status}] net=${net:+,.0f}")
            else:
                print(f"  {month_label}: Best Δ={primary['delta']:.3f} too far from 0.20")

    save_cache(cache)
    print(f"  Total API calls: {api_calls}, Skipped months: {skipped}")

    final_date, final_price = nearest_trading_day(prices, date(2025, 12, 31), direction=-1)
    if final_price is None:
        final_price = exp_price

    bh_return = (final_price / init_price - 1) * 100
    bh_final = shares * final_price + remaining_cash

    total_prem_d20 = sum(r['total_premium'] for r in monthly_results)
    total_assign_d20 = sum(r['assignment_cost'] for r in monthly_results)
    net_cc_d20 = total_prem_d20 - total_assign_d20
    times_assigned_d20 = sum(1 for r in monthly_results if r['assigned'])

    yearly = {}
    for r in monthly_results:
        yr = r['year']
        if yr not in yearly:
            yearly[yr] = {'premium': 0, 'assignment': 0, 'net': 0, 'months': 0, 'assigned': 0}
        yearly[yr]['premium'] += r['total_premium']
        yearly[yr]['assignment'] += r['assignment_cost']
        yearly[yr]['net'] += r['net_cc']
        yearly[yr]['months'] += 1
        if r['assigned']:
            yearly[yr]['assigned'] += 1

    yearly_bh = {}
    for year in range(2021, 2026):
        start_d, start_p = nearest_trading_day(prices, date(year, 1, 1), direction=1)
        end_d, end_p = nearest_trading_day(prices, date(year, 12, 31), direction=-1)
        if start_p and end_p:
            yearly_bh[year] = round((end_p / start_p - 1) * 100, 1)

    delta_grid_summary = {}
    for delta_str, results in delta_grid_results.items():
        if results:
            tp = sum(r['total_premium'] for r in results)
            ta = sum(r['assignment_cost'] for r in results)
            net = tp - ta
            avg_iv = sum(r['iv'] for r in results) / len(results)
            nassign = sum(1 for r in results if r['assigned'])
            yr_net = {}
            for r in results:
                yr = r['year']
                yr_net[yr] = yr_net.get(yr, 0) + r['net_cc']

            delta_grid_summary[delta_str] = {
                'total_premium': round(tp, 2),
                'total_assignment': round(ta, 2),
                'net_cc': round(net, 2),
                'net_cc_pct': round(net / INITIAL_CAPITAL * 100, 1),
                'times_assigned': nassign,
                'avg_iv': round(avg_iv, 4),
                'months_covered': len(results),
                'yearly_net': {str(yr): round(v, 2) for yr, v in yr_net.items()},
            }

    best_delta = max(delta_grid_summary.items(),
                     key=lambda x: x[1]['net_cc']) if delta_grid_summary else None

    summary = {
        'symbol': symbol,
        'initial_price': round(init_price, 2),
        'final_price': round(final_price, 2),
        'shares': shares,
        'contracts': contracts,
        'remaining_cash': round(remaining_cash, 2),
        'bh_return_pct': round(bh_return, 1),
        'bh_final_value': round(bh_final, 2),
        'yearly_bh_returns': yearly_bh,
        'total_premium_d20': round(total_prem_d20, 2),
        'total_assignment_d20': round(total_assign_d20, 2),
        'net_cc_d20': round(net_cc_d20, 2),
        'net_cc_pct_d20': round(net_cc_d20 / INITIAL_CAPITAL * 100, 1),
        'times_assigned_d20': times_assigned_d20,
        'total_months': len(monthly_results),
        'yearly': {str(k): v for k, v in yearly.items()},
        'delta_grid': delta_grid_summary,
        'optimal_delta': best_delta[0] if best_delta else None,
        'optimal_net_cc': round(best_delta[1]['net_cc'], 2) if best_delta else 0,
        'optimal_net_cc_pct': best_delta[1]['net_cc_pct'] if best_delta else 0,
        'monthly_detail': monthly_results,
    }

    print(f"\n  === {symbol} SUMMARY ===")
    print(f"  B&H Return: {bh_return:+.1f}%  Final Value: ${bh_final:,.0f}")
    print(f"  CC Premium (Δ=0.20): ${total_prem_d20:,.0f}")
    print(f"  Assignment Cost: ${total_assign_d20:,.0f}")
    print(f"  Net CC Overlay: ${net_cc_d20:+,.0f} ({net_cc_d20/INITIAL_CAPITAL*100:+.1f}%)")
    print(f"  Times Assigned: {times_assigned_d20}/{len(monthly_results)}")
    if best_delta:
        bd = best_delta[1]
        print(f"  Optimal Δ={best_delta[0]} → Net CC: ${bd['net_cc']:+,.0f} ({bd['net_cc_pct']:+.1f}%)")
    print(f"  Yearly B&H: {yearly_bh}")
    for yr in sorted(yearly.keys()):
        y = yearly[yr]
        print(f"    {yr}: Prem=${y['premium']:,.0f} Assign=${y['assignment']:,.0f} "
              f"Net=${y['net']:+,.0f} Assigned={y['assigned']}/{y['months']}")

    return summary


def main():
    print("=" * 70)
    print("  COVERED CALL BACKTEST V2 — REAL ThetaData Option Premiums")
    print("  Period: Jan 2021 – Dec 2025 | Capital: $100K/stock")
    print("  Strikes: Calculated mathematically (bypasses slow /strikes API)")
    print("=" * 70)

    try:
        resp = SESSION.get(f"{BASE_URL}/v3/option/list/expirations?symbol=AAPL", timeout=30)
        if resp.status_code != 200 or '<html>' in resp.text.lower():
            print("ERROR: ThetaData API not responding properly")
            return
    except Exception as e:
        print(f"ERROR: Cannot connect to ThetaData API: {e}")
        return
    print("ThetaData API: OK")

    stock_prices = download_stock_prices()
    cache = load_cache()
    all_results = {}

    for i, symbol in enumerate(STOCKS):
        print(f"\n[{i+1}/{len(STOCKS)}] Starting {symbol}...")
        result = process_stock(symbol, stock_prices, cache)
        if result:
            all_results[symbol] = result
            with open(RESULTS_FILE, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"  Saved {symbol} results.")

    save_cache(cache)

    print(f"\n{'='*70}")
    print(f"  Results saved to: {RESULTS_FILE}")
    print(f"{'='*70}")

    print(f"\n{'='*90}")
    print(f"  FINAL COMPARISON — REAL OPTION PREMIUMS")
    print(f"{'='*90}")
    print(f"\n{'Stock':<8} {'B&H%':>8} {'CC Prem':>10} {'Assign$':>10} {'NetCC$':>10} "
          f"{'NetCC%':>8} {'Comb%':>8} {'OptΔ':>6} {'OptNet%':>8} {'#Asgn':>8}")
    print("-" * 90)

    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            bh = r['bh_return_pct']
            net_pct = r['net_cc_pct_d20']
            comb = bh + net_pct
            od = r.get('optimal_delta', 'N/A')
            on = r.get('optimal_net_cc_pct', 0)
            print(f"{sym:<8} {bh:>+7.1f}% ${r['total_premium_d20']:>9,.0f} "
                  f"${r['total_assignment_d20']:>9,.0f} ${r['net_cc_d20']:>9,.0f} "
                  f"{net_pct:>+7.1f}% {comb:>+7.1f}% {od:>6} {on:>+7.1f}% "
                  f"{r['times_assigned_d20']:>5}/{r['total_months']}")

    print(f"\n{'='*90}")
    print(f"  YEARLY NET CC OVERLAY ($) at Delta=0.20")
    print(f"{'='*90}")
    print(f"{'Stock':<8}", end="")
    for yr in range(2021, 2026):
        print(f"  {yr:>10}", end="")
    print(f"  {'5-Yr Total':>10}")
    print("-" * 78)
    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            print(f"{sym:<8}", end="")
            for yr in range(2021, 2026):
                yr_data = r['yearly'].get(str(yr), {})
                net = yr_data.get('net', 0)
                print(f"  ${net:>9,.0f}", end="")
            print(f"  ${r['net_cc_d20']:>9,.0f}")

    print(f"\n{'='*90}")
    print(f"  YEARLY BUY & HOLD RETURNS (%)")
    print(f"{'='*90}")
    print(f"{'Stock':<8}", end="")
    for yr in range(2021, 2026):
        print(f"  {yr:>8}", end="")
    print(f"  {'5-Year':>8}")
    print("-" * 68)
    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            print(f"{sym:<8}", end="")
            for yr in range(2021, 2026):
                ret = r['yearly_bh_returns'].get(yr, 0)
                print(f"  {ret:>+7.1f}%", end="")
            print(f"  {r['bh_return_pct']:>+7.1f}%")

    print(f"\n{'='*90}")
    print(f"  DELTA GRID SEARCH — Net CC % of $100K")
    print(f"{'='*90}")
    header = f"{'Stock':<8}"
    for d in TARGET_DELTAS:
        header += f"  {d:>5}"
    header += f"  {'Best':>6}"
    print(header)
    print("-" * (8 + len(TARGET_DELTAS) * 7 + 8))

    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            line = f"{sym:<8}"
            for d in TARGET_DELTAS:
                val = r['delta_grid'].get(str(d), {}).get('net_cc_pct', 0)
                line += f"  {val:>+5.1f}"
            best = r.get('optimal_delta', 'N/A')
            line += f"  {best:>6}"
            print(line)

    print(f"\n{'='*90}")
    print("  BACKTEST COMPLETE — All premiums from real ThetaData bid/ask!")
    print(f"{'='*90}")


if __name__ == "__main__":
    main()
