import os
import asyncio
from datetime import datetime, time, timedelta
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Header, HTTPException

from app.line_bot import verify_signature, reply_message, push_message
from app.scraper import fetch_today_matches, fetch_match_analysis
from app.model import calculate_prediction

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
                # Attach handicap text for display
                pred["handicap"] = match.get("handicap", "0.0")
                # Calculate max cover probability for confidence sorting
                pred["max_prob"] = max(pred["p_home_cover"], pred["p_away_cover"])
                results_list.append(pred)
            except Exception:
                continue
                
        if not results_list:
            return "วันนี้ไม่มีข้อมูลคู่วิเคราะห์น้าาา 🥺💦"
            
        # Sort by cover probability descending
        results_list.sort(key=lambda x: x["max_prob"], reverse=True)
        
        # Select top 4-7 matches
        selected_count = min(7, len(results_list))
        selected_tips = results_list[:selected_count]
        
        res = f"🌟 คัด {selected_count} คู่เด่นโอกาสชนะแต้มต่อสูงสุดวันนี้ค่ะ! 💖\n\n"
        for i, tip in enumerate(selected_tips, 1):
            if tip["p_home_cover"] >= tip["p_away_cover"]:
                rec_team = tip["home_team"]
                win_prob = tip["p_home_cover"]
            else:
                rec_team = tip["away_team"]
                win_prob = tip["p_away_cover"]
                
            res += f"{i}. {tip['home_team']} VS {tip['away_team']}\n"
            res += f"   - ราคาต่อรอง: {tip['handicap']}\n"
            res += f"   - ฟันธง: วาง {rec_team} (โอกาสวิน: {win_prob * 100:.1f}%)\n"
            if tip["is_best_tip"]:
                res += f"   - [ราคาคุ้มค่าพิเศษ! มี Value Edge +{tip['edge_value'] * 100:.1f}%]\n"
            res += "\n"
            
        res += "ขอให้เฮงๆ รวยๆ กันถ้วนหน้านะคะ! 💪🥺💕"
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
            
            res = f"⚽ วิเคราะห์เจาะลึกแมตช์นี้มาให้แล้วค่ะ! 💖\n\n"
            res += f"🏆 {pred['home_team']} VS {pred['away_team']}\n"
            res += f"⏰ เวลาแข่งวันนี้: {matched_match['time']}\n"
            res += f"📈 ราคาต่อรองปัจจุบัน: {matched_match['handicap']}\n\n"
            res += f"📊 คาดการณ์จำนวนประตู (xG):\n"
            res += f"   - เจ้าบ้าน {pred['home_team']}: {pred['home_xg']}\n"
            res += f"   - ทีมเยือน {pred['away_team']}: {pred['away_xg']}\n\n"
            res += f"🎲 ความน่าจะเป็นผลการแข่ง (1X2):\n"
            res += f"   - โอกาสเจ้าบ้านชนะ: {pred['p_home'] * 100:.1f}%\n"
            res += f"   - โอกาสเสมอ: {pred['p_draw'] * 100:.1f}%\n"
            res += f"   - โอกาสทีมเยือนชนะ: {pred['p_away'] * 100:.1f}%\n\n"
            res += f"🎯 วิเคราะห์จากโมเดลคณิตศาสตร์:\n"
            res += f"   - {pred['value_recommendation']}\n\n"
            res += "เอาข้อมูลสถิติประวัติ 20 นัดมาวิเคราะห์ให้อย่างดี ขอให้โชคดีสมหวังน้าาา~ 🥺💕💪"
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
    asyncio.create_task(scheduler_loop())

@app.post("/broadcast")
async def manual_broadcast(token: str = None):
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret or token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    await send_daily_tips()
    return {"status": "success", "groups_sent": get_group_ids()}

