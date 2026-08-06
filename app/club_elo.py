import requests
from app.scraper import get_cached, set_cached

# Mapping of Thai team names to ClubElo English identifiers (only for major clubs)
THAI_TO_ELO = {
    # English Premier League
    "แมนเชสเตอร์ ยูไนเต็ด": "ManUnited",
    "แมนฯ ยูไนเต็ด": "ManUnited",
    "แมนเชสเตอร์ ซิตี้": "ManCity",
    "แมนฯ ซิตี้": "ManCity",
    "ลิเวอร์พูล": "Liverpool",
    "เชลซี": "Chelsea",
    "อาร์เซน่อล": "Arsenal",
    "สเปอร์ส": "Tottenham",
    "ท็อตแน่ม ฮ็อทสเปอร์": "Tottenham",
    "นิวคาสเซิ่ล": "Newcastle",
    "แอสตัน วิลล่า": "AstonVilla",
    "เลสเตอร์": "Leicester",
    "เวสต์แฮม": "WestHam",
    "เอฟเวอร์ตัน": "Everton",
    "ไบรท์ตัน": "Brighton",
    "คริสตัล พาเลซ": "CrystalPalace",
    "วูล์ฟแฮมป์ตัน": "Wolves",
    # Spanish La Liga
    "เรอัล มาดริด": "RealMadrid",
    "บาร์เซโลน่า": "Barcelona",
    "แอตเลติโก มาดริด": "Atletico",
    "เซบีย่า": "Sevilla",
    "เรอัล โซเซียดาด": "RealSociedad",
    "บียาร์เรอัล": "Villarreal",
    # Italian Serie A
    "ยูเวนตุส": "Juventus",
    "อินเตอร์ มิลาน": "Inter",
    "เอซี มิลาน": "Milan",
    "โรม่า": "Roma",
    "เอเอส โรม่า": "Roma",
    "ลาซิโอ": "Lazio",
    "นาโปลี": "Napoli",
    "อตาลันต้า": "Atalanta",
    "ฟิออเรนติน่า": "Fiorentina",
    # German Bundesliga
    "บาเยิร์น มิวนิค": "Bayern",
    "ดอร์ทมุนด์": "Dortmund",
    "เลเวอร์คูเซ่น": "Leverkusen",
    "ไลป์ซิก": "Leipzig",
    # French Ligue 1
    "ปารีส แซงต์ แชร์กแมง": "PSG",
    "เปแอสเช": "PSG",
    "มาร์เซย์": "Marseille",
    "โมนาโก": "Monaco",
    "ลียง": "Lyon",
    # Other European
    "เบนฟิก้า": "Benfica",
    "สปอร์ติ้ง ลิสบอน": "Sporting",
    "ปอร์โต้": "Porto",
    "เซลติก": "Celtic",
    "กลาสโกว์ เรนเจอร์ส": "Rangers",
    "อาแจ็กซ์": "Ajax",
    "พีเอสวี": "PSV",
    "เฟเยนูร์ด": "Feyenoord"
}

# Approx Elo ratings for top national teams (updated periodically, fallback database)
THAI_TO_NATIONAL_ELO = {
    "อาร์เจนตินา": 2100,
    "ฝรั่งเศส": 2080,
    "สเปน": 2050,
    "อังกฤษ": 2020,
    "บราซิล": 2010,
    "เบลเยียม": 1980,
    "เนเธอร์แลนด์": 1970,
    "โปรตุเกส": 1960,
    "อิตาลี": 1950,
    "เยอรมนี": 1940,
    "โครเอเชีย": 1930,
    "อุรุกวัย": 1920,
    "โคลอมเบีย": 1910,
    "โมร็อกโก": 1900,
    "ญี่ปุ่น": 1880,
    "เซเนกัล": 1870,
    "สหรัฐอเมริกา": 1860,
    "เม็กซิโก": 1850,
    "สวิตเซอร์แลนด์": 1840,
    "เดนมาร์ก": 1830,
    "เกาหลีใต้": 1820,
    "ออสเตรเลีย": 1800,
    "ยูเครน": 1790,
    "ออสเตรีย": 1780,
    "สวีเดน": 1770,
    "ฮังการี": 1760,
    "โปแลนด์": 1750,
    "เอกวาดอร์": 1740,
    "เวลส์": 1730,
    "ไทย": 1500
}

def fetch_club_elo(club_name: str) -> float:
    """
    Fetch latest Elo rating for a club from ClubElo API.
    Cached for 24 hours. Returns None if API fails or times out.
    """
    cache_key = f"elo_{club_name}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    url = f"http://api.clubelo.com/{club_name}"
    try:
        # 3 seconds timeout to prevent blocking application
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            lines = resp.text.strip().split("\n")
            if len(lines) > 1:
                # Latest row is the last line
                cols = lines[-1].split(",")
                if len(cols) > 4:
                    elo = float(cols[4])
                    # Cache for 1 day (86400 seconds)
                    set_cached(cache_key, elo, 86400)
                    return elo
    except Exception:
        pass
    return None

def get_match_elo_ratings(home_team: str, away_team: str) -> tuple:
    """
    Get Elo ratings for home and away teams.
    Looks up in national teams first, then major clubs API.
    Returns (home_elo, away_elo) or (None, None).
    """
    # 1. Check National Teams
    home_elo = THAI_TO_NATIONAL_ELO.get(home_team)
    away_elo = THAI_TO_NATIONAL_ELO.get(away_team)
    if home_elo and away_elo:
        return home_elo, away_elo

    # 2. Check Club ELO
    home_id = THAI_TO_ELO.get(home_team)
    away_id = THAI_TO_ELO.get(away_team)
    
    if home_id or away_id:
        h_elo = fetch_club_elo(home_id) if home_id else None
        a_elo = fetch_club_elo(away_id) if away_id else None
        
        # If one club rating is found, we can approximate the other if it's a known club, 
        # otherwise return them.
        return h_elo, a_elo

    return None, None
