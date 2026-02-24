"""
Covered Call Backtest with REAL ThetaData Option Premiums
=========================================================
Period: January 2021 – December 2025 (60 months)
Initial Investment: $100,000 per stock
Stocks: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA

Stock prices: Yahoo Finance (split-adjusted)
Option premiums: REAL bid/ask from ThetaData API v3 (OPTION.STANDARD subscription)
"""

import json
import time
import math
import requests
import pandas as pd
import yfinance as yf
from datetime import date, timedelta, datetime
from collections import defaultdict

BASE_URL = "http://127.0.0.1:25503"
SESSION = requests.Session()
STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
INITIAL_CAPITAL = 100_000
TARGET_DELTAS = [0.05, 0.08, 0.10, 0.15, 0.18, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


def third_friday(year, month):
    """Return the 3rd Friday of a given month."""
    d = date(year, month, 1)
    day_of_week = d.weekday()
    first_friday = d + timedelta(days=(4 - day_of_week) % 7)
    return first_friday + timedelta(weeks=2)


def download_all_stock_prices():
    """Download all stock prices in bulk via yfinance."""
    print("Downloading stock prices from Yahoo Finance...")
    tickers = " ".join(STOCKS)
    data = yf.download(tickers, start="2020-12-28", end="2026-01-05", auto_adjust=True)
    close = data['Close']
    print(f"  Downloaded {len(close)} trading days for {len(STOCKS)} stocks")
    return close


def get_expirations(symbol):
    """Get all available option expirations for a symbol."""
    url = f"{BASE_URL}/v3/option/list/expirations?symbol={symbol}"
    resp = SESSION.get(url, timeout=15)
    lines = resp.text.strip().split('\n')[1:]
    exps = []
    for line in lines:
        parts = line.strip().replace('"', '').split(',')
        if len(parts) >= 2:
            exps.append(parts[1])
    return exps


def get_strikes(symbol, expiration):
    """Get available strikes for a symbol/expiration."""
    url = f"{BASE_URL}/v3/option/list/strikes?symbol={symbol}&expiration={expiration}"
    resp = SESSION.get(url, timeout=15)
    lines = resp.text.strip().split('\n')[1:]
    strikes = []
    for line in lines:
        parts = line.strip().replace('"', '').split(',')
        if len(parts) >= 2:
            try:
                strikes.append(float(parts[1]))
            except ValueError:
                pass
    return sorted(strikes)


def get_option_greeks_eod(symbol, expiration, strike, sell_date_str):
    """Get EOD option greeks for a specific CALL contract on a specific date."""
    url = (f"{BASE_URL}/v3/option/history/greeks/eod"
           f"?symbol={symbol}&expiration={expiration}"
           f"&strike={strike}&right=C"
           f"&start_date={sell_date_str}&end_date={sell_date_str}")
    try:
        resp = SESSION.get(url, timeout=15)
        text = resp.text.strip()
        if 'Error' in text or 'error' in text.lower() or 'subscription' in text.lower():
            return None
        lines = text.split('\n')
        if len(lines) < 2:
            return None
        header = lines[0].split(',')
        values = lines[1].split(',')
        if len(values) < len(header):
            return None
        row = {}
        for h, v in zip(header, values):
            h = h.strip()
            v = v.strip().replace('"', '')
            row[h] = v
        return row
    except Exception:
        return None


def select_otm_strikes(all_strikes, stock_price):
    """Select OTM call strikes covering delta range 0.50 (ATM) to 0.03 (deep OTM)."""
    # ATM to ~25% OTM should cover the full delta range
    lower = stock_price * 0.97  # slightly ITM for ATM reference
    upper = stock_price * 1.30  # 30% OTM for deep OTM
    relevant = [s for s in all_strikes if lower <= s <= upper]

    if len(relevant) > 30:
        step = max(1, len(relevant) // 30)
        relevant = relevant[::step]
    elif len(relevant) < 5:
        idx = next((i for i, s in enumerate(all_strikes) if s >= stock_price), len(all_strikes) // 2)
        start = max(0, idx - 3)
        end = min(len(all_strikes), idx + 15)
        relevant = all_strikes[start:end]

    return relevant


def query_chain_greeks(symbol, expiration, strikes, sell_date_str):
    """Query greeks for multiple strikes. Returns list of parsed option data."""
    results = []
    for strike in strikes:
        data = get_option_greeks_eod(symbol, expiration, strike, sell_date_str)
        if data:
            try:
                delta = float(data.get('delta', 0))
                bid = float(data.get('bid', 0))
                ask = float(data.get('ask', 0))
                close_px = float(data.get('close', 0))
                iv = float(data.get('implied_vol', 0))
                mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else close_px
                if delta > 0 and mid > 0:
                    results.append({
                        'strike': strike,
                        'delta': delta,
                        'bid': bid,
                        'ask': ask,
                        'mid': mid,
                        'close': close_px,
                        'iv': iv,
                    })
            except (ValueError, TypeError):
                pass
        time.sleep(0.02)
    return results


def find_best_for_delta(chain, target_delta):
    """Find the option closest to target delta from the chain."""
    if not chain:
        return None
    best = min(chain, key=lambda c: abs(c['delta'] - target_delta))
    if abs(best['delta'] - target_delta) > 0.12:
        return None
    return best


def nearest_trading_day(prices_series, target_date, direction=1, max_tries=10):
    """Find the nearest trading day with data."""
    d = target_date
    for _ in range(max_tries):
        ts = pd.Timestamp(d)
        if ts in prices_series.index:
            val = prices_series.loc[ts]
            if not pd.isna(val):
                return d, float(val)
        d += timedelta(days=direction)
    return None, None


def process_stock(symbol, stock_prices):
    """Run the full CC backtest for one stock using real option data."""
    print(f"\n{'='*70}")
    print(f"  Processing {symbol}")
    print(f"{'='*70}")

    prices = stock_prices[symbol].dropna()

    # Get all available expirations
    all_exps = get_expirations(symbol)
    exp_set = set(all_exps)

    # Build monthly expiration map
    monthly_exps = {}
    for year in range(2021, 2026):
        for month in range(1, 13):
            tf = third_friday(year, month)
            tf_str = tf.strftime('%Y-%m-%d')
            if tf_str in exp_set:
                monthly_exps[(year, month)] = tf_str
            else:
                for offset in [-1, 1, -2, 2, -3, 3]:
                    alt = (tf + timedelta(days=offset)).strftime('%Y-%m-%d')
                    if alt in exp_set:
                        monthly_exps[(year, month)] = alt
                        break

    print(f"  Found {len(monthly_exps)} monthly expirations")

    # Initial price and share count
    init_date, init_price = nearest_trading_day(prices, date(2021, 1, 4), direction=1)
    if init_price is None:
        print(f"  ERROR: No initial price for {symbol}")
        return None

    shares = int(INITIAL_CAPITAL / init_price)
    contracts = shares // 100
    shares = contracts * 100
    remaining_cash = INITIAL_CAPITAL - shares * init_price

    print(f"  Initial: ${init_price:.2f} on {init_date}, Shares: {shares}, Contracts: {contracts}")

    monthly_results = []
    delta_grid_results = {d: [] for d in TARGET_DELTAS}
    last_exp_price = init_price

    for year in range(2021, 2026):
        for month in range(1, 13):
            key = (year, month)
            if key not in monthly_exps:
                continue

            expiration = monthly_exps[key]
            month_label = f"{year}-{month:02d}"

            # Sell date: first trading day of the month
            sell_date, sell_price = nearest_trading_day(prices, date(year, month, 1), direction=1)
            if sell_price is None:
                print(f"  {month_label}: No sell date data, skipping")
                continue

            # Expiration date stock price
            exp_date_obj = datetime.strptime(expiration, '%Y-%m-%d').date()
            exp_date, exp_price = nearest_trading_day(prices, exp_date_obj, direction=-1)
            if exp_price is None:
                exp_date, exp_price = nearest_trading_day(prices, exp_date_obj, direction=1)
            if exp_price is None:
                print(f"  {month_label}: No expiration price, skipping")
                continue
            last_exp_price = exp_price

            # Get available strikes
            strikes = get_strikes(symbol, expiration)
            if not strikes:
                print(f"  {month_label}: No strikes available")
                continue

            # Select relevant OTM strikes
            relevant = select_otm_strikes(strikes, sell_price)
            if not relevant:
                print(f"  {month_label}: No relevant strikes")
                continue

            # Query option chain with real greeks
            sell_date_str = sell_date.strftime('%Y-%m-%d')
            chain = query_chain_greeks(symbol, expiration, relevant, sell_date_str)

            # If no data on sell date, try 1-2 days after
            if not chain:
                for offset in [1, 2, -1]:
                    alt = (sell_date + timedelta(days=offset)).strftime('%Y-%m-%d')
                    chain = query_chain_greeks(symbol, expiration, relevant, alt)
                    if chain:
                        break

            if not chain:
                print(f"  {month_label}: No option chain data")
                continue

            # For each target delta
            for td in TARGET_DELTAS:
                best = find_best_for_delta(chain, td)
                if best:
                    prem = best['mid']
                    strike = best['strike']
                    assigned = exp_price > strike
                    assign_cost = max(0, (exp_price - strike)) * shares if assigned else 0
                    total_prem = prem * shares
                    net = total_prem - assign_cost

                    delta_grid_results[td].append({
                        'month': month_label, 'year': year,
                        'sell_price': sell_price, 'exp_price': exp_price,
                        'strike': strike, 'delta': best['delta'],
                        'iv': best['iv'], 'bid': best['bid'], 'ask': best['ask'],
                        'premium_per_share': prem, 'total_premium': total_prem,
                        'assigned': assigned, 'assignment_cost': assign_cost,
                        'net_cc': net,
                    })

            # Primary delta=0.20 result
            primary = find_best_for_delta(chain, 0.20)
            if primary:
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
                      f"Δ={primary['delta']:.3f} bid=${primary['bid']:.2f} ask=${primary['ask']:.2f} "
                      f"mid=${prem:.2f} exp=${exp_price:.0f} [{status}] net=${net:+,.0f}")
            else:
                print(f"  {month_label}: No delta=0.20 match (chain has {len(chain)} strikes)")

    # Final values
    final_date, final_price = nearest_trading_day(prices, date(2025, 12, 31), direction=-1)
    if final_price is None:
        final_price = last_exp_price
    bh_return = (final_price / init_price - 1) * 100
    bh_final = shares * final_price + remaining_cash

    total_prem_d20 = sum(r['total_premium'] for r in monthly_results)
    total_assign_d20 = sum(r['assignment_cost'] for r in monthly_results)
    net_cc_d20 = total_prem_d20 - total_assign_d20
    times_assigned_d20 = sum(1 for r in monthly_results if r['assigned'])

    # Yearly breakdown
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

    # Also compute yearly B&H returns
    yearly_bh = {}
    for year in range(2021, 2026):
        start_d, start_p = nearest_trading_day(prices, date(year, 1, 1), direction=1)
        end_d, end_p = nearest_trading_day(prices, date(year, 12, 31), direction=-1)
        if start_p and end_p:
            yearly_bh[year] = round((end_p / start_p - 1) * 100, 1)

    # Delta grid summary
    delta_grid_summary = {}
    for delta_val, results in delta_grid_results.items():
        if results:
            tp = sum(r['total_premium'] for r in results)
            ta = sum(r['assignment_cost'] for r in results)
            net = tp - ta
            avg_iv = sum(r['iv'] for r in results) / len(results)
            nassign = sum(1 for r in results if r['assigned'])

            # Yearly breakdown for this delta
            yr_net = {}
            for r in results:
                yr = r['year']
                yr_net[yr] = yr_net.get(yr, 0) + r['net_cc']

            delta_grid_summary[str(delta_val)] = {
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
    print(f"  B&H Return: {bh_return:+.1f}%  Final: ${bh_final:,.0f}")
    print(f"  CC Premium (Δ=0.20): ${total_prem_d20:,.0f}")
    print(f"  Assignment Cost: ${total_assign_d20:,.0f}")
    print(f"  Net CC Overlay: ${net_cc_d20:+,.0f} ({net_cc_d20/INITIAL_CAPITAL*100:+.1f}%)")
    print(f"  Times Assigned: {times_assigned_d20}/{len(monthly_results)}")
    if best_delta:
        print(f"  Optimal Delta: {best_delta[0]} → net: ${best_delta[1]['net_cc']:+,.0f} ({best_delta[1]['net_cc_pct']:+.1f}%)")
    print(f"  Yearly B&H: {yearly_bh}")

    return summary


def main():
    print("=" * 70)
    print("  COVERED CALL BACKTEST — REAL ThetaData Option Premiums")
    print("  Period: Jan 2021 – Dec 2025 | Capital: $100K/stock")
    print("=" * 70)

    # Verify ThetaData API
    try:
        resp = SESSION.get(f"{BASE_URL}/v3/option/list/expirations?symbol=AAPL", timeout=10)
        if 'AAPL' not in resp.text:
            print("ERROR: ThetaData API not responding")
            return
    except Exception as e:
        print(f"ERROR: Cannot connect to ThetaData API: {e}")
        return
    print("ThetaData API: OK")

    # Download all stock prices in bulk
    stock_prices = download_all_stock_prices()

    all_results = {}
    for symbol in STOCKS:
        result = process_stock(symbol, stock_prices)
        if result:
            all_results[symbol] = result

    # Save results
    output_path = "/Users/rachel/Library/CloudStorage/OneDrive-Personal/Investment/RobotInvestment/cc_real_data_results.json"
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"  Results saved to: {output_path}")
    print(f"{'='*70}")

    # Comparison table
    print(f"\n{'='*70}")
    print(f"  FINAL COMPARISON — REAL OPTION PREMIUMS")
    print(f"{'='*70}")
    print(f"\n{'Stock':<8} {'B&H%':>8} {'CC Prem':>10} {'Assign$':>10} {'NetCC%':>8} "
          f"{'Comb%':>8} {'OptΔ':>6} {'OptNet%':>8} {'#Asgn':>6}")
    print("-" * 84)

    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            bh = r['bh_return_pct']
            net_pct = r['net_cc_pct_d20']
            comb = bh + net_pct
            od = r.get('optimal_delta', 'N/A')
            on = r.get('optimal_net_cc_pct', 0)
            print(f"{sym:<8} {bh:>+7.1f}% ${r['total_premium_d20']:>9,.0f} "
                  f"${r['total_assignment_d20']:>9,.0f} {net_pct:>+7.1f}% "
                  f"{comb:>+7.1f}% {od:>6} {on:>+7.1f}% "
                  f"{r['times_assigned_d20']:>5}/{r['total_months']}")

    # Yearly Net CC
    print(f"\n{'='*70}")
    print(f"  YEARLY NET CC OVERLAY ($) at Delta=0.20")
    print(f"{'='*70}")
    print(f"{'Stock':<8}", end="")
    for yr in range(2021, 2026):
        print(f"  {yr:>9}", end="")
    print(f"  {'Total':>9}")
    print("-" * 70)
    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            print(f"{sym:<8}", end="")
            for yr in range(2021, 2026):
                yr_data = r['yearly'].get(str(yr), {})
                net = yr_data.get('net', 0)
                print(f"  ${net:>8,.0f}", end="")
            print(f"  ${r['net_cc_d20']:>8,.0f}")

    # Yearly B&H
    print(f"\n{'='*70}")
    print(f"  YEARLY BUY & HOLD RETURNS (%)")
    print(f"{'='*70}")
    print(f"{'Stock':<8}", end="")
    for yr in range(2021, 2026):
        print(f"  {yr:>8}", end="")
    print(f"  {'5-Year':>8}")
    print("-" * 62)
    for sym in STOCKS:
        if sym in all_results:
            r = all_results[sym]
            print(f"{sym:<8}", end="")
            for yr in range(2021, 2026):
                ret = r['yearly_bh_returns'].get(yr, 0)
                print(f"  {ret:>+7.1f}%", end="")
            print(f"  {r['bh_return_pct']:>+7.1f}%")

    # Delta Grid Search
    print(f"\n{'='*70}")
    print(f"  DELTA OPTIMIZATION GRID (Net CC % of $100K)")
    print(f"{'='*70}")
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


if __name__ == "__main__":
    main()
