import re
import json
import requests
from lxml import html

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

import time

# Simple in-memory cache
# Format: {key: (data, expiry_timestamp)}
_cache = {}

def get_cached(key: str):
    now = time.time()
    if key in _cache:
        data, expiry = _cache[key]
        if now < expiry:
            return data
        else:
            del _cache[key]
    return None

def set_cached(key: str, data, ttl: int):
    _cache[key] = (data, time.time() + ttl)

def clear_cache():
    global _cache
    _cache = {}

def fetch_today_matches() -> list:
    cache_key = "today_matches"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    url = "https://goal7.co/"
    odds_url = "https://goal7.co/data/odds.txt"
    try:
        # Fetch odds map
        odds_map = {}
        try:
            odds_resp = requests.get(odds_url, headers=HEADERS, timeout=5)
            if odds_resp.status_code == 200:
                odds_map = odds_resp.json()
        except Exception:
            pass

        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []
        tree = html.fromstring(response.content)
        matches = []
        # Extract matches from rows with class 'utable_tr'
        rows = tree.xpath("//tr[@class='utable_tr']")
        for row in rows:
            row_id = row.attrib.get("id")
            analysis_links = row.xpath(".//a[contains(@href, 'analyse/?id=')]/@href")
            match_id = None
            if analysis_links:
                match_id = analysis_links[0].split("id=")[-1].strip()
            if not match_id:
                match_id = row_id

            time_cols = row.xpath("./td[contains(@class, 'utable_f1')]/text()")
            time_str = time_cols[0].strip() if time_cols else ""
            
            home_cols = row.xpath("./td[contains(@class, 'utable_f2')]//span/text()")
            home_team = home_cols[0].strip() if home_cols else ""
            
            away_cols = row.xpath("./td[contains(@class, 'utable_f4')]//span/text()")
            away_team = away_cols[0].strip() if away_cols else ""
            
            # Extract handicap line text
            odds_col = row.xpath("./td[contains(@class, 'classodds')]/text()")
            handicap = odds_col[0].strip() if odds_col else ""
            
            # Extract live ID for odds mapping (row_id is the primary live_id)
            live_id = row_id
            if not live_id:
                live_id_el = row.xpath(".//input[@class='live_id']/@value")
                live_id = live_id_el[0].strip() if live_id_el else None

            
            home_odds = None
            away_odds = None
            if live_id and live_id in odds_map:
                try:
                    home_odds = float(odds_map[live_id].get("text1"))
                    away_odds = float(odds_map[live_id].get("text3"))
                except (ValueError, TypeError, KeyError, AttributeError):
                    pass

            if match_id and home_team and away_team:
                matches.append({
                    "id": match_id,
                    "time": time_str,
                    "home_team": home_team,
                    "away_team": away_team,
                    "handicap": handicap,
                    "home_odds": home_odds,
                    "away_odds": away_odds
                })
        if matches:
            set_cached(cache_key, matches, 300)
        return matches
    except Exception:
        return []


def extract_json_block(html_content: str, var_name: str) -> dict:
    pattern = rf"var\s+{var_name}\s*=\s*"
    match = re.search(pattern, html_content)
    if not match:
        return {}
    
    start_idx = match.end()
    brace_start = html_content.find('{', start_idx)
    if brace_start == -1:
        return {}
        
    count = 0
    in_string = False
    escape = False
    quote_char = None
    
    for i in range(brace_start, len(html_content)):
        char = html_content[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if in_string:
            if char == quote_char:
                in_string = False
                quote_char = None
            continue
        if char in ('"', "'"):
            in_string = True
            quote_char = char
            continue
        if char == '{':
            count += 1
        elif char == '}':
            count -= 1
            if count == 0:
                json_str = html_content[brace_start:i+1]
                try:
                    return json.loads(json_str)
                except Exception:
                    pass
                try:
                    cleaned = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
                    import ast
                    return ast.literal_eval(cleaned)
                except Exception:
                    return {}
    return {}


def fetch_match_analysis(match_id: str) -> dict:
    cache_key = f"analysis_{match_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    url = f"https://goal7.co/analyse/?id={match_id}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch analysis page: {response.status_code}")
    
    html_content = response.text
    
    # ponytail: gamePrediction is not trustworthy, so we exclude it.
    vars_to_extract = ["gameInfo", "gameTeamHistory"]
    result = {}
    
    for var_name in vars_to_extract:
        result[var_name] = extract_json_block(html_content, var_name)
            
    if result:
        set_cached(cache_key, result, 300)
    return result

