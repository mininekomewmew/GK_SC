import requests
import xml.etree.ElementTree as ET
import re
from app.scraper import get_cached, set_cached

RSS_URL = "https://www.thairath.co.th/rss/sport"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_team_name(name: str) -> str:
    # Strip rank prefixes like [D1-5] or [12]
    name = re.sub(r"^\[[^\]]+\]", "", name)
    # Strip rank suffixes like [D1-5] or [12]
    name = re.sub(r"\[[^\]]+\]$", "", name)
    # Strip (N)
    name = name.replace("(N)", "")
    return name.strip()

def fetch_thairath_rss() -> list:
    cache_key = "thairath_rss"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        
        # Parse XML using ElementTree
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall(".//item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            
            title_txt = title.text.strip() if title is not None and title.text else ""
            link_txt = link.text.strip() if link is not None and link.text else ""
            desc_txt = desc.text.strip() if desc is not None and desc.text else ""
            
            if title_txt:
                items.append({
                    "title": title_txt,
                    "link": link_txt,
                    "description": desc_txt
                })
        
        # Cache for 15 minutes
        set_cached(cache_key, items, 900)
        return items
    except Exception:
        return []

def get_news_for_match(home_team: str, away_team: str) -> list:
    news_items = fetch_thairath_rss()
    if not news_items:
        return []
        
    home_clean = clean_team_name(home_team)
    away_clean = clean_team_name(away_team)
    
    matches = []
    # Keywords to extract short names (e.g. Manchester United -> แมนยู)
    # Thai news often uses short names
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
    
    def check_match(team_name, text):
        if len(team_name) >= 3 and team_name in text:
            return True
        for k, v_list in shorts.items():
            if k in team_name:
                for v in v_list:
                    if v in text:
                        return True
        return False

    for item in news_items:
        text_to_check = item["title"] + " " + item["description"]
        if check_match(home_clean, text_to_check) or check_match(away_clean, text_to_check):
            matches.append(item)
            
    return matches
