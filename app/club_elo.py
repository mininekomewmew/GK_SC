import os
import json
import requests

class EloService:
    def __init__(self, cache_manager):
        self.cache = cache_manager
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data")
        
        with open(os.path.join(data_dir, "club_elo.json"), "r", encoding="utf-8") as f:
            self.thai_to_elo = json.load(f)
            
        with open(os.path.join(data_dir, "national_elo.json"), "r", encoding="utf-8") as f:
            self.thai_to_national_elo = json.load(f)

    def fetch_club_elo(self, club_name: str) -> float:
        cache_key = f"elo_{club_name}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"http://api.clubelo.com/{club_name}"
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                if len(lines) > 1:
                    cols = lines[-1].split(",")
                    if len(cols) > 4:
                        elo = float(cols[4])
                        self.cache.set(cache_key, elo, 86400)
                        return elo
        except Exception:
            pass
        return None

    def get_match_elo_ratings(self, home_team: str, away_team: str) -> tuple:
        home_elo = self.thai_to_national_elo.get(home_team)
        away_elo = self.thai_to_national_elo.get(away_team)
        if home_elo and away_elo:
            return home_elo, away_elo

        home_id = self.thai_to_elo.get(home_team)
        away_id = self.thai_to_elo.get(away_team)
        
        if home_id or away_id:
            h_elo = self.fetch_club_elo(home_id) if home_id else None
            a_elo = self.fetch_club_elo(away_id) if away_id else None
            return h_elo, a_elo

        return None, None
