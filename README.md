# Denver Temperature Dashboard

Visualizes Denver daily temperature data against 30-year historical norms.

## Quick Start

1. Install Python dependency:
   ```
   pip install requests
   ```

2. Fetch the latest data:
   ```
   python fetch_data.py
   ```

3. Open the dashboard:
   ```
   open index.html
   ```

## What's on the Dashboard

- **Hero cards**: Latest high, YTD average vs normal, hottest day, days below freezing
- **Main chart**: Daily high/low temperature range with 10-year trailing averages and historical percentile bands
- **Monthly averages**: Grouped bar chart comparing this year to 30-year normals
- **Temperature anomaly**: Monthly departure from normal (high and low)
- **Monthly table**: Detailed breakdown with records and departure badges

## Data Source

[Open-Meteo Historical Weather API](https://open-meteo.com/) — free, no auth needed.
Denver coordinates: 39.7392°N, 104.9903°W.
