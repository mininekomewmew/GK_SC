import json

def make_analysis_flex(alt_text: str, pred: dict, matched_match: dict, goal7_tip: str, pol_analysis: dict, news_items: list) -> str:
    """
    Generate a LINE Flex Message for single match analysis.
    Returns a JSON string.
    """
    home = pred["home_team"]
    away = pred["away_team"]
    handicap = matched_match["handicap"]
    time_str = matched_match["time"]
    date_str = pred.get("date", "")
    
    home_elo = pred.get("home_elo")
    away_elo = pred.get("away_elo")
    
    # Build Flex Bubble Contents
    header_contents = [
        {
            "type": "text",
            "text": f"🏆 {home} VS {away}",
            "weight": "bold",
            "size": "md",
            "color": "#FFFFFF",
            "wrap": True
        },
        {
            "type": "text",
            "text": f"⏰ {date_str} ({time_str} น.)" if date_str else f"⏰ เวลา {time_str} น.",
            "size": "xs",
            "color": "#A0A0B0",
            "margin": "xs"
        },
        {
            "type": "text",
            "text": f"📈 แต้มต่อปัจจุบัน: {handicap}",
            "size": "xs",
            "color": "#F9D342",
            "weight": "bold",
            "margin": "xs"
        }
    ]

    body_contents = []
    
    # Elo Row
    if home_elo and away_elo:
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "📊 ค่าพลังความแกร่ง (Elo Rating)",
                    "size": "xs",
                    "color": "#808090",
                    "weight": "bold"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "xs",
                    "contents": [
                        {"type": "text", "text": f"{home}: {int(home_elo)}", "size": "xs", "color": "#E5E5E5"},
                        {"type": "text", "text": f"{away}: {int(away_elo)}", "size": "xs", "color": "#E5E5E5", "align": "end"}
                    ]
                }
            ]
        })
        
    # xG Row
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "md",
        "contents": [
            {
                "type": "text",
                "text": "⚽ คาดการณ์ประตู (xG)",
                "size": "xs",
                "color": "#808090",
                "weight": "bold"
            },
            {
                "type": "box",
                "layout": "horizontal",
                "margin": "xs",
                "contents": [
                    {"type": "text", "text": f"{home}: {pred['home_xg']:.2f}", "size": "xs", "color": "#E5E5E5"},
                    {"type": "text", "text": f"{away}: {pred['away_xg']:.2f}", "size": "xs", "color": "#E5E5E5", "align": "end"}
                ]
            }
        ]
    })
    
    # 1X2 Probabilities Row
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "md",
        "contents": [
            {
                "type": "text",
                "text": "🎲 โอกาสผลแข่งชนะ/เสมอ/แพ้ (1X2)",
                "size": "xs",
                "color": "#808090",
                "weight": "bold"
            },
            {
                "type": "box",
                "layout": "horizontal",
                "margin": "xs",
                "contents": [
                    {"type": "text", "text": f"เหย้าชนะ: {pred['p_home'] * 100:.1f}%", "size": "xs", "color": "#8EE4AF"},
                    {"type": "text", "text": f"เสมอ: {pred['p_draw'] * 100:.1f}%", "size": "xs", "color": "#E5E5E5", "align": "center"},
                    {"type": "text", "text": f"เยือนชนะ: {pred['p_away'] * 100:.1f}%", "size": "xs", "color": "#FF6B6B", "align": "end"}
                ]
            }
        ]
    })

    # Recommendation Banner
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "backgroundColor": "#2A363B",
        "cornerRadius": "sm",
        "paddingAll": "md",
        "contents": [
            {
                "type": "text",
                "text": pred["value_recommendation"],
                "color": "#FFFFFF",
                "size": "xs",
                "weight": "bold",
                "wrap": True,
                "align": "center"
            }
        ]
    })

    # Pundits Tips Box
    pundits_items = []
    if goal7_tip:
        pundits_items.append({
            "type": "text",
            "text": f"• [Goal7] {goal7_tip}",
            "size": "xs",
            "color": "#D3D3D3",
            "wrap": True
        })
    if pol_analysis:
        pundits_items.append({
            "type": "text",
            "text": f"• [Polball] ฟันธง: {pol_analysis['tip']} | ผล: {pol_analysis['score']}",
            "size": "xs",
            "color": "#D3D3D3",
            "wrap": True,
            "margin": "xs"
        })
        
    if pundits_items:
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "💡 ทรรศนะจากกูรูเซียนบอล",
                    "size": "xs",
                    "color": "#808090",
                    "weight": "bold"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xs",
                    "contents": pundits_items
                }
            ]
        })

    # News Box
    if news_items:
        news_elements = []
        for n in news_items[:3]:
            news_elements.append({
                "type": "text",
                "text": f"• [{n['source']}] {n['title']}",
                "size": "xxs",
                "color": "#B0B0B0",
                "wrap": True,
                "margin": "xs"
            })
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "📰 ข่าวสารล่าสุดที่เกี่ยวข้อง",
                    "size": "xs",
                    "color": "#808090",
                    "weight": "bold"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xs",
                    "contents": news_elements
                }
            ]
        })

    flex_payload = {
        "type": "flex",
        "altText": alt_text,
        "contents": {
            "type": "bubble",
            "styles": {
                "header": {"backgroundColor": "#0F2027"},
                "body": {"backgroundColor": "#203A43"}
            },
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": header_contents
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents
            }
        }
    }
    return json.dumps(flex_payload, ensure_ascii=False)

def make_daily_tips_flex(alt_text: str, selected_tips: list, selected_count: int) -> str:
    """
    Generate a LINE Flex Message for the daily tips (ทีเด็ดชุด).
    Returns a JSON string.
    """
    card_items = []
    for i, tip in enumerate(selected_tips, 1):
        rec_team = tip["home_team"] if tip["value_recommendation"].startswith("🔮 พลังเวททำนายชี้เป้า: จัดหนัก " + tip["home_team"]) else tip["away_team"]
        win_prob = tip["p_home_cover"] if rec_team == tip["home_team"] else tip["p_away_cover"]
        date_display = tip.get("date", "")
        time_display = tip.get("time", "")
        datetime_str = f"{date_display} ({time_display} น.)" if date_display else f"{time_display} น."
        
        card_items.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "backgroundColor": "#141E30",
            "cornerRadius": "sm",
            "paddingAll": "md",
            "contents": [
                {
                    "type": "text",
                    "text": f"{i}. {tip['home_team']} VS {tip['away_team']}",
                    "weight": "bold",
                    "size": "sm",
                    "color": "#FFFFFF",
                    "wrap": True
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "xs",
                    "contents": [
                        {"type": "text", "text": f"⏰ {datetime_str}", "size": "xxs", "color": "#A0A0B0"},
                        {"type": "text", "text": f"ราคา: {tip['handicap']}", "size": "xxs", "color": "#F9D342", "align": "end"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "xs",
                    "contents": [
                        {"type": "text", "text": f"🔮 วาง {rec_team}", "size": "xs", "weight": "bold", "color": "#8EE4AF"},
                        {"type": "text", "text": f"โอกาสชนะ: {win_prob * 100:.1f}%", "size": "xs", "color": "#8EE4AF", "align": "end"}
                    ]
                }
            ]
        })
        
    flex_payload = {
        "type": "flex",
        "altText": alt_text,
        "contents": {
            "type": "bubble",
            "styles": {
                "header": {"backgroundColor": "#0F2027"},
                "body": {"backgroundColor": "#203A43"}
            },
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🔮 สเต็ป {selected_count} คัดเน้นๆ ประจำวันนี้" if selected_count >= 3 else f"🔮 คัด {selected_count} ทีเด็ดเด่นน่าจัดวันนี้",
                        "weight": "bold",
                        "size": "md",
                        "color": "#FFFFFF"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": card_items
            }
        }
    }
    return json.dumps(flex_payload, ensure_ascii=False)
