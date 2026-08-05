import os
import asyncio
import json
from datetime import datetime, time, timedelta
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Header, HTTPException

from app.line_bot import verify_signature, reply_message, push_message
from app.scraper import fetch_today_matches, fetch_match_analysis, fetch_polball_analysis, fetch_finished_scores
from app.model import calculate_prediction, parse_handicap
from app.database import (
    init_db,
    save_prediction_db as save_prediction,
    update_predictions_db as update_predictions_history,
    get_stats_db,
    get_recent_predictions_db
)

app = FastAPI(title="Football Prediction Bot")

def save_group_id(group_id: str):
    if not group_id:
        return
    # ponytail: simple flat file to save group IDs
    file_path = "groups.txt"
    existing = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing = {line.strip() for line in f if line.strip()}
        except Exception:
            pass
    if group_id not in existing:
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(group_id + "\n")
        except Exception:
            pass

def get_group_ids() -> list:
    file_path = "groups.txt"
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(None)):
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
    
    body = await request.body()
    if not verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    data = await request.json()
    events = data.get("events", [])
    for event in events:
        source = event.get("source", {})
        source_type = source.get("type", "user")
        
        if source_type == "group":
            group_id = source.get("groupId")
            if group_id:
                save_group_id(group_id)
        elif source_type == "room":
            room_id = source.get("roomId")
            if room_id:
                save_group_id(room_id)
                
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            reply_token = event.get("replyToken")
            text = event["message"]["text"].strip()
            
            is_group = source_type in ("group", "room")
            response_text = process_user_command(text, is_group=is_group)
            if reply_token and response_text:
                reply_message(reply_token, response_text)
                
    return "OK"

# Predictions are now handled using SQLite DB via app/database.py

def process_user_command(command: str, is_group: bool = False) -> str:

    if command == "ทีเด็ด" or command == "ทีเด็ดวันนี้":
        matches = fetch_today_matches()
        if not matches:
            return "วันนี้ไม่มีข้อมูลการแข่ง หรือดึงข้อมูลขัดข้องน้าาา 🥺💦"
        
        # Run analysis on all matches
        results_list = []
        for match in matches:
            try:
                analysis = fetch_match_analysis(match["id"])
                pred = calculate_prediction(
                    analysis,
                    home_odds=match.get("home_odds"),
                    away_odds=match.get("away_odds")
                )
                pred["id"] = match["id"]
                # Attach handicap text for display
                pred["handicap"] = match.get("handicap", "0.0")
                # Calculate max cover probability for confidence sorting
                pred["max_prob"] = max(pred["p_home_cover"], pred["p_away_cover"])
                results_list.append(pred)
            except Exception:
                continue
                
        # Filter to only the matches that are worth betting on (is_best_tip = True)
        best_tips = [tip for tip in results_list if tip["is_best_tip"]]
        
        if not best_tips:
            return "วันนี้วิเคราะห์แล้วยังไม่มีคู่ที่กระแสค่าน้ำคุ้มค่าความเสี่ยงเลยนะคะ 🥺💦 ลองพิมพ์ 'วิเคราะห์ [ชื่อทีม]' เพื่อส่องกระแสรายคู่ได้เลยค่ะ 💖"
            
        # Sort by cover probability descending
        best_tips.sort(key=lambda x: x["max_prob"], reverse=True)
        
        # Cap at 7 matches
        selected_tips = best_tips[:7]
        selected_count = len(selected_tips)
        
        if selected_count >= 3:
            res = f"🔮 มนตราวิเคราะห์ชี้เป้า: ทีเด็ดชุด \"สเต็ป {selected_count}\" คัดเน้นๆ วันนี้ค่ะ! ⚡\n\n"
        else:
            res = f"🔮 มนตราวิเคราะห์ชี้เป้า: คัด {selected_count} คู่เด่นน่าจัดที่สุดวันนี้ค่ะ! ⚡\n\n"
            
        for i, tip in enumerate(selected_tips, 1):
            if tip["p_home_cover"] >= tip["p_away_cover"]:
                rec_team = tip["home_team"]
                win_prob = tip["p_home_cover"]
            else:
                rec_team = tip["away_team"]
                win_prob = tip["p_away_cover"]
                
            # Handicap parsing
            handicap_val = parse_handicap(tip["handicap"])
                
            # Save to prediction history
            save_prediction(
                match_id=tip["id"],
                date_str=datetime.now().strftime("%Y-%m-%d"),
                home_team=tip["home_team"],
                away_team=tip["away_team"],
                handicap_val=handicap_val,
                rec_team=rec_team,
                edge_val=tip["edge_value"],
                win_prob=win_prob
            )
            
            res += f"{i}. {tip['home_team']} VS {tip['away_team']}\n"
            res += f"   - ราคาต่อรอง: {tip['handicap']}\n"
            res += f"   - ฟันธง: 🔮 พลังเวทชี้เป้า วาง {rec_team}! (โอกาสวินแต้มต่อ: {win_prob * 100:.1f}%) ⚡\n"
            res += "\n"
            
        res += "ขอให้เฮงๆ รวยๆ กันถ้วนหน้านะคะ! 💪🥺💕"
        return res

    elif command == "ผลงาน" or command == "สถิติ":
        # 1. Update history with latest finished scores
        try:
            scores = fetch_finished_scores()
            update_predictions_history(scores)
        except Exception:
            pass
            
        # 2. Get stats from DB
        try:
            stats = get_stats_db()
        except Exception:
            return "ไม่สามารถโหลดข้อมูลประวัติการทายผลได้ค่ะ 🥺💦"
            
        if not stats:
            return "ยังไม่มีข้อมูลประวัติการทายผลเลยนะคะ 🥺💦"
            
        res = f"📊 สถิติผลงานการทายผลของอัญค่ะ! 💖\n\n"
        res += f"📈 ผลงานภาพรวม:\n"
        res += f"   - ทายทั้งหมด: {stats['total']} คู่\n"
        res += f"   - ชนะ (WIN): {stats['wins']} คู่ (เขียวขจี) 🟢\n"
        res += f"   - แพ้ (LOSE): {stats['losses']} คู่ 🔴\n"
        res += f"   - เจ๊า/เสมอหู (DRAW): {stats['draws']} คู่ 🟡\n"
        res += f"   - อัตราความแม่นยำ (Win Rate): {stats['win_rate']:.1f}%\n\n"
        
        # 3. Get last 5 matches
        try:
            recent = get_recent_predictions_db(5)
        except Exception:
            recent = []
            
        if recent:
            res += f"⚽ ผลงานการทาย 5 นัดล่าสุด:\n"
            for i, item in enumerate(recent, 1):
                emoji = "🟢 WIN" if item["result"] == "WIN" else "🔴 LOSE" if item["result"] == "LOSE" else "🟡 DRAW"
                res += f"{i}. {item['home_team']} VS {item['away_team']}\n"
                res += f"   - ทาย: วาง {item['rec_team']} (ราคาต่อรอง: {item['handicap_value']})\n"
                res += f"   - ผลลัพธ์: {emoji} (สกอร์: {item['actual_score']})\n\n"
                
        res += "อัญจะตั้งใจวิเคราะห์ให้แม่นยำยิ่งขึ้นเสมอนะคะ! 🥺💕💪"
        return res
        
    elif command.startswith("วิเคราะห์ "):
        team_query = command[9:].strip()
        if not team_query:
            return "กรุณาระบุชื่อทีมที่ต้องการค้นหาและวิเคราะห์ด้วยนะคะ 🥺"
        matches = fetch_today_matches()

        matched_match = None
        for m in matches:
            if team_query.lower() in m["home_team"].lower() or team_query.lower() in m["away_team"].lower():
                matched_match = m
                break
                
        if not matched_match:
            return f"หาคู่แข่งของทีม '{team_query}' ในตารางแข่งขันวันนี้ไม่เจอเลยค่ะ 🥺💦 ลองพิมพ์ชื่อทีมให้ตรงคีย์น้าาา"
            
        try:
            analysis = fetch_match_analysis(matched_match["id"])
            pred = calculate_prediction(
                analysis,
                home_odds=matched_match.get("home_odds"),
                away_odds=matched_match.get("away_odds")
            )
            
            # Save single match analysis prediction
            if pred["p_home_cover"] >= pred["p_away_cover"]:
                rec_team = pred["home_team"]
                win_prob = pred["p_home_cover"]
            else:
                rec_team = pred["away_team"]
                win_prob = pred["p_away_cover"]
                
            # Handicap parsing
            handicap_val = parse_handicap(matched_match["handicap"])
                
            save_prediction(
                match_id=matched_match["id"],
                date_str=datetime.now().strftime("%Y-%m-%d"),
                home_team=pred["home_team"],
                away_team=pred["away_team"],
                handicap_val=handicap_val,
                rec_team=rec_team,
                edge_val=pred["edge_value"],
                win_prob=win_prob
            )
            
            res = f"⚽ วิเคราะห์แมตช์วันนี้มาให้แล้วค่ะ! 💖\n\n"
            res += f"🏆 {pred['home_team']} VS {pred['away_team']}\n"
            res += f"⏰ เวลาแข่งวันนี้: {matched_match['time']}\n"
            res += f"📈 ราคาต่อรองปัจจุบัน: {matched_match['handicap']}\n\n"
            
            res += f"🎯 ผลการวิเคราะห์จากโมเดล:\n"
            res += f"   - {pred['value_recommendation']}\n\n"
            
            pol_analysis = fetch_polball_analysis(pred['home_team'], pred['away_team'])
            if pol_analysis:
                res += f"💡 ทรรศนะจากเว็บ Polball:\n"
                res += f"   - ฟันธง: {pol_analysis['tip']}\n"
                res += f"   - ผลที่คาด: {pol_analysis['score']}\n\n"
                
            res += "ขอให้โชคดีสมหวังน้าาา~ 🥺💕💪"
            return res
        except Exception as e:
            return f"ขออภัยน้าาา ดึงข้อมูลวิเคราะห์คู่นี้ขัดข้อง: {str(e)} 🥺💦"
            
    if is_group:
        return ""
    return "ยังไม่เข้าใจคำสั่งนี้ค่ะ 🥺 ลองพิมพ์ 'ทีเด็ด' หรือ 'วิเคราะห์ [ชื่อทีม]' ดูน้าาา พร้อมลุยค่ะ 💖"

async def send_daily_tips():
    tips_text = process_user_command("ทีเด็ด")
    if not tips_text or "วันนี้ไม่มีข้อมูล" in tips_text:
        return
    
    group_ids = get_group_ids()
    for gid in group_ids:
        push_message(gid, tips_text)

async def scheduler_loop():
    while True:
        try:
            now = datetime.now()
            target = datetime.combine(now.date(), time(8, 0))
            if now >= target:
                target += timedelta(days=1)
            sleep_seconds = (target - now).total_seconds()
            await asyncio.sleep(sleep_seconds)
            await send_daily_tips()
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(scheduler_loop())

@app.post("/broadcast")
async def manual_broadcast(token: str = None):
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret or token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    await send_daily_tips()
    return {"status": "success", "groups_sent": get_group_ids()}

