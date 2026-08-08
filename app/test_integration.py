import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from fastapi import HTTPException

os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test_token"
os.environ["DB_PATH"] = "test_integration.db"

from app.main import webhook, bot

class TestIntegration(unittest.TestCase):
    def setUp(self):
        import sqlite3
        conn = sqlite3.connect("test_integration.db")
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS predictions")
        conn.commit()
        conn.close()
        bot.startup()
        
    def tearDown(self):
        if os.path.exists("test_integration.db"):
            try:
                os.remove("test_integration.db")
            except Exception:
                pass
                
    def test_webhook_unauthorized(self):
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b"{}")
        with self.assertRaises(HTTPException) as context:
            asyncio.run(webhook(mock_request, x_line_signature="invalid"))
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Invalid signature")

    def test_group_chat_filter(self):
        res_ignored = bot.process_command("hello world", is_group=True)
        self.assertEqual(res_ignored, "")
        res_fallback = bot.process_command("hello world", is_group=False)
        self.assertIn("ยังไม่เข้าใจคำสั่งนี้ค่ะ", res_fallback)

    def test_menu_command_logic(self):
        for cmd in ["วิธีใช้", "เมนู", "help", "คำสั่ง"]:
            res = bot.process_command(cmd, is_group=False)
            self.assertIn("คู่มือคำสั่งบอทนักทำนายฟุตบอลค่ะ", res)

    @patch.object(bot.scraper, 'fetch_today_matches')
    @patch.object(bot.scraper, 'fetch_match_analysis')
    def test_ti_ded_command_logic(self, mock_analysis, mock_matches):
        mock_matches.return_value = [
            {"id": "1", "time": "22:00", "home_team": "Team A", "away_team": "Team B", "handicap": "0.25"},
        ]
        mock_analysis.return_value = {
            "gameInfo": {"taname": "Team A", "tbname": "Team B", "handicap": "0.25"},
            "gameTeamHistory": {}
        }
        res = bot.process_command("ทีเด็ด", is_group=False)
        self.assertIn("คู่เด่นน่าจัดที่สุดวันนี้ค่ะ", res)

    @patch.object(bot.scraper, 'fetch_today_matches')
    @patch.object(bot.scraper, 'fetch_match_analysis')
    @patch.object(bot.scraper, 'fetch_polball_analysis')
    def test_analysis_command_with_polball(self, mock_polball, mock_analysis, mock_matches):
        mock_matches.return_value = [
            {"id": "1", "time": "22:00", "home_team": "Team A", "away_team": "Team B", "handicap": "0.25"}
        ]
        mock_analysis.return_value = {
            "gameInfo": {"taname": "Team A", "tbname": "Team B", "handicap": "0.25"},
            "gameTeamHistory": {}
        }
        mock_polball.return_value = {"tip": "รอง Team B", "score": "เสมอ 1-1"}
        res = bot.process_command("วิเคราะห์ Team A", is_group=False)
        self.assertIn("ทรรศนะจากเว็บ Polball", res)
        self.assertIn("รอง Team B", res)

    @patch.object(bot.scraper, 'fetch_finished_scores')
    def test_performance_command(self, mock_finished_scores):
        mock_finished_scores.return_value = {"1": "1-2"}
        bot.db.save_prediction("1", "2026-08-05", "Team A", "Team B", -0.25, "Team B", 0.08, 0.55, is_best_tip=True)
        res = bot.process_command("ผลงาน", is_group=False)
        self.assertIn("สถิติผลงานการทำนาย", res)
        self.assertIn("วิน", res)

    @patch.object(bot.db, 'save_group_id')
    @patch.object(bot.line, 'verify_signature', return_value=True)
    def test_webhook_saves_group_id_on_message(self, mock_verify, mock_save):
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b"{}")
        mock_request.json = AsyncMock(return_value={
            "events": [
                {
                    "type": "message",
                    "message": {"type": "text", "text": "hello"},
                    "source": {"type": "group", "groupId": "G12345"},
                    "replyToken": "reply_123"
                }
            ]
        })
        with patch.object(bot.line, 'reply_message'):
            asyncio.run(webhook(mock_request, x_line_signature="valid"))
            mock_save.assert_called_with("G12345")

    @patch.object(bot.db, 'get_group_ids')
    @patch.object(bot, 'process_command')
    @patch.object(bot.line, 'push_message')
    def test_send_daily_tips(self, mock_push, mock_process, mock_get_groups):
        mock_get_groups.return_value = ["G1", "G2"]
        mock_process.return_value = "ทีเด็ดวันนี้..."
        asyncio.run(bot.send_daily_tips())
        mock_push.assert_any_call("G1", "ทีเด็ดวันนี้...")
        mock_push.assert_any_call("G2", "ทีเด็ดวันนี้...")

if __name__ == '__main__':
    unittest.main()
