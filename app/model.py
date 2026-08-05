import math

def poisson_probability(lmbda: float, k: int) -> float:
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def calculate_prediction(analysis: dict, home_odds: float = None, away_odds: float = None) -> dict:
    game_info = analysis.get("gameInfo", {})
    team_history = analysis.get("gameTeamHistory", {})
    
    home_name = game_info.get("taname", "Home")
    away_name = game_info.get("tbname", "Away")
    handicap_str = game_info.get("handicap", "0.0")
    
    # 1. Parse goals from last 20 matches (or as many as available)
    history_a = team_history.get("A", {}).get("all", {}).get("history", {})
    history_b = team_history.get("B", {}).get("all", {}).get("history", {})
    
    home_id = int(game_info.get("taid") or 0)
    away_id = int(game_info.get("tbid") or 0)
    
    def parse_team_goals(history_dict: dict, team_id: int) -> tuple[list, list]:
        scored = []
        conceded = []
        if not team_id or not history_dict:
            return scored, conceded
        
        aids = history_dict.get("aid", [])
        bids = history_dict.get("bid", [])
        live_a = history_dict.get("liveA", [])
        live_b = history_dict.get("liveB", [])
        
        for i in range(len(live_a)):
            h_id = aids[i] if i < len(aids) else 0
            a_id = bids[i] if i < len(bids) else 0
            try:
                hg = int(live_a[i])
                ag = int(live_b[i])
            except (ValueError, TypeError):
                continue
            
            if h_id == team_id:
                scored.append(hg)
                conceded.append(ag)
            elif a_id == team_id:
                scored.append(ag)
                conceded.append(hg)
            else:
                scored.append(hg)
                conceded.append(ag)
        return scored, conceded

    goals_scored_a, goals_conceded_a = parse_team_goals(history_a, home_id)
    goals_scored_b, goals_conceded_b = parse_team_goals(history_b, away_id)

    
    # 2. Time-decay weighting (gamma = 0.05)
    def calculate_weighted_average(goals_list: list) -> float:
        if not goals_list:
            return 1.2  # default baseline goal expectation
        total_weight = 0.0
        weighted_sum = 0.0
        for i, goals in enumerate(goals_list[:20]):
            weight = math.exp(-0.05 * i)
            weighted_sum += goals * weight
            total_weight += weight
        return weighted_sum / total_weight

    avg_scored_a = calculate_weighted_average(goals_scored_a)
    avg_conceded_a = calculate_weighted_average(goals_conceded_a)
    avg_scored_b = calculate_weighted_average(goals_scored_b)
    avg_conceded_b = calculate_weighted_average(goals_conceded_b)
    
    # League average goals per team baseline is roughly 1.35
    baseline = 1.35
    
    # 3. Compute expected goals (xG) using simple Attack and Defense factors
    attack_a = avg_scored_a / baseline if avg_scored_a > 0 else 1.0
    defense_a = avg_conceded_a / baseline if avg_conceded_a > 0 else 1.0
    attack_b = avg_scored_b / baseline if avg_scored_b > 0 else 1.0
    defense_b = avg_conceded_b / baseline if avg_conceded_b > 0 else 1.0
    
    home_xg = attack_a * defense_b * baseline
    away_xg = attack_b * defense_a * baseline
    
    # 4. Generate exact score grid probabilities and derive W/D/L
    p_home_win = 0.0
    p_draw = 0.0
    p_away_win = 0.0
    
    score_probs = {}
    for h in range(6):
        for a in range(6):
            prob = poisson_probability(home_xg, h) * poisson_probability(away_xg, a)
            score_probs[f"{h}-{a}"] = prob
            if h > a:
                p_home_win += prob
            elif h == a:
                p_draw += prob
            else:
                p_away_win += prob
                
    # Normalize simple outcomes
    total_outcome_prob = p_home_win + p_draw + p_away_win
    if total_outcome_prob > 0:
        p_home_win /= total_outcome_prob
        p_draw /= total_outcome_prob
        p_away_win /= total_outcome_prob
        
    # 5. Market Edge calculation
    # HandiCap parsing logic:
    # On goal7.co, handicap can be a string like "0.5" or "0/0.5" (which is 0.125 or 0.25).
    # If the home team is favored to win, it is written with a minus or as a positive, depending on context.
    # In general, if handicap starts with - (e.g. -0.25), then home gives away goals.
    # If it is positive, home receives goals.
    # Let's clean the handicap string.
    try:
        if "/" in handicap_str:
            parts = handicap_str.split("/")
            handicap_val = (float(parts[0]) + float(parts[1])) / 2.0
        else:
            handicap_val = float(handicap_str)
    except Exception:
        handicap_val = 0.0
        
    # Calculate probability of home team covering handicap
    # Home covers if home_score + handicap > away_score.
    p_home_cover = 0.0
      # We subtract from away_score. Or add to home_score.
      # e.g., if handicap is -0.5, Home needs to win by >= 1 goal. home_score - 0.5 > away_score.
    p_away_cover = 0.0
    for score_line, prob in score_probs.items():
        h, a = map(int, score_line.split("-"))
        diff = h - a + handicap_val
        if diff > 0:
            p_home_cover += prob
        elif diff < 0:
            p_away_cover += prob
            
    total_cover = p_home_cover + p_away_cover
    if total_cover > 0:
        p_home_cover /= total_cover
        p_away_cover /= total_cover
    else:
        p_home_cover = 0.5
        p_away_cover = 0.5
        
    # Calculate implied probabilities from odds prices if available
    p_market_implied_home = 0.50
    p_market_implied_away = 0.50
    if home_odds is not None and away_odds is not None:
        try:
            o_home = float(home_odds) + 1.0
            o_away = float(away_odds) + 1.0
            p_home_raw = 1.0 / o_home
            p_away_raw = 1.0 / o_away
            overround = p_home_raw + p_away_raw
            if overround > 0:
                p_market_implied_home = p_home_raw / overround
                p_market_implied_away = p_away_raw / overround
        except (ValueError, TypeError, ZeroDivisionError):
            p_market_implied_home = 0.50
            p_market_implied_away = 0.50

    edge_home = p_home_cover - p_market_implied_home
    edge_away = p_away_cover - p_market_implied_away
    
    if edge_home >= 0.05:
        recommendation = f"วาง {home_name} (มี Value Edge +{edge_home * 100:.1f}%)"
        has_edge = True
    elif edge_away >= 0.05:
        recommendation = f"วาง {away_name} (มี Value Edge +{edge_away * 100:.1f}%)"
        has_edge = True
    else:
        recommendation = "ไม่มีทีเด็ดราคาคุ้มค่าพิเศษสำหรับคู่นี้ค่ะ"
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
        "is_best_tip": has_edge and max(edge_home, edge_away) >= 0.05
    }
