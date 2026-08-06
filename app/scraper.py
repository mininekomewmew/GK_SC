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

    urls = ["https://goal7.co/", "https://goal7.co/ตารางบอลพรุ่งนี้/"]
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

        matches = []
        seen_ids = set()
        
        for url in urls:
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                if response.status_code != 200:
                    continue
                tree = html.fromstring(response.content)
                rows = tree.xpath("//tr[@class='utable_tr']")
                for row in rows:
                    row_id = row.attrib.get("id")
                    analysis_links = row.xpath(".//a[contains(@href, 'analyse/?id=')]/@href")
                    match_id = None
                    if analysis_links:
                        match_id = analysis_links[0].split("id=")[-1].strip()
                    if not match_id:
                        match_id = row_id
                    
                    if not match_id or match_id in seen_ids:
                        continue
                        
                    time_cols = row.xpath("./td[contains(@class, 'utable_f1')]/text()")
                    time_str = time_cols[0].strip() if time_cols else ""
                    
                    home_cols = row.xpath("./td[contains(@class, 'utable_f2')]//span/text()")
                    home_team = home_cols[0].strip() if home_cols else ""
                    
                    away_cols = row.xpath("./td[contains(@class, 'utable_f4')]//span/text()")
                    away_team = away_cols[0].strip() if away_cols else ""
                    
                    # Detect favorite team to set handicap sign (home favorite is negative, away is positive)
                    home_fav = bool(row.xpath("./td[contains(@class, 'utable_f2')]//span[contains(@class, 'ured')]"))
                    odds_col = row.xpath("./td[contains(@class, 'classodds')]/text()")
                    handicap_text = odds_col[0].strip() if odds_col else ""
                    
                    if home_fav and handicap_text and not handicap_text.startswith("-") and handicap_text != "เสมอ":
                        handicap = "-" + handicap_text
                    else:
                        handicap = handicap_text
                    
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

                    cols = row.xpath("./td")
                    pundit_tip = cols[8].text_content().strip() if len(cols) > 8 else ""

                    if match_id and home_team and away_team:
                        seen_ids.add(match_id)
                        matches.append({
                            "id": match_id,
                            "time": time_str,
                            "home_team": home_team,
                            "away_team": away_team,
                            "handicap": handicap,
                            "home_odds": home_odds,
                            "away_odds": away_odds,
                            "pundit_tip": pundit_tip
                        })
            except Exception:
                pass

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
    vars_to_extract = ["gameInfo", "gameTeamHistory", "gamehistory"]
    result = {}
    
    for var_name in vars_to_extract:
        result[var_name] = extract_json_block(html_content, var_name)
            
    if result:
        set_cached(cache_key, result, 300)
    return result

def fetch_polball_analysis(home_team: str, away_team: str) -> dict:
    cache_key = "polball_home"
    html_content = get_cached(cache_key)
    if html_content is None:
        try:
            url = "https://www.polball.club/"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                html_content = resp.text
                set_cached(cache_key, html_content, 600)  # 10 minutes cache
        except Exception:
            pass
            
    if not html_content:
        return None
        
    try:
        tree = html.fromstring(html_content)
        links = tree.xpath("//a")
        matched_url = None
        
        def clean_team_name(name: str) -> str:
            name = re.sub(r'\[.*?\]', '', name)  # Remove [...]
            name = re.sub(r'\(.*?\)', '', name)  # Remove (...)
            return name.strip().lower()
            
        h_clean = clean_team_name(home_team)
        a_clean = clean_team_name(away_team)
        
        for l in links:
            href = l.attrib.get("href", "")
            if not href:
                continue
            text_content = " ".join([t.strip() for t in l.xpath(".//text()") if t.strip()]).lower()
            # Check if it is a match analysis link
            if "วิเคราะห์บอล" in text_content or "-vs-" in text_content or "vs" in href or "วิเคราะห์บอล" in href:
                if h_clean and (h_clean in text_content or h_clean in href):
                    matched_url = href
                    break
                if a_clean and (a_clean in text_content or a_clean in href):
                    matched_url = href
                    break
                
        if not matched_url:
            return None
            
        detail_key = f"polball_detail_{matched_url}"
        detail_html = get_cached(detail_key)
        if detail_html is None:
            resp = requests.get(matched_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                detail_html = resp.text
                set_cached(detail_key, detail_html, 600)
                
        if not detail_html:
            return None
            
        detail_tree = html.fromstring(detail_html)
        p_nodes = detail_tree.xpath("//p | //blockquote | //div[contains(@class, 'entry-content')]")
        
        pol_tip = None
        pol_score = None
        for p in p_nodes:
            text_content = " ".join([t.strip() for t in p.xpath(".//text()") if t.strip()])
            if "ทีเด็ดบอล :" in text_content:
                pol_tip = text_content.replace("ทีเด็ดบอล :", "").strip()
            elif "ผลที่คาด :" in text_content:
                pol_score = text_content.replace("ผลที่คาด :", "").strip()
                
        if pol_tip or pol_score:
            return {"tip": pol_tip or "ไม่มีข้อมูล", "score": pol_score or "ไม่มีข้อมูล"}
    except Exception:
        pass
        
    return None

def fetch_finished_scores() -> dict:
    urls = ["https://goal7.co/", "https://goal7.co/ผลบอลย้อนหลัง/", "https://goal7.co/ตารางบอลพรุ่งนี้/"]
    scores = {}
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            tree = html.fromstring(resp.content)
            rows = tree.xpath("//tr[contains(@class, 'utable_tr')]")
            for row in rows:
                analysis_links = row.xpath(".//a[contains(@href, 'analyse/?id=')]/@href")
                match_id = None
                if analysis_links:
                    match_id = analysis_links[0].split("id=")[-1].strip()
                if not match_id:
                    row_id = row.attrib.get("id")
                    match_id = row_id
                if not match_id:
                    continue
                    
                cols = row.xpath("./td")
                text_content = [c.text_content().strip() for c in cols]
                if len(text_content) > 7:
                    score = text_content[7]
                    if '?' not in score and '-' in score:
                        scores[match_id] = score.replace(" ", "")
        except Exception:
            pass
    return scores

