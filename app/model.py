import math
import datetime

class PredictionEngine:
    def __init__(self, elo_service):
        self.elo_service = elo_service

    def poisson_probability(self, lmbda: float, k: int) -> float:
        if lmbda <= 0:
            return 1.0 if k == 0 else 0.0
        return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

    def parse_handicap(self, handicap_str: str) -> float:
        if not handicap_str: return 0.0
        try:
            clean_str = handicap_str.replace("เสมอ", "0.0").replace(" ", "")
            if "/" in clean_str:
                parts = clean_str.split("/")
                return (float(parts[0]) + float(parts[1])) / 2.0
            return float(clean_str)
        except Exception:
            return 0.0

    def calculate_prediction(self, analysis: dict, home_odds: float = None, away_odds: float = None, handicap: str = None) -> dict:
        game_info = analysis.get("gameInfo", {})
        team_history = analysis.get("gameTeamHistory", {})
        team_fixture = analysis.get("gameTeamFixture", {})
        game_history = analysis.get("gamehistory", {})
        
        home_name = game_info.get("taname", "Home")
        away_name = game_info.get("tbname", "Away")
        handicap_str = handicap if handicap is not None else game_info.get("handicap", "0.0")
        
        match_date = None
        match_time_ms = game_info.get("time")
        match_dt = datetime.datetime.now()
        if match_time_ms:
            try:
                match_dt = datetime.datetime.fromtimestamp(float(match_time_ms) / 1000.0, datetime.timezone.utc) + datetime.timedelta(hours=7)
                match_date = match_dt.strftime("%d/%m/%Y")
            except Exception:
                pass
                
        if not match_date and game_info.get("updatedtime"):
            match_date = game_info.get("updatedtime").split()[0]
            try:
                match_dt = datetime.datetime.strptime(match_date, "%d/%m/%Y")
            except Exception:
                pass

        history_a = team_history.get("A", {}).get("all", {}).get("history", {})
        history_b = team_history.get("B", {}).get("all", {}).get("history", {})
        home_id = int(game_info.get("taid") or 0)
        away_id = int(game_info.get("tbid") or 0)
        
        def parse_team_goals(history_dict: dict, team_id: int):
            scored, conceded = [], []
            if not team_id or not history_dict: return scored, conceded
            aids, bids = history_dict.get("aid", []), history_dict.get("bid", [])
            live_a, live_b = history_dict.get("liveA", []), history_dict.get("liveB", [])
            
            for i in range(len(live_a)):
                h_id = aids[i] if i < len(aids) else 0
                a_id = bids[i] if i < len(bids) else 0
                try:
                    hg, ag = int(live_a[i]), int(live_b[i])
                except (ValueError, TypeError):
                    continue
                
                if h_id == team_id:
                    scored.append(hg); conceded.append(ag)
                elif a_id == team_id:
                    scored.append(ag); conceded.append(hg)
                else:
                    scored.append(hg); conceded.append(ag)
            return scored, conceded

        goals_scored_a, goals_conceded_a = parse_team_goals(history_a, home_id)
        goals_scored_b, goals_conceded_b = parse_team_goals(history_b, away_id)

        h2h_data = game_history.get("historymatch", {}) if game_history else {}
        h2h_scored_a, h2h_scored_b, past_results = [], [], []
        
        if h2h_data and "liveA" in h2h_data and "liveB" in h2h_data:
            aids, bids = h2h_data.get("aid", []), h2h_data.get("bid", [])
            live_a, live_b = h2h_data.get("liveA", []), h2h_data.get("liveB", [])
            dates = h2h_data.get("date", [])
            teams = game_history.get("team", {})
            
            for i in range(len(live_a)):
                try:
                    hg, ag = int(live_a[i]), int(live_b[i])
                    aid = aids[i] if i < len(aids) else 0
                    bid = bids[i] if i < len(bids) else 0
                    
                    if aid == home_id:
                        h2h_scored_a.append(hg); h2h_scored_b.append(ag)
                    else:
                        h2h_scored_a.append(ag); h2h_scored_b.append(hg)
                        
                    if len(past_results) < 5:
                        date_str = dates[i] if i < len(dates) else ""
                        team_a, team_b = teams.get(str(aid), str(aid)), teams.get(str(bid), str(bid))
                        past_results.append(f"{date_str}: {team_a} {hg}-{ag} {team_b}")
                except (ValueError, TypeError, IndexError):
                    continue

        h2h_weight, h2h_avg_a, h2h_avg_b = 0.0, 0.0, 0.0
        if h2h_scored_a:
            h2h_avg_a = sum(h2h_scored_a) / len(h2h_scored_a)
            h2h_avg_b = sum(h2h_scored_b) / len(h2h_scored_b)
            h2h_weight = 0.20
        
        def calc_weighted_avg(goals_list: list) -> float:
            if not goals_list: return 1.2
            total_wt, wt_sum = 0.0, 0.0
            for i, goals in enumerate(goals_list[:20]):
                wt = math.exp(-0.05 * i)
                wt_sum += goals * wt
                total_wt += wt
            return wt_sum / total_wt

        avg_scored_a = calc_weighted_avg(goals_scored_a)
        avg_conceded_a = calc_weighted_avg(goals_conceded_a)
        avg_scored_b = calc_weighted_avg(goals_scored_b)
        avg_conceded_b = calc_weighted_avg(goals_conceded_b)
        
        baseline = 1.35
        attack_a = avg_scored_a / baseline if avg_scored_a > 0 else 1.0
        defense_a = avg_conceded_a / baseline if avg_conceded_a > 0 else 1.0
        attack_b = avg_scored_b / baseline if avg_scored_b > 0 else 1.0
        defense_b = avg_conceded_b / baseline if avg_conceded_b > 0 else 1.0
        
        home_xg = attack_a * defense_b * baseline
        away_xg = attack_b * defense_a * baseline
        
        is_neutral = int(game_info.get("neutral") or 0) == 1
        if not is_neutral and "(N)" in game_info.get("taname", ""):
            is_neutral = True
            
        if not is_neutral:
            home_xg *= 1.10
            away_xg *= 0.90
            
        if h2h_weight > 0:
            home_xg = (1.0 - h2h_weight) * home_xg + h2h_weight * h2h_avg_a
            away_xg = (1.0 - h2h_weight) * away_xg + h2h_weight * h2h_avg_b
            
        home_elo, away_elo = self.elo_service.get_match_elo_ratings(home_name, away_name)
        if home_elo is not None and away_elo is not None:
            adjustment = (home_elo - away_elo) / 1000.0
            home_xg = max(0.1, home_xg + adjustment)
            away_xg = max(0.1, away_xg - adjustment)

        warnings = []
        
        # 1. Scoring Momentum
        def get_momentum_penalty(goals_list):
            if len(goals_list) >= 10:
                short_avg = sum(goals_list[:3]) / 3
                long_avg = sum(goals_list[:10]) / 10
                if short_avg < long_avg * 0.7:
                    return 0.95
            return 1.0
            
        mom_a = get_momentum_penalty(goals_scored_a)
        if mom_a < 1.0:
            home_xg *= mom_a
            warnings.append(f"⚠️ {home_name} ฟอร์มฝืด ยิงได้น้อยกว่าปกติ")
            
        mom_b = get_momentum_penalty(goals_scored_b)
        if mom_b < 1.0:
            away_xg *= mom_b
            warnings.append(f"⚠️ {away_name} ฟอร์มฝืด ยิงได้น้อยกว่าปกติ")

        # 2. Fitness Penalty
        def get_rest_days(history_dict):
            dates = history_dict.get("date", [])
            if not dates: return 7
            try:
                date_str = dates[0]
                if "," in date_str:
                    last_dt = datetime.datetime.strptime(date_str, "%Y,%m,%d")
                else:
                    last_dt = datetime.datetime.strptime(date_str, "%d/%m/%y")
                return (match_dt - last_dt).days
            except Exception:
                return 7

        rest_a = get_rest_days(history_a)
        if rest_a < 3:
            home_xg *= 0.90
            warnings.append(f"⚠️ {home_name} พักน้อยกว่า 3 วัน ความฟิตลดลง (-10%)")
            
        rest_b = get_rest_days(history_b)
        if rest_b < 3:
            away_xg *= 0.90
            warnings.append(f"⚠️ {away_name} พักน้อยกว่า 3 วัน ความฟิตลดลง (-10%)")

        # 3. Look-ahead Penalty
        def get_lookahead_penalty(fixture_dict, my_elo):
            if not fixture_dict or not my_elo: return 0.0
            times = fixture_dict.get("time", [])
            if not times: return 0.0
            for i, ts in enumerate(times):
                try:
                    f_dt = datetime.datetime.fromtimestamp(float(ts)/1000.0, datetime.timezone.utc) + datetime.timedelta(hours=7)
                    days_until = (f_dt - match_dt).days
                    if 0 <= days_until <= 4:
                        return 0.15 # Flat penalty if there is an upcoming match soon
                except Exception:
                    continue
            return 0.0

        lookahead_a = get_lookahead_penalty(team_fixture.get("A", {}), home_elo)
        lookahead_b = get_lookahead_penalty(team_fixture.get("B", {}), away_elo)
        
        # 4. Odds Suspicion
        p_market_implied_home, p_market_implied_away = 0.50, 0.50
        if home_odds is not None and away_odds is not None:
            try:
                p_home_raw = 1.0 / (float(home_odds) + 1.0)
                p_away_raw = 1.0 / (float(away_odds) + 1.0)
                overround = p_home_raw + p_away_raw
                if overround > 0:
                    p_market_implied_home = p_home_raw / overround
                    p_market_implied_away = p_away_raw / overround
            except Exception:
                pass

        if lookahead_a > 0:
            if p_market_implied_home < 0.45: # Suspicious odds
                lookahead_a *= 1.5
                warnings.append(f"⚠️ {home_name} มีนัดสำคัญรออยู่ + ค่าน้ำไหลแปลกๆ (กั๊กแรงชัวร์!)")
            else:
                warnings.append(f"⚠️ {home_name} มีนัดสำคัญรออยู่ในอีก 4 วัน (อาจโรเตชั่นนักเตะ)")
            home_xg *= (1.0 - lookahead_a)

        if lookahead_b > 0:
            if p_market_implied_away < 0.45:
                lookahead_b *= 1.5
                warnings.append(f"⚠️ {away_name} มีนัดสำคัญรออยู่ + ค่าน้ำไหลแปลกๆ (กั๊กแรงชัวร์!)")
            else:
                warnings.append(f"⚠️ {away_name} มีนัดสำคัญรออยู่ในอีก 4 วัน (อาจโรเตชั่นนักเตะ)")
            away_xg *= (1.0 - lookahead_b)

        p_home_win, p_draw, p_away_win = 0.0, 0.0, 0.0
        score_probs = {}
        for h in range(6):
            for a in range(6):
                prob = self.poisson_probability(home_xg, h) * self.poisson_probability(away_xg, a)
                score_probs[f"{h}-{a}"] = prob
                if h > a: p_home_win += prob
                elif h == a: p_draw += prob
                else: p_away_win += prob
                    
        total_outcome_prob = p_home_win + p_draw + p_away_win
        if total_outcome_prob > 0:
            p_home_win /= total_outcome_prob
            p_draw /= total_outcome_prob
            p_away_win /= total_outcome_prob
            
        handicap_val = self.parse_handicap(handicap_str)
        p_home_cover, p_away_cover = 0.0, 0.0
        for score_line, prob in score_probs.items():
            h, a = map(int, score_line.split("-"))
            diff = h - a + handicap_val
            if diff > 0: p_home_cover += prob
            elif diff < 0: p_away_cover += prob
                
        total_cover = p_home_cover + p_away_cover
        if total_cover > 0:
            p_home_cover /= total_cover
            p_away_cover /= total_cover
        else:
            p_home_cover, p_away_cover = 0.5, 0.5

        edge_home = p_home_cover - p_market_implied_home
        edge_away = p_away_cover - p_market_implied_away
        
        if edge_home >= 0.05:
            recommendation = f"🔮 พลังเวททำนายชี้เป้า: จัดหนัก {home_name}! (โอกาสวินแต้มต่อ: {p_home_cover * 100:.1f}%) ⚡"
            has_edge = True
        elif edge_away >= 0.05:
            recommendation = f"🔮 พลังเวททำนายชี้เป้า: จัดหนัก {away_name}! (โอกาสวินแต้มต่อ: {p_away_cover * 100:.1f}%) ⚡"
            has_edge = True
        else:
            recommendation = "💤 คู่นี้กระแสค่าน้ำไม่คุ้มค่าความเสี่ยง... ปล่อยผ่านไปก่อนดีกว่าค่ะ! 🥺"
            has_edge = False
            
        return {
            "home_team": home_name,
            "away_team": away_name,
            "home_xg": round(home_xg, 2),
            "away_xg": round(away_xg, 2),
            "p_home": round(p_home_win, 4),
            "p_draw": round(p_draw, 4),
            "p_away": round(p_away_win, 4),
            "p_home_cover": round(p_home_cover, 4),
            "p_away_cover": round(p_away_cover, 4),
            "edge_value": round(max(edge_home, edge_away), 4),
            "value_recommendation": recommendation,
            "is_best_tip": has_edge and max(edge_home, edge_away) >= 0.05,
            "date": match_date,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "past_results": past_results,
            "warnings": warnings
        }
