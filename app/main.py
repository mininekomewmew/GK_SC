import re
import asyncio
import json
import os
from datetime import datetime, time, timedelta
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Header, HTTPException

from app.database import DatabaseManager
from app.line_bot import LineClient
from app.scraper import CacheManager, FootballScraper
from app.club_elo import EloService
from app.rss_scraper import NewsScraper
from app.model import PredictionEngine

load_dotenv()

class FootballBotController:
    def __init__(self):
        self.db = DatabaseManager()
        self.line = LineClient()
        self.cache = CacheManager()
        self.scraper = FootballScraper(self.cache)
        self.elo = EloService(self.cache)
        self.news = NewsScraper(self.cache, self.elo)
        self.engine = PredictionEngine(self.elo)
        
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data")
        with open(os.path.join(data_dir, "team_aliases.json"), "r", encoding="utf-8") as f:
            self.aliases = json.load(f)

    def _get_football_date(self) -> datetime:
        """Returns the current date adjusted for 12:00 PM cutoff"""
        now = datetime.now()
        if now.hour < 12:
            return now - timedelta(days=1)
        return now

    def startup(self):
        self.db.init_db()

    def process_webhook(self, signature: str, body: bytes, data: dict):
        for event in data.get("events", []):
            source = event.get("source", {})
            source_type = source.get("type", "user")
            
            group_id = source.get("groupId") or source.get("roomId")
            if group_id:
                self.db.save_group_id(group_id)
                    
            if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
                reply_token = event.get("replyToken")
                text = event["message"]["text"].strip()
                is_group = source_type in ("group", "room")
                
                if not is_group and source.get("userId"):
                    self.line.show_loading_animation(source["userId"], loading_seconds=30)
                
                response_text = self.process_command(text, is_group)
                if reply_token and response_text:
                    self.line.reply_message(reply_token, response_text)

    def _is_team_match(self, query: str, team_name: str) -> bool:
        def clean(s: str) -> str:
            # Remove [League-Rank] tags first, then special chars
            s = re.sub(r"\[.*?\]", "", s)
            return re.sub(r"[\s\.\-\(\)]", "", s.lower().strip())

        q_clean = clean(query)
        t_clean = clean(team_name)

        if q_clean == t_clean or t_clean.startswith(q_clean):
            return True

        for key, targets in self.aliases.items():
            if clean(key) == q_clean:
                return any(clean(target) == t_clean or t_clean.startswith(clean(target)) for target in targets)
                
        # Fallback for very specific queries to avoid short false positives (like 'แมน' in 'ทูคูแมน')
        if len(q_clean) >= 4 and q_clean in t_clean:
            return True
            
        return False

    def process_command(self, command: str, is_group: bool = False) -> str:
        for prefix in ["วิเคราะห์ ", "วิ ", "เช็ค ", "เชค ", "v ", "vs "]:
            if command.lower().startswith(prefix):
                command = "วิเคราะห์ " + command[len(prefix):].strip()
                break

        if command in ["วิธีใช้", "เมนู", "ช่วยด้วย", "help", "คำสั่ง"]:
            return (
                "🔮 คู่มือคำสั่งบอทนักทำนายฟุตบอลค่ะ! 💖\n\n"
                "1. 🔮 [ทีเด็ด] - วิเคราะห์คู่เด่นวันนี้\n"
                "2. 📊 [สถิติ / ผลงาน] - ดู Win Rate\n"
                "3. ⚽ [วิ [ชื่อทีม]] หรือ [vs [ชื่อทีม]] - เจาะลึกรายคู่\n"
                "4. ℹ️ [วิธีใช้] - ดูเมนูนี้\n\n"
                "พร้อมลุยพาทุกคนคว้าแต้มต่อแล้วค่ะ! 🥺💕💪"
            )

        if command in ["ทีเด็ด", "ทีเด็ดวันนี้", "สเต็ป4"]:
            matches = self.scraper.fetch_today_matches()
            if not matches:
                return "วันนี้ไม่มีข้อมูลการแข่ง หรือดึงข้อมูลขัดข้องน้าาา 🥺💦"
            
            results_list = []
            for match in matches:
                try:
                    analysis = self.scraper.fetch_match_analysis(match["id"])
                    pred = self.engine.calculate_prediction(analysis, match.get("home_odds"), match.get("away_odds"), match.get("handicap"))
                    pred.update({"id": match["id"], "handicap": match.get("handicap", "0.0"), "time": match["time"]})
                    pred["max_prob"] = max(pred["p_home_cover"], pred["p_away_cover"])
                    results_list.append(pred)
                except Exception:
                    continue
                    
            best_tips = []
            football_date = self._get_football_date().date()
            for tip in results_list:
                if not tip["is_best_tip"]: continue
                if tip.get("date"):
                    try:
                        if datetime.strptime(tip["date"].split()[0], "%d/%m/%Y").date() < football_date:
                            continue
                    except Exception:
                        pass
                best_tips.append(tip)
            
            if not best_tips:
                return "วันนี้วิเคราะห์แล้วยังไม่มีคู่ที่กระแสค่าน้ำคุ้มค่าความเสี่ยงเลยนะคะ 🥺💦 ลองพิมพ์ 'วิเคราะห์ [ชื่อทีม]' เพื่อส่องกระแสรายคู่ได้เลยค่ะ 💖"
                
            for tip in best_tips:
                tip["is_major"] = self.scraper.is_major_match(tip["home_team"], tip["away_team"])
                
            best_tips.sort(key=lambda x: (x.get("is_major", False), x["max_prob"]), reverse=True)
            selected_tips = best_tips[:20]
            selected_count = len(selected_tips)
            
            for tip in results_list:
                rec_t = tip["home_team"] if tip["p_home_cover"] >= tip["p_away_cover"] else tip["away_team"]
                w_prob = max(tip["p_home_cover"], tip["p_away_cover"])
                is_best = any(t["id"] == tip["id"] for t in selected_tips)
                self.db.save_prediction(
                    tip["id"], self._get_football_date().strftime("%Y-%m-%d"), tip["home_team"], tip["away_team"],
                    self.engine.parse_handicap(tip["handicap"]), rec_t, tip["edge_value"], w_prob, is_best
                )

            if command == "สเต็ป4":
                usable_tips = selected_tips[:len(selected_tips) - (len(selected_tips) % 4)]
                if len(usable_tips) < 4:
                    return "วันนี้มีคู่ที่มั่นใจผ่านเกณฑ์ไม่ถึง 4 คู่ จัดชุดสเต็ป 4 ไม่ได้น้าาา 🥺💦"
                
                res = "🔮 มนตราจัดชุดสเต็ป 4 คู่เด่นเน้นๆ ให้แล้วค่ะ! ⚡\n\n"
                for s in range(0, len(usable_tips), 4):
                    res += f"🔥 ชุดที่ {(s//4)+1}:\n"
                    for i, tip in enumerate(usable_tips[s:s+4], 1):
                        rec_t = tip["home_team"] if tip["p_home_cover"] >= tip["p_away_cover"] else tip["away_team"]
                        dt_str = f"({tip.get('date', '')[:5]} {tip['time']})" if tip.get('date') else f"({tip['time']})"
                        res += f"   {i}. {rec_t} {dt_str} | ราคา: {tip['handicap']}\n"
                    res += "\n"
                res += "ขอให้เข้าเต็มๆ แตกทุกชุดนะคะ! 💪🥺💕"
                return res[:5000]

            res = f"🔮 มนตราวิเคราะห์ชี้เป้า: {'ทีเด็ดชุด สเต็ป' if selected_count >= 3 else 'คัด'} {selected_count} คู่เด่นน่าจัดที่สุดวันนี้ค่ะ! ⚡\n\n"
            
            for i, tip in enumerate(selected_tips, 1):
                rec_t = tip["home_team"] if tip["p_home_cover"] >= tip["p_away_cover"] else tip["away_team"]
                w_prob = max(tip["p_home_cover"], tip["p_away_cover"])
                dt_str = f" | ⏰ {tip.get('date', '')[:5]} ({tip['time']})" if tip.get('date') else f" | ⏰ {tip['time']}"
                res += f"{i}. {tip['home_team']} VS {tip['away_team']}{dt_str}\n"
                res += f"   - 🔮 วาง {rec_t}! (โอกาสวินแต้มต่อ: {w_prob * 100:.1f}%) | ราคา: {tip['handicap']}\n"
                if tip.get("warnings"):
                    for w in tip["warnings"]:
                        res += f"   - {w}\n"
                res += "\n"
                
            res += "ขอให้เฮงๆ รวยๆ กันถ้วนหน้านะคะ! 💪🥺💕"
            return res[:5000]

        if command in ["ผลงาน", "สถิติ"]:
            try:
                self.db.update_predictions(self.scraper.fetch_finished_scores())
            except Exception:
                pass
                
            try:
                stats = self.db.get_stats()
            except Exception:
                return "ไม่สามารถโหลดข้อมูลประวัติการทายผลได้ค่ะ 🥺💦"
                
            if not stats or stats.get("all", {}).get("total", 0) == 0:
                return "ยังไม่มีข้อมูลประวัติการทายผลเลยนะคะ 🥺💦"
                
            res = "📊 สถิติผลงานการทำนายค่ะ! 💖\n\n"
            s_best = stats.get("best", {})
            res += f"⭐ ผลงาน 'ทีเด็ด' (คัดเน้นๆ):\n"
            res += f"   - ทาย: {s_best.get('total', 0)} คู่ | วิน: {s_best.get('wins', 0)} | เสีย: {s_best.get('losses', 0)} | เจ๊า: {s_best.get('draws', 0)}\n"
            res += f"   - 🎯 ความแม่นยำ (Win Rate): {s_best.get('win_rate', 0.0):.1f}%\n\n"
            
            s_all = stats.get("all", {})
            res += f"📈 ผลงานรวมทุกคู่ (รวมคู่ธรรมดา):\n"
            res += f"   - ทาย: {s_all.get('total', 0)} คู่ | วิน: {s_all.get('wins', 0)} | เสีย: {s_all.get('losses', 0)} | เจ๊า: {s_all.get('draws', 0)}\n"
            res += f"   - 🎯 ความแม่นยำ (Win Rate): {s_all.get('win_rate', 0.0):.1f}%\n\n"
            
            def result_emoji(result: str) -> str:
                return "🟢 วิน" if result == "WIN" else "🔴 เสีย" if result == "LOSE" else "🟡 เจ๊า"
                
            try:
                recent_best = self.db.get_recent_predictions(3, is_best_tip=True)
                recent_other = self.db.get_recent_predictions(3, is_best_tip=False)
            except Exception:
                recent_best, recent_other = [], []
                
            if recent_best:
                res += "⚽ ผลงานการทาย 'ทีเด็ด' ล่าสุด:\n"
                for i, item in enumerate(recent_best, 1):
                    res += f"{i}. {item['home_team']} VS {item['away_team']}\n"
                    res += f"   - วาง {item['rec_team']} ({item['handicap_value']}) -> {result_emoji(item['result'])} ({item['actual_score']})\n"

            if recent_other:
                res += "\n⚽ ตัวอย่างคู่ที่ไม่ได้ออกทีเด็ด:\n"
                for i, item in enumerate(recent_other, 1):
                    res += f"{i}. {item['home_team']} VS {item['away_team']}\n"
                    res += f"   - วาง {item['rec_team']} ({item['handicap_value']}) -> {result_emoji(item['result'])} ({item['actual_score']})\n"
                    
            res += "\nจะตั้งใจวิเคราะห์ให้แม่นยำยิ่งขึ้นเสมอนะคะ! 🥺💕💪"
            return res
            
        if command.startswith("วิเคราะห์ "):
            team_query = command[9:].strip()
            if not team_query: return "กรุณาระบุชื่อทีมที่ต้องการค้นหาและวิเคราะห์ด้วยนะคะ 🥺"
            
            matched_match = None
            for m in self.scraper.fetch_today_matches():
                if self._is_team_match(team_query, m["home_team"]) or self._is_team_match(team_query, m["away_team"]):
                    matched_match = m
                    break
                    
            if not matched_match: return f"หาคู่แข่งของทีม '{team_query}' ในตารางแข่งขันวันนี้ไม่เจอเลยค่ะ 🥺💦 ลองพิมพ์ชื่อทีมให้ตรงคีย์น้าาา"
                
            try:
                analysis = self.scraper.fetch_match_analysis(matched_match["id"])
                pred = self.engine.calculate_prediction(analysis, matched_match.get("home_odds"), matched_match.get("away_odds"), matched_match.get("handicap"))
                
                rec_t = pred["home_team"] if pred["p_home_cover"] >= pred["p_away_cover"] else pred["away_team"]
                w_prob = max(pred["p_home_cover"], pred["p_away_cover"])
                self.db.save_prediction(
                    matched_match["id"], self._get_football_date().strftime("%Y-%m-%d"), pred["home_team"], pred["away_team"],
                    self.engine.parse_handicap(matched_match["handicap"]), rec_t, pred["edge_value"], w_prob
                )
                
                res = f"⚽ วิเคราะห์แมตช์มาให้แล้วค่ะ! 💖\n\n🏆 {pred['home_team']} VS {pred['away_team']}\n"
                res += f"⏰ วันเวลาแข่ง: {pred.get('date', '')} เวลา {matched_match['time']} น.\n" if pred.get('date') else f"⏰ เวลาแข่ง: {matched_match['time']} น.\n"
                res += f"📈 ราคาต่อรองปัจจุบัน: {matched_match['handicap']}\n\n"
                
                if pred.get("home_elo") and pred.get("away_elo"):
                    res += f"📊 ค่าพลังความแกร่ง (Elo Rating):\n   - เจ้าบ้าน {pred['home_team']}: {int(pred['home_elo'])}\n   - ทีมเยือน {pred['away_team']}: {int(pred['away_elo'])}\n\n"
                
                res += f"📊 คาดการณ์จำนวนประตู (xG):\n   - เจ้าบ้าน {pred['home_team']}: {pred['home_xg']:.2f}\n   - ทีมเยือน {pred['away_team']}: {pred['away_xg']:.2f}\n\n"
                res += f"🎲 ความน่าจะเป็นผลการแข่ง (1X2):\n   - โอกาสเจ้าบ้านชนะ: {pred['p_home'] * 100:.1f}%\n   - โอกาสเสมอ: {pred['p_draw'] * 100:.1f}%\n   - โอกาสทีมเยือนชนะ: {pred['p_away'] * 100:.1f}%\n\n"
                res += f"🎯 ผลการวิเคราะห์จากโมเดล:\n   - {pred['value_recommendation']}\n\n"
                
                if pred.get("warnings"):
                    res += "⚠️ ข้อควรระวัง (จากสถิติและค่าน้ำ):\n"
                    for w in pred["warnings"]:
                        res += f"   - {w}\n"
                    res += "\n"
                
                if pred.get("past_results"):
                    res += "🔄 ผลบอลย้อนหลัง (H2H):\n" + "\n".join(f"   - {pr}" for pr in pred["past_results"]) + "\n\n"
                
                goal7_tip = matched_match.get("pundit_tip")
                if goal7_tip:
                    res += f"💡 ทรรศนะจากเว็บ Goal7:\n   - {goal7_tip}\n\n"
                
                pol_analysis = self.scraper.fetch_polball_analysis(pred['home_team'], pred['away_team'])
                if pol_analysis:
                    res += f"💡 ทรรศนะจากเว็บ Polball:\n   - ฟันธง: {pol_analysis['tip']}\n   - ผลที่คาด: {pol_analysis['score']}\n\n"
                    
                news_items = self.news.get_news_for_match(pred['home_team'], pred['away_team'])
                if news_items:
                    res += "📰 ข่าวสารล่าสุดที่เกี่ยวข้อง:\n" + "\n".join(f"   - [{n['source']}] {n['title']}" for n in news_items[:3]) + "\n\n"

                res += "ขอให้โชคดีสมหวังน้าาา~ 🥺💕💪"
                
                scores = self.scraper.fetch_finished_scores()
                if matched_match["id"] in scores:
                    res = f"🏁 สกอร์จริง: {scores[matched_match['id']]}\n\n" + res
                    
                return res[:5000]
            except Exception as e:
                return f"ขออภัยน้าาา ดึงข้อมูลวิเคราะห์คู่นี้ขัดข้อง: {str(e)} 🥺💦"
                
        if is_group: return ""
        return "ยังไม่เข้าใจคำสั่งนี้ค่ะ 🥺 ลองพิมพ์ 'ทีเด็ด' หรือ 'วิ [ชื่อทีม]' ดูน้าาา พร้อมลุยค่ะ 💖"

    async def send_daily_tips(self):
        tips_text = self.process_command("ทีเด็ด")
        if not tips_text or "วันนี้ไม่มีข้อมูล" in tips_text: return
        for gid in self.db.get_group_ids():
            self.line.push_message(gid, tips_text)

    async def scheduler_loop(self):
        while True:
            try:
                now = datetime.now()
                target = datetime.combine(now.date(), time(8, 0))
                if now >= target: target += timedelta(days=1)
                await asyncio.sleep((target - now).total_seconds())
                await self.send_daily_tips()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(60)


app = FastAPI(title="Football Prediction Bot")
bot = FootballBotController()

@app.on_event("startup")
async def startup_event():
    bot.startup()
    asyncio.create_task(bot.scheduler_loop())

@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(None)):
    if not x_line_signature: raise HTTPException(status_code=400, detail="Missing signature header")
    body = await request.body()
    if not bot.line.verify_signature(body, x_line_signature): raise HTTPException(status_code=400, detail="Invalid signature")
    data = await request.json()
    bot.process_webhook(x_line_signature, body, data)
    return "OK"

@app.post("/broadcast")
async def manual_broadcast(token: str = None):
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret or token != secret: raise HTTPException(status_code=403, detail="Forbidden")
    await bot.send_daily_tips()
    return {"status": "success", "groups_sent": bot.db.get_group_ids()}
