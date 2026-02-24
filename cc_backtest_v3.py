"""
Covered Call Backtest V3 — REAL ThetaData Option Premiums + Split Handling
==========================================================================
Period: January 2021 – December 2025 (60 months)
Initial Investment: $100,000 per stock
Stocks: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA

V3 improvements:
  - Proper stock split handling (GOOGL 20:1, AMZN 20:1, NVDA 4:1+10:1, TSLA 3:1)
  - Converts yfinance adjusted prices to actual trading prices for option queries
  - Tracks share count changes through splits
  - Skips months where contracts < 1
  - Uses cached results from V2 for AAPL and MSFT (no splits)
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
CACHE_FILE = os.path.join(WORK_DIR, "cc_v3_cache.json")
RESULTS_FILE = os.path.join(WORK_DIR, "cc_real_data_results_v3.json")
V2_RESULTS_FILE = os.path.join(WORK_DIR, "cc_real_data_results_v2.json")

SPLITS = {
    "GOOGL": [(date(2022, 7, 18), 20)],
    "AMZN":  [(date(2022, 6, 6), 20)],
    "NVDA":  [(date(2021, 7, 20), 4), (date(2024, 6, 10), 10)],
    "TSLA":  [(date(2022, 8, 25), 3)],
}


def get_split_ratio(symbol, query_date):
    """Get the cumulative split ratio for a given date.
    This converts yfinance adjusted price to actual trading price:
       actual_price = adjusted_price * ratio
    """
    if symbol not in SPLITS:
        return 1
    ratio = 1
    for split_date, split_factor in SPLITS[symbol]:
        if query_date < split_date:
            ratio *= split_factor
    return ratio


def third_friday(year, month):
    d = date(year, month, 1)
    day_of_week = d.weekday()
    first_friday = d + timedelta(days=(4 - day_of_week) % 7)
    return first_friday + timedelta(weeks=2)


def round_strike(stock_price, raw_strike):
    if stock_price < 25:
        return round(raw_strike * 2) / 2
    elif stock_price < 200:
        return round(raw_strike / 2.5) * 2.5
    elif stock_price < 1000:
        return round(raw_strike / 5) * 5
    else:
        return round(raw_strike / 10) * 10


def generate_candidate_strikes(actual_price):
    """Generate OTM call strikes based on actual (non-adjusted) trading price."""
    strikes = set()
    if actual_price < 25:
        step = 0.5
    elif actual_price < 200:
        step = 2.5
    elif actual_price < 1000:
        step = 5.0
    else:
        step = 10.0

    atm = round_strike(actual_price, actual_price)
    lower = atm
    upper = actual_price * 1.25

    s = lower
    while s <= upper:
        strikes.add(s)
        s += step

    return sorted(strikes)


def api_call_with_retry(url, max_retries=3, timeout=20):
    for attempt in range(max_retries):
        try:
            resp = SESSION.get(url, timeout=timeout)
            text = resp.text.strip()

            if resp.status_code == 429 or 'too many requests' in text.lower():
                wait = 15 * (attempt + 1)
                print(f"    [429] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            if '<html>' in text.lower():
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
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return None
    return None


def parse_greeks_response(text):
    if not text:
        return None
    lines = text.split('\n')
    if len(lines) < 2:
        return None
    header = [h.strip().replace('"', '') for h in lines[0].split(',')]
    values = [v.strip().replace('"', '') for v in lines[1].split(',')]
    if len(values) < len(header):
        return None
    return dict(zip(header, values))


def query_option_greeks(symbol, expiration, strike, query_date):
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
        underlying = float(row.get('underlying_price', 0))
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
                'underlying': underlying,
            }
    except (ValueError, TypeError):
        pass
    return None


def get_expirations(symbol):
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
    print(f"\n{'='*70}")
    print(f"  Processing {symbol}")
    print(f"{'='*70}")

    prices = stock_prices[symbol].dropna()

    all_exps = get_expirations(symbol)
    if not all_exps:
        print(f"  ERROR: No expirations for {symbol}")
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

    init_date, init_adj_price = nearest_trading_day(prices, date(2021, 1, 4), direction=1)
    if init_adj_price is None:
        print(f"  ERROR: No initial price for {symbol}")
        return None

    init_split_ratio = get_split_ratio(symbol, init_date)
    init_actual_price = init_adj_price * init_split_ratio

    # Buy max shares affordable (don't round to 100-lot yet; splits may bring us above 100)
    init_actual_shares = int(INITIAL_CAPITAL / init_actual_price)
    remaining_cash = INITIAL_CAPITAL - init_actual_shares * init_actual_price
    init_contracts = init_actual_shares // 100

    print(f"  Init: adj=${init_adj_price:.2f} actual=${init_actual_price:.2f} "
          f"ratio={init_split_ratio} shares={init_actual_shares} contracts={init_contracts}")

    if init_contracts < 1:
        future_splits = SPLITS.get(symbol, [])
        max_future_mult = 1
        for _, sf in future_splits:
            max_future_mult *= sf
        future_shares = init_actual_shares * max_future_mult
        future_contracts = future_shares // 100
        if future_contracts >= 1:
            print(f"  NOTE: After all splits → {future_shares} shares = {future_contracts} contracts")
        else:
            print(f"  WARNING: Even after splits, can't do CC with $100K")

    monthly_results = []
    delta_grid_results = {str(d): [] for d in TARGET_DELTAS}
    api_calls = 0
    skipped_no_data = 0
    skipped_no_contracts = 0

    for year in range(2021, 2026):
        for month in range(1, 13):
            key = (year, month)
            if key not in monthly_exps:
                continue

            expiration = monthly_exps[key]
            month_label = f"{year}-{month:02d}"

            sell_date, sell_adj_price = nearest_trading_day(
                prices, date(year, month, 1), direction=1)
            if sell_adj_price is None:
                continue

            split_ratio = get_split_ratio(symbol, sell_date)
            sell_actual_price = sell_adj_price * split_ratio

            # Track how many shares we'd have by this date (splits applied)
            cumul_mult = 1
            for s_date, s_factor in SPLITS.get(symbol, []):
                if init_date < s_date <= sell_date:
                    cumul_mult *= s_factor
            current_actual_shares = init_actual_shares * cumul_mult
            current_contracts = current_actual_shares // 100

            if current_contracts < 1:
                skipped_no_contracts += 1
                continue

            tradeable_shares = current_contracts * 100

            exp_date_obj = datetime.strptime(expiration, '%Y-%m-%d').date()
            exp_date, exp_adj_price = nearest_trading_day(
                prices, exp_date_obj, direction=-1)
            if exp_adj_price is None:
                exp_date, exp_adj_price = nearest_trading_day(
                    prices, exp_date_obj, direction=1)
            if exp_adj_price is None:
                continue

            exp_split_ratio = get_split_ratio(symbol, exp_date)
            exp_actual_price = exp_adj_price * exp_split_ratio

            sell_date_str = sell_date.strftime('%Y-%m-%d')
            cache_key = f"{symbol}_{expiration}_{sell_date_str}_v3"

            if cache_key in cache:
                chain = cache[cache_key]
            else:
                candidates = generate_candidate_strikes(sell_actual_price)
                chain = []
                for strike in candidates:
                    result = query_option_greeks(symbol, expiration, strike, sell_date_str)
                    api_calls += 1
                    if result:
                        chain.append(result)

                if not chain:
                    for offset_day in [1, 2, -1]:
                        alt = (sell_date + timedelta(days=offset_day)).strftime('%Y-%m-%d')
                        for strike in candidates[:5]:
                            result = query_option_greeks(
                                symbol, expiration, strike, alt)
                            api_calls += 1
                            if result:
                                chain.append(result)
                        if chain:
                            break

                cache[cache_key] = chain
                if api_calls % 50 == 0:
                    save_cache(cache)

            if not chain:
                print(f"  {month_label}: No chain (actual=${sell_actual_price:.0f}, "
                      f"ratio={split_ratio}, API calls: {api_calls})")
                skipped_no_data += 1
                continue

            for td in TARGET_DELTAS:
                td_str = str(td)
                best = min(chain, key=lambda c: abs(c['delta'] - td))
                if abs(best['delta'] - td) <= 0.15:
                    prem_per_share = best['mid']
                    strike = best['strike']
                    assigned = exp_actual_price > strike
                    assign_cost = (max(0, exp_actual_price - strike)
                                   * tradeable_shares if assigned else 0)
                    total_prem = prem_per_share * tradeable_shares

                    delta_grid_results[td_str].append({
                        'month': month_label, 'year': year,
                        'sell_price_actual': sell_actual_price,
                        'exp_price_actual': exp_actual_price,
                        'strike': strike, 'delta': best['delta'],
                        'iv': best['iv'], 'bid': best['bid'], 'ask': best['ask'],
                        'premium_per_share': prem_per_share,
                        'total_premium': total_prem,
                        'assigned': assigned, 'assignment_cost': assign_cost,
                        'net_cc': total_prem - assign_cost,
                        'contracts': current_contracts,
                    })

            primary = min(chain, key=lambda c: abs(c['delta'] - 0.20))
            if abs(primary['delta'] - 0.20) <= 0.12:
                prem = primary['mid']
                strike = primary['strike']
                assigned = exp_actual_price > strike
                assign_cost = (max(0, exp_actual_price - strike)
                               * tradeable_shares if assigned else 0)
                total_prem = prem * tradeable_shares
                net = total_prem - assign_cost

                monthly_results.append({
                    'month': month_label, 'year': year,
                    'sell_date': sell_date_str, 'expiration': expiration,
                    'sell_price_adj': round(sell_adj_price, 2),
                    'sell_price_actual': round(sell_actual_price, 2),
                    'exp_price_actual': round(exp_actual_price, 2),
                    'strike': strike, 'delta': round(primary['delta'], 4),
                    'iv': round(primary['iv'], 4),
                    'bid': round(primary['bid'], 2),
                    'ask': round(primary['ask'], 2),
                    'premium_per_share': round(prem, 2),
                    'total_premium': round(total_prem, 2),
                    'assigned': assigned,
                    'assignment_cost': round(assign_cost, 2),
                    'net_cc': round(net, 2),
                    'contracts': current_contracts,
                    'tradeable_shares': tradeable_shares,
                    'split_ratio': split_ratio,
                })

                status = "ASSIGNED" if assigned else "expired"
                print(f"  {month_label}: S=${sell_actual_price:.0f} K=${strike:.0f} "
                      f"Δ={primary['delta']:.3f} bid=${primary['bid']:.2f} "
                      f"ask=${primary['ask']:.2f} mid=${prem:.2f} "
                      f"exp=${exp_actual_price:.0f} [{status}] "
                      f"net=${net:+,.0f} ({current_contracts}c)")
            else:
                print(f"  {month_label}: Best Δ={primary['delta']:.3f} too far from 0.20")

    save_cache(cache)
    print(f"  API calls: {api_calls}, Skipped(no data): {skipped_no_data}, "
          f"Skipped(no contracts): {skipped_no_contracts}")

    final_date, final_adj_price = nearest_trading_day(
        prices, date(2025, 12, 31), direction=-1)
    if final_adj_price is None:
        final_adj_price = prices.iloc[-1]
    bh_return = (final_adj_price / init_adj_price - 1) * 100
    # B&H final: all shares (after all splits) × final actual price + remaining cash
    final_split = get_split_ratio(symbol, date(2025, 12, 31))
    final_actual_price = final_adj_price * final_split
    all_splits_mult = 1
    for s_date, s_factor in SPLITS.get(symbol, []):
        if init_date < s_date:
            all_splits_mult *= s_factor
    final_shares = init_actual_shares * all_splits_mult
    bh_final = final_shares * final_actual_price + remaining_cash

    total_prem_d20 = sum(r['total_premium'] for r in monthly_results)
    total_assign_d20 = sum(r['assignment_cost'] for r in monthly_results)
    net_cc_d20 = total_prem_d20 - total_assign_d20
    times_assigned_d20 = sum(1 for r in monthly_results if r['assigned'])

    yearly = {}
    for r in monthly_results:
        yr = r['year']
        if yr not in yearly:
            yearly[yr] = {'premium': 0, 'assignment': 0, 'net': 0,
                          'months': 0, 'assigned': 0}
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

    cc_months = len(monthly_results)
    total_months_possible = len(monthly_exps)

    summary = {
        'symbol': symbol,
        'initial_price_adj': round(init_adj_price, 2),
        'initial_price_actual': round(init_actual_price, 2),
        'final_price_adj': round(final_adj_price, 2),
        'init_shares_actual': init_actual_shares,
        'init_contracts': init_contracts,
        'remaining_cash': round(remaining_cash, 2),
        'bh_return_pct': round(bh_return, 1),
        'bh_final_value': round(bh_final, 2),
        'yearly_bh_returns': yearly_bh,
        'total_premium_d20': round(total_prem_d20, 2),
        'total_assignment_d20': round(total_assign_d20, 2),
        'net_cc_d20': round(net_cc_d20, 2),
        'net_cc_pct_d20': round(net_cc_d20 / INITIAL_CAPITAL * 100, 1),
        'times_assigned_d20': times_assigned_d20,
        'cc_months': cc_months,
        'total_months_possible': total_months_possible,
        'skipped_no_contracts': skipped_no_contracts,
        'yearly': {str(k): v for k, v in yearly.items()},
        'delta_grid': delta_grid_summary,
        'optimal_delta': best_delta[0] if best_delta else None,
        'optimal_net_cc': round(best_delta[1]['net_cc'], 2) if best_delta else 0,
        'optimal_net_cc_pct': best_delta[1]['net_cc_pct'] if best_delta else 0,
        'monthly_detail': monthly_results,
    }

    print(f"\n  === {symbol} SUMMARY ===")
    print(f"  B&H Return: {bh_return:+.1f}%  Final: ${bh_final:,.0f}")
    print(f"  CC Months: {cc_months}/{total_months_possible} "
          f"(skipped {skipped_no_contracts} months, no contracts)")
    print(f"  CC Premium (Δ=0.20): ${total_prem_d20:,.0f}")
    print(f"  Assignment Cost: ${total_assign_d20:,.0f}")
    print(f"  Net CC Overlay: ${net_cc_d20:+,.0f} ({net_cc_d20/INITIAL_CAPITAL*100:+.1f}%)")
    print(f"  Times Assigned: {times_assigned_d20}/{cc_months}")
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
    print("  COVERED CALL BACKTEST V3 — REAL DATA + SPLIT HANDLING")
    print("  Period: Jan 2021 – Dec 2025 | Capital: $100K/stock")
    print("=" * 70)

    try:
        resp = SESSION.get(
            f"{BASE_URL}/v3/option/list/expirations?symbol=AAPL", timeout=30)
        if resp.status_code != 200 or '<html>' in resp.text.lower():
            print("ERROR: ThetaData API not responding")
            return
    except Exception as e:
        print(f"ERROR: Cannot connect to ThetaData API: {e}")
        return
    print("ThetaData API: OK")

    v2_results = {}
    if os.path.exists(V2_RESULTS_FILE):
        with open(V2_RESULTS_FILE, 'r') as f:
            v2_results = json.load(f)
        print(f"Loaded V2 results for: {list(v2_results.keys())}")

    stock_prices = download_stock_prices()
    cache = load_cache()
    all_results = {}

    for sym in ["AAPL", "MSFT"]:
        if sym in v2_results:
            all_results[sym] = v2_results[sym]
            print(f"\n  Using cached V2 results for {sym}")

    for sym in ["GOOGL", "AMZN", "NVDA", "META", "TSLA"]:
        print(f"\n[Processing {sym}]")
        result = process_stock(sym, stock_prices, cache)
        if result:
            all_results[sym] = result
            with open(RESULTS_FILE, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"  Saved {sym} results.")

    save_cache(cache)

    with open(RESULTS_FILE, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n{'='*90}")
    print(f"  FINAL COMPARISON — REAL OPTION PREMIUMS")
    print(f"{'='*90}")
    print(f"\n{'Stock':<8} {'B&H%':>8} {'CC Prem':>10} {'Assign$':>10} {'NetCC$':>10} "
          f"{'NetCC%':>8} {'Comb%':>8} {'OptΔ':>6} {'OptNet%':>8} {'CC/60mo':>8}")
    print("-" * 96)

    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            bh = r['bh_return_pct']
            net_pct = r['net_cc_pct_d20']
            comb = bh + net_pct
            od = r.get('optimal_delta', 'N/A')
            on = r.get('optimal_net_cc_pct', 0)
            cc_mo = r.get('cc_months', r.get('total_months', 60))
            print(f"{sym:<8} {bh:>+7.1f}% ${r['total_premium_d20']:>9,.0f} "
                  f"${r['total_assignment_d20']:>9,.0f} ${r['net_cc_d20']:>9,.0f} "
                  f"{net_pct:>+7.1f}% {comb:>+7.1f}% {od:>6} {on:>+7.1f}% "
                  f"{cc_mo:>5}/60")

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
                ret = r['yearly_bh_returns'].get(yr, r['yearly_bh_returns'].get(str(yr), 0))
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
