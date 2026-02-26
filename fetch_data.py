#!/usr/bin/env python3
"""
Denver Temperature Dashboard - Data Fetcher

Fetches daily temperature data from the Open-Meteo Archive API for Denver, CO.
Computes 30-year normals, trailing averages, percentile envelopes, and monthly stats.

Usage:
    pip install requests
    python fetch_data.py

Output: data.js (JavaScript file for the dashboard)
"""

import requests
import json
import datetime
import time
import sys
from collections import defaultdict

# --- Configuration ---
LATITUDE = 39.7392
LONGITUDE = -104.9903
TIMEZONE = "America/Denver"
TEMP_UNIT = "fahrenheit"
RATE_LIMIT_SLEEP = 0.3  # seconds between API calls

# Historical range: 30 years (1996-2025)
HIST_START_YEAR = 1996
HIST_END_YEAR = 2025
TRAILING_YEARS = 10  # 2016-2025 for trailing average

TODAY = datetime.date.today()
CURRENT_YEAR = TODAY.year

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def fetch_year(year, end_date=None):
    """Fetch daily high/low temperature data for a given year."""
    start = f"{year}-01-01"
    end = end_date or f"{year}-12-31"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": TIMEZONE,
        "temperature_unit": TEMP_UNIT,
    }

    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                return {
                    "dates": daily.get("time", []),
                    "high": daily.get("temperature_2m_max", []),
                    "low": daily.get("temperature_2m_min", []),
                }
            elif resp.status_code in (429, 503):
                wait = (attempt + 1) * 5
                print(f"  Rate limited ({resp.status_code}), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  API error {resp.status_code}: {resp.text[:200]}")
                if attempt < 2:
                    time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}")
            if attempt < 2:
                time.sleep(2)
    return None


def md_key(date_str):
    """Convert YYYY-MM-DD to MM-DD for day-of-year grouping."""
    return date_str[5:]  # "MM-DD"


def is_leap_day(date_str):
    """Check if a date string is Feb 29."""
    return date_str[5:] == "02-29"


def main():
    print("=" * 60)
    print("  Denver Temperature Dashboard - Data Fetcher")
    print(f"  Year: {CURRENT_YEAR} | Today: {TODAY}")
    print("=" * 60)

    # -----------------------------------------------------------
    # Step 1: Fetch 30 historical years (1996-2025)
    # -----------------------------------------------------------
    print(f"\nFetching {HIST_END_YEAR - HIST_START_YEAR + 1} historical years ({HIST_START_YEAR}-{HIST_END_YEAR})...")

    historical = {}  # {year_str: {dates[], high[], low[]}}
    all_daily = defaultdict(lambda: {"highs": [], "lows": []})  # MM-DD -> lists

    for year in range(HIST_START_YEAR, HIST_END_YEAR + 1):
        print(f"  {year}...", end="", flush=True)
        data = fetch_year(year)
        if data is None:
            print(" FAILED")
            continue

        historical[str(year)] = data
        for i, date_str in enumerate(data["dates"]):
            h = data["high"][i]
            l = data["low"][i]
            if h is not None and l is not None:
                key = md_key(date_str)
                all_daily[key]["highs"].append(h)
                all_daily[key]["lows"].append(l)
        print(f" {len(data['dates'])} days")
        time.sleep(RATE_LIMIT_SLEEP)

    # -----------------------------------------------------------
    # Step 2: Fetch current year (2026-01-01 to today)
    # -----------------------------------------------------------
    print(f"\nFetching current year ({CURRENT_YEAR}-01-01 to {TODAY})...")
    current_data = fetch_year(CURRENT_YEAR, end_date=TODAY.isoformat())
    if current_data is None:
        print("ERROR: Could not fetch current year data")
        sys.exit(1)
    print(f"  Got {len(current_data['dates'])} days")

    # -----------------------------------------------------------
    # Step 3: Compute 30-year normals (avg high/low per day-of-year)
    # -----------------------------------------------------------
    print("\nComputing 30-year normals...")
    normals = {"dates": [], "high": [], "low": []}

    # Build ordered list of MM-DD keys (use a non-leap year as base)
    base_dates = []
    d = datetime.date(2025, 1, 1)  # non-leap year
    while d <= datetime.date(2025, 12, 31):
        base_dates.append(d.strftime("%m-%d"))
        d += datetime.timedelta(days=1)
    # Add Feb 29
    if "02-29" not in base_dates:
        base_dates.insert(base_dates.index("02-28") + 1, "02-29")

    for md in base_dates:
        highs = all_daily[md]["highs"]
        lows = all_daily[md]["lows"]
        if highs and lows:
            normals["dates"].append(md)
            normals["high"].append(round(sum(highs) / len(highs), 1))
            normals["low"].append(round(sum(lows) / len(lows), 1))

    print(f"  Normals computed for {len(normals['dates'])} days")

    # -----------------------------------------------------------
    # Step 4: Compute 10-year trailing average (2016-2025)
    # -----------------------------------------------------------
    print("Computing 10-year trailing average...")
    trailing_daily = defaultdict(lambda: {"highs": [], "lows": []})
    for year in range(HIST_END_YEAR - TRAILING_YEARS + 1, HIST_END_YEAR + 1):
        yr_str = str(year)
        if yr_str not in historical:
            continue
        data = historical[yr_str]
        for i, date_str in enumerate(data["dates"]):
            h = data["high"][i]
            l = data["low"][i]
            if h is not None and l is not None:
                key = md_key(date_str)
                trailing_daily[key]["highs"].append(h)
                trailing_daily[key]["lows"].append(l)

    trailing_avg = {"dates": [], "high": [], "low": []}
    for md in base_dates:
        highs = trailing_daily[md]["highs"]
        lows = trailing_daily[md]["lows"]
        if highs and lows:
            trailing_avg["dates"].append(md)
            trailing_avg["high"].append(round(sum(highs) / len(highs), 1))
            trailing_avg["low"].append(round(sum(lows) / len(lows), 1))

    print(f"  Trailing avg computed for {len(trailing_avg['dates'])} days")

    # -----------------------------------------------------------
    # Step 5: Compute historical envelope (percentiles per day-of-year)
    # -----------------------------------------------------------
    print("Computing historical envelope...")
    envelope = {
        "dates": [],
        "p10_high": [], "p25_high": [], "p75_high": [], "p90_high": [],
        "p10_low": [], "p25_low": [], "p75_low": [], "p90_low": [],
        "record_high": [], "record_low": [],
    }

    for md in base_dates:
        highs = sorted(all_daily[md]["highs"])
        lows = sorted(all_daily[md]["lows"])
        if len(highs) < 5 or len(lows) < 5:
            continue
        n_h = len(highs)
        n_l = len(lows)
        envelope["dates"].append(md)
        envelope["p10_high"].append(round(highs[max(0, int(n_h * 0.1))], 1))
        envelope["p25_high"].append(round(highs[max(0, int(n_h * 0.25))], 1))
        envelope["p75_high"].append(round(highs[min(n_h - 1, int(n_h * 0.75))], 1))
        envelope["p90_high"].append(round(highs[min(n_h - 1, int(n_h * 0.9))], 1))
        envelope["p10_low"].append(round(lows[max(0, int(n_l * 0.1))], 1))
        envelope["p25_low"].append(round(lows[max(0, int(n_l * 0.25))], 1))
        envelope["p75_low"].append(round(lows[min(n_l - 1, int(n_l * 0.75))], 1))
        envelope["p90_low"].append(round(lows[min(n_l - 1, int(n_l * 0.9))], 1))
        envelope["record_high"].append(round(max(highs), 1))
        envelope["record_low"].append(round(min(lows), 1))

    print(f"  Envelope computed for {len(envelope['dates'])} days")

    # -----------------------------------------------------------
    # Step 6: Monthly stats (current year vs normals, records)
    # -----------------------------------------------------------
    print("Computing monthly stats...")

    # Build monthly normals from all historical data
    monthly_hist = defaultdict(lambda: {"highs": [], "lows": []})
    for yr_str, data in historical.items():
        for i, date_str in enumerate(data["dates"]):
            h = data["high"][i]
            l = data["low"][i]
            if h is not None and l is not None:
                month_num = int(date_str[5:7])
                monthly_hist[month_num]["highs"].append(h)
                monthly_hist[month_num]["lows"].append(l)

    # Build monthly records with year tracking
    monthly_records = defaultdict(lambda: {
        "record_high": -999, "record_high_year": "",
        "record_low": 999, "record_low_year": "",
    })
    for yr_str, data in historical.items():
        for i, date_str in enumerate(data["dates"]):
            h = data["high"][i]
            l = data["low"][i]
            month_num = int(date_str[5:7])
            if h is not None and h > monthly_records[month_num]["record_high"]:
                monthly_records[month_num]["record_high"] = h
                monthly_records[month_num]["record_high_year"] = yr_str
            if l is not None and l < monthly_records[month_num]["record_low"]:
                monthly_records[month_num]["record_low"] = l
                monthly_records[month_num]["record_low_year"] = yr_str

    # Current year monthly stats
    current_monthly = defaultdict(lambda: {"highs": [], "lows": []})
    for i, date_str in enumerate(current_data["dates"]):
        h = current_data["high"][i]
        l = current_data["low"][i]
        if h is not None and l is not None:
            month_num = int(date_str[5:7])
            current_monthly[month_num]["highs"].append(h)
            current_monthly[month_num]["lows"].append(l)

    monthly = {}
    for m in range(1, 13):
        name = MONTH_NAMES[m - 1]
        hist_h = monthly_hist[m]["highs"]
        hist_l = monthly_hist[m]["lows"]
        normal_high = round(sum(hist_h) / len(hist_h), 1) if hist_h else None
        normal_low = round(sum(hist_l) / len(hist_l), 1) if hist_l else None

        cur_h = current_monthly[m]["highs"]
        cur_l = current_monthly[m]["lows"]
        avg_high = round(sum(cur_h) / len(cur_h), 1) if cur_h else None
        avg_low = round(sum(cur_l) / len(cur_l), 1) if cur_l else None

        departure_high = round(avg_high - normal_high, 1) if avg_high is not None and normal_high is not None else None
        departure_low = round(avg_low - normal_low, 1) if avg_low is not None and normal_low is not None else None

        monthly[name] = {
            "avg_high": avg_high,
            "avg_low": avg_low,
            "normal_high": normal_high,
            "normal_low": normal_low,
            "record_high": monthly_records[m]["record_high"] if monthly_records[m]["record_high"] > -999 else None,
            "record_high_year": monthly_records[m]["record_high_year"],
            "record_low": monthly_records[m]["record_low"] if monthly_records[m]["record_low"] < 999 else None,
            "record_low_year": monthly_records[m]["record_low_year"],
            "departure_high": departure_high,
            "departure_low": departure_low,
        }

    # -----------------------------------------------------------
    # Step 7: Temperature anomalies (monthly departure)
    # -----------------------------------------------------------
    print("Computing temperature anomalies...")
    anomalies = {"months": [], "high_departure": [], "low_departure": []}
    for m in range(1, 13):
        name = MONTH_NAMES[m - 1]
        info = monthly[name]
        if info["departure_high"] is not None:
            anomalies["months"].append(name[:3])
            anomalies["high_departure"].append(info["departure_high"])
            anomalies["low_departure"].append(info["departure_low"])

    # -----------------------------------------------------------
    # Step 8: Summary stats
    # -----------------------------------------------------------
    print("Computing summary stats...")

    # Today's temps (most recent day with data)
    today_high = None
    today_low = None
    today_date = None
    for i in range(len(current_data["dates"]) - 1, -1, -1):
        if current_data["high"][i] is not None and current_data["low"][i] is not None:
            today_high = current_data["high"][i]
            today_low = current_data["low"][i]
            today_date = current_data["dates"][i]
            break

    # YTD average high
    valid_highs = [h for h in current_data["high"] if h is not None]
    valid_lows = [l for l in current_data["low"] if l is not None]
    ytd_avg_high = round(sum(valid_highs) / len(valid_highs), 1) if valid_highs else None

    # YTD normal average high (average of normals for days elapsed)
    ytd_normal_highs = []
    for date_str in current_data["dates"]:
        md = md_key(date_str)
        idx = normals["dates"].index(md) if md in normals["dates"] else -1
        if idx >= 0:
            ytd_normal_highs.append(normals["high"][idx])
    ytd_normal_avg_high = round(sum(ytd_normal_highs) / len(ytd_normal_highs), 1) if ytd_normal_highs else None

    # Hottest day this year
    hottest_temp = -999
    hottest_date = None
    for i, h in enumerate(current_data["high"]):
        if h is not None and h > hottest_temp:
            hottest_temp = h
            hottest_date = current_data["dates"][i]

    # Coldest day this year (lowest low)
    coldest_temp = 999
    coldest_date = None
    for i, l in enumerate(current_data["low"]):
        if l is not None and l < coldest_temp:
            coldest_temp = l
            coldest_date = current_data["dates"][i]

    # Days below freezing (low <= 32)
    days_below_freezing = sum(1 for l in current_data["low"] if l is not None and l <= 32)

    # Days above 90
    days_above_90 = sum(1 for h in current_data["high"] if h is not None and h >= 90)

    summary = {
        "today_high": today_high,
        "today_low": today_low,
        "today_date": today_date,
        "ytd_avg_high": ytd_avg_high,
        "ytd_normal_avg_high": ytd_normal_avg_high,
        "hottest_day": {"date": hottest_date, "temp": hottest_temp if hottest_temp > -999 else None},
        "coldest_day": {"date": coldest_date, "temp": coldest_temp if coldest_temp < 999 else None},
        "days_below_freezing": days_below_freezing,
        "days_above_90": days_above_90,
    }

    # -----------------------------------------------------------
    # Step 9: Prepare historical years for output
    # -----------------------------------------------------------
    print("Preparing historical year data...")
    hist_output = {}
    for yr_str, data in historical.items():
        hist_output[yr_str] = {
            "dates": data["dates"],
            "high": [round(v, 1) if v is not None else None for v in data["high"]],
            "low": [round(v, 1) if v is not None else None for v in data["low"]],
        }

    # -----------------------------------------------------------
    # Step 10: Assemble and write output
    # -----------------------------------------------------------
    print("\nWriting data.js...")

    output = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "year": CURRENT_YEAR,
        "location": {
            "name": "Denver, CO",
            "lat": LATITUDE,
            "lon": LONGITUDE,
            "elevation": "5,280 ft",
        },
        "current_year": {
            "dates": current_data["dates"],
            "high": [round(v, 1) if v is not None else None for v in current_data["high"]],
            "low": [round(v, 1) if v is not None else None for v in current_data["low"]],
        },
        "trailing_avg": trailing_avg,
        "normals": normals,
        "historical_envelope": envelope,
        "historical_years": hist_output,
        "monthly": monthly,
        "anomalies": anomalies,
        "summary": summary,
    }

    json_str = json.dumps(output, indent=2)
    with open("data.js", "w") as f:
        f.write(f"const DATA = {json_str};\n")

    print(f"\nDone! File written:")
    print(f"  data.js  ({len(json_str) // 1024} KB)")
    print(f"\nSummary:")
    print(f"  Historical years: {HIST_START_YEAR}-{HIST_END_YEAR}")
    print(f"  Current year days: {len(current_data['dates'])}")
    if today_high is not None:
        print(f"  Latest: {today_date} — High {today_high}°F, Low {today_low}°F")
    if ytd_avg_high is not None:
        print(f"  YTD avg high: {ytd_avg_high}°F (normal: {ytd_normal_avg_high}°F)")
    print(f"  Days below freezing: {days_below_freezing}")
    print(f"  Days above 90°F: {days_above_90}")


if __name__ == "__main__":
    main()
