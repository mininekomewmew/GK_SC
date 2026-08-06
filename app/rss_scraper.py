import requests
import xml.etree.ElementTree as ET
import re
from app.scraper import get_cached, set_cached
from app.club_elo import THAI_TO_ELO

# We use Thairath (Thai) and ESPN / BBC (English) RSS feeds
RSS_FEEDS = {
    "thairath": {"url": "https://www.thairath.co.th/rss/sport", "lang": "th", "source": "ไทยรัฐ"},
    "bbc": {"url": "https://www.bbc.co.uk/sport/football/rss.xml", "lang": "en", "source": "BBC Sport"},
    "espn": {"url": "https://www.espn.com/espn/rss/soccer/news", "lang": "en", "source": "ESPN FC"}
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_team_name(name: str) -> str:
    # Strip rank prefixes like [D1-5] or [12]
    name = re.sub(r"^\[[^\]]+\]", "", name)
    # Strip rank suffixes like [D1-5] or [12]
    name = re.sub(r"\[[^\]]+\]$", "", name)
    # Strip (N)
    name = name.replace("(N)", "")
    return name.strip()

def fetch_rss_feeds() -> list:
    cache_key = "all_rss_news"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    all_items = []
    for key, cfg in RSS_FEEDS.items():
        try:
            resp = requests.get(cfg["url"], headers=HEADERS, timeout=5)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item"):
                    title = item.find("title")
                    link = item.find("link")
                    desc = item.find("description")
                    
                    title_txt = title.text.strip() if title is not None and title.text else ""
                    link_txt = link.text.strip() if link is not None and link.text else ""
                    desc_txt = desc.text.strip() if desc is not None and desc.text else ""
                    
                    if title_txt:
                        all_items.append({
                            "title": title_txt,
                            "link": link_txt,
                            "description": desc_txt,
                            "lang": cfg["lang"],
                            "source": cfg["source"]
                        })
        except Exception:
            pass

    # Cache for 15 minutes
    set_cached(cache_key, all_items, 900)
    return all_items

def get_news_for_match(home_team: str, away_team: str) -> list:
    news_items = fetch_rss_feeds()
    if not news_items:
        return []
        
    home_clean = clean_team_name(home_team)
    away_clean = clean_team_name(away_team)
    
    # Get English mappings for matching English news
    home_en = THAI_TO_ELO.get(home_team)
    away_en = THAI_TO_ELO.get(away_team)
    
    # Clean English names (e.g. ManUnited -> Manchester United, ManCity -> Manchester City)
    def expand_en_name(en_name):
        if not en_name:
            return []
        # Expand common abbreviation names
        expansions = [en_name]
        if "ManUnited" in en_name:
            expansions.extend(["Manchester United", "Man United", "United"])
        elif "ManCity" in en_name:
            expansions.extend(["Manchester City", "Man City", "City"])
        elif "RealMadrid" in en_name:
            expansions.extend(["Real Madrid", "Madrid"])
        elif "RealSociedad" in en_name:
            expansions.extend(["Real Sociedad", "Sociedad"])
        elif "AstonVilla" in en_name:
            expansions.extend(["Aston Villa", "Villa"])
        elif "CrystalPalace" in en_name:
            expansions.extend(["Crystal Palace", "Palace"])
        return expansions

    home_en_list = expand_en_name(home_en)
    away_en_list = expand_en_name(away_en)

    matches = []
    # Thai keywords mapping
    shorts = {
        "แมนฯ ยูไนเต็ด": ["แมนยู", "ยูไนเต็ด"],
        "แมนเชสเตอร์ ยูไนเต็ด": ["แมนยู", "ยูไนเต็ด"],
        "แมนเชสเตอร์ ซิตี้": ["แมนซิตี้", "ซิตี้"],
        "สเปอร์ส": ["สเปอร์"],
        "นิวคาสเซิ่ล": ["นิวคาสเซิล"],
        "ลิเวอร์พูล": ["หงส์แดง"],
        "เชลซี": ["สิงห์บลู"],
        "อาร์เซน่อล": ["ปืนใหญ่"]
    }
    
    def check_match_thai(team_name, text):
        if len(team_name) >= 3 and team_name in text:
            return True
        for k, v_list in shorts.items():
            if k in team_name:
                for v in v_list:
                    if v in text:
                        return True
        return False

    def check_match_english(en_names, text):
        text_lower = text.lower()
        for name in en_names:
            if len(name) >= 3 and name.lower() in text_lower:
                return True
        return False

    for item in news_items:
        text_to_check = item["title"] + " " + item["description"]
        if item["lang"] == "th":
            if check_match_thai(home_clean, text_to_check) or check_match_thai(away_clean, text_to_check):
                matches.append(item)
        elif item["lang"] == "en":
            if check_match_english(home_en_list, text_to_check) or check_match_english(away_en_list, text_to_check):
                matches.append(item)
            
    return matches
