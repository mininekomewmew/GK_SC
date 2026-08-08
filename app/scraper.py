import re
import json
import time
import requests
from lxml import html
from typing import List, Dict, Set

class CacheManager:
    def __init__(self):
        self._cache = {}

    def get(self, key: str):
        now = time.time()
        if key in self._cache:
            data, expiry = self._cache[key]
            if now < expiry:
                return data
            else:
                del self._cache[key]
        return None

    def set(self, key: str, data, ttl: int):
        self._cache[key] = (data, time.time() + ttl)

    def clear(self):
        self._cache.clear()

class FootballScraper:
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_today_matches(self) -> List[Dict]:
        cache_key = "today_matches"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        urls = ["https://goal7.co/", "https://goal7.co/ตารางบอลพรุ่งนี้/"]
        odds_url = "https://goal7.co/data/odds.txt"
        
        try:
            odds_map = {}
            try:
                odds_resp = requests.get(odds_url, headers=self.headers, timeout=5)
                if odds_resp.status_code == 200:
                    odds_map = odds_resp.json()
            except Exception:
                pass

            matches = []
            seen_ids = set()
            
            for url in urls:
                try:
                    response = requests.get(url, headers=self.headers, timeout=10)
                    if response.status_code != 200:
                        continue
                    tree = html.fromstring(response.content)
                    rows = tree.xpath("//tr[@class='utable_tr']")
                    for row in rows:
                        row_id = row.attrib.get("id")
                        analysis_links = row.xpath(".//a[contains(@href, 'analyse/?id=')]/@href")
                        match_id = analysis_links[0].split("id=")[-1].strip() if analysis_links else row_id
                        
                        if not match_id or match_id in seen_ids:
                            continue
                            
                        time_cols = row.xpath("./td[contains(@class, 'utable_f1')]/text()")
                        time_str = time_cols[0].strip() if time_cols else ""
                        
                        home_cols = row.xpath("./td[contains(@class, 'utable_f2')]//span/text()")
                        home_team = home_cols[0].strip() if home_cols else ""
                        
                        away_cols = row.xpath("./td[contains(@class, 'utable_f4')]//span/text()")
                        away_team = away_cols[0].strip() if away_cols else ""
                        
                        home_fav = bool(row.xpath("./td[contains(@class, 'utable_f2')]//span[contains(@class, 'ured')]"))
                        odds_col = row.xpath("./td[contains(@class, 'classodds')]/text()")
                        handicap_text = odds_col[0].strip() if odds_col else ""
                        
                        handicap = "-" + handicap_text if home_fav and handicap_text and not handicap_text.startswith("-") and handicap_text != "เสมอ" else handicap_text
                        
                        live_id = row_id
                        if not live_id:
                            live_id_el = row.xpath(".//input[@class='live_id']/@value")
                            live_id = live_id_el[0].strip() if live_id_el else None

                        home_odds, away_odds = None, None
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
                self.cache.set(cache_key, matches, 300)
            return matches
        except Exception:
            return []

    def _extract_json_block(self, html_content: str, var_name: str) -> dict:
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
                        try:
                            cleaned = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
                            import ast
                            return ast.literal_eval(cleaned)
                        except Exception:
                            return {}
        return {}

    def fetch_match_analysis(self, match_id: str) -> dict:
        cache_key = f"analysis_{match_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"https://goal7.co/analyse/?id={match_id}"
        response = requests.get(url, headers=self.headers, timeout=10)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch analysis page: {response.status_code}")
        
        html_content = response.text
        vars_to_extract = ["gameInfo", "gameTeamHistory", "gamehistory", "gameTeamFixture"]
        result = {var_name: self._extract_json_block(html_content, var_name) for var_name in vars_to_extract}
                
        if result:
            self.cache.set(cache_key, result, 300)
        return result

    def fetch_polball_analysis(self, home_team: str, away_team: str) -> dict:
        cache_key = "polball_home"
        html_content = self.cache.get(cache_key)
        if html_content is None:
            try:
                url = "https://www.polball.club/"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    html_content = resp.text
                    self.cache.set(cache_key, html_content, 600)
            except Exception:
                pass
                
        if not html_content:
            return None
            
        try:
            tree = html.fromstring(html_content)
            links = tree.xpath("//a")
            matched_url = None
            
            def clean_team_name(name: str) -> str:
                name = re.sub(r'\[.*?\]', '', name)
                name = re.sub(r'\(.*?\)', '', name)
                return name.strip().lower().replace(' ', '').replace('fc', '')
                
            h_clean = clean_team_name(home_team)
            a_clean = clean_team_name(away_team)
            
            # Use 7 chars for Thai to ensure uniqueness, fallback to full name if shorter
            h_prefix = h_clean[:7] if len(h_clean) >= 7 else h_clean
            a_prefix = a_clean[:7] if len(a_clean) >= 7 else a_clean
            
            for l in links:
                href = l.attrib.get("href", "")
                if not href: continue
                text_content = " ".join([t.strip() for t in l.xpath(".//text()") if t.strip()]).lower().replace(' ', '').replace('fc', '')
                if "วิเคราะห์บอล" in text_content or "-vs-" in text_content or "vs" in href or "วิเคราะห์บอล" in href:
                    if (h_prefix and h_prefix in text_content) or (a_prefix and a_prefix in text_content):
                        # Ensure we don't match completely different teams due to short prefix
                        if "vs" in text_content or "-vs-" in text_content:
                            if not (h_prefix in text_content or a_prefix in text_content):
                                continue
                        matched_url = href
                        break
                    
            if not matched_url: return None
                
            detail_key = f"polball_detail_{matched_url}"
            detail_html = self.cache.get(detail_key)
            if detail_html is None:
                resp = requests.get(matched_url, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    detail_html = resp.text
                    self.cache.set(detail_key, detail_html, 600)
                    
            if not detail_html: return None
                
            detail_tree = html.fromstring(detail_html)
            p_nodes = detail_tree.xpath("//p | //blockquote | //div[contains(@class, 'entry-content')]")
            
            pol_tip, pol_score = None, None
            for p in p_nodes:
                text_content = " ".join([t.strip() for t in p.xpath(".//text()") if t.strip()])
                if "ทีเด็ดบอล :" in text_content:
                    pol_tip = text_content.replace("ทีเด็ดบอล :", "").strip()
                elif "ผลที่คาด :" in text_content:
                    pol_score = text_content.replace("ผลที่คาด :", "").strip()
                    
            if pol_tip or pol_score:
                return {"url": matched_url, "tip": pol_tip, "score": pol_score}
        except Exception:
            pass
        return None

    def _get_polball_teams(self) -> Set[str]:
        cache_key = "polball_teams_set"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return set(cached)
            
        html_content = self.cache.get("polball_home")
        if html_content is None:
            try:
                resp = requests.get("https://www.polball.club/", headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    html_content = resp.text
                    self.cache.set("polball_home", html_content, 600)
            except Exception:
                pass
                
        if not html_content: return set()
            
        try:
            tree = html.fromstring(html_content)
            links = tree.xpath("//a")
            teams = set()
            for l in links:
                text_content = " ".join([t.strip() for t in l.xpath(".//text()") if t.strip()]).lower().replace(' ', '').replace('fc', '')
                if "วิเคราะห์บอล" in text_content or "-vs-" in text_content:
                    parts = text_content.split('-vs-')
                    if len(parts) == 2:
                        h_team = parts[0].split(':')[-1].strip()
                        if h_team: teams.add(h_team[:7])
                        a_team = parts[1].strip()
                        if a_team: teams.add(a_team[:7])
            
            self.cache.set(cache_key, list(teams), 600)
            return teams
        except Exception:
            return set()

    def is_major_match(self, home_team: str, away_team: str) -> bool:
        def clean_team_name(name: str) -> str:
            name = re.sub(r'\[.*?\]', '', name)
            name = re.sub(r'\(.*?\)', '', name)
            return name.strip().lower().replace(' ', '').replace('fc', '')
            
        h_clean = clean_team_name(home_team)
        a_clean = clean_team_name(away_team)
        
        h_prefix = h_clean[:7] if len(h_clean) >= 7 else h_clean
        a_prefix = a_clean[:7] if len(a_clean) >= 7 else a_clean
        
        pt = self._get_polball_teams()
        if not pt:
            return True
        return h_prefix in pt or a_prefix in pt

    def fetch_finished_scores(self) -> dict:
        urls = ["https://goal7.co/", "https://goal7.co/ผลบอลย้อนหลัง/", "https://goal7.co/ตารางบอลพรุ่งนี้/"]
        scores = {}
        for url in urls:
            try:
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200: continue
                tree = html.fromstring(resp.content)
                rows = tree.xpath("//tr[contains(@class, 'utable_tr')]")
                for row in rows:
                    analysis_links = row.xpath(".//a[contains(@href, 'analyse/?id=')]/@href")
                    match_id = analysis_links[0].split("id=")[-1].strip() if analysis_links else row.attrib.get("id")
                    if not match_id: continue
                        
                    cols = row.xpath("./td")
                    text_content = [c.text_content().strip() for c in cols]
                    if len(text_content) > 7:
                        score = text_content[7]
                        if '?' not in score and '-' in score:
                            scores[match_id] = score.replace(" ", "")
            except Exception:
                pass
        return scores
