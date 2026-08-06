import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from fastapi import HTTPException

# Mock environment variables before importing app
os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test_token"
os.environ["DB_PATH"] = "test_integration.db"

from app.main import webhook, process_user_command


class TestIntegration(unittest.TestCase):
    def setUp(self):
        from app.database import init_db
        init_db("test_integration.db")
        
    def tearDown(self):
        if os.path.exists("test_integration.db"):
            try:
                os.remove("test_integration.db")
            except Exception:
                pass
                
    def test_webhook_unauthorized(self):
        # Create a mock Request object
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b"{}")
        
        with self.assertRaises(HTTPException) as context:
            asyncio.run(webhook(mock_request, x_line_signature="invalid"))

        
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Invalid signature")

    def test_group_chat_filter(self):
        # General chat inside a group should be ignored (return empty string)
        res_ignored = process_user_command("hello world", is_group=True)
        self.assertEqual(res_ignored, "")
        
        # Unrecognized message inside DM should return fallback message
        res_fallback = process_user_command("hello world", is_group=False)
        self.assertIn("ยังไม่เข้าใจคำสั่งนี้ค่ะ", res_fallback)

    def test_menu_command_logic(self):
        # Menu/Help command should return a structured command list
        for cmd in ["วิธีใช้", "เมนู", "help", "คำสั่ง"]:
            res = process_user_command(cmd, is_group=False)
            self.assertIn("คู่มือคำสั่งบอทนักทำนายฟุตบอลค่ะ", res)
            self.assertIn("ทีเด็ด", res)
            self.assertIn("สถิติ / ผลงาน", res)
            self.assertIn("วิเคราะห์เจาะลึกรายคู่", res)

    @patch('app.main.fetch_today_matches')
    @patch('app.main.fetch_match_analysis')
    def test_ti_ded_command_logic(self, mock_analysis, mock_matches):
        mock_matches.return_value = [
            {"id": "1", "time": "22:00", "home_team": "Team A", "away_team": "Team B", "handicap": "0.25"},
            {"id": "2", "time": "23:00", "home_team": "Team C", "away_team": "Team D", "handicap": "0.5"}
        ]
        mock_analysis.return_value = {
            "gameInfo": {"taname": "Team A", "tbname": "Team B", "handicap": "0.25"},
            "gameTeamHistory": {}
        }
        res = process_user_command("ทีเด็ด", is_group=False)
        self.assertIn("คู่เด่นน่าจัดที่สุดวันนี้ค่ะ", res)

    @patch('app.main.fetch_today_matches')
    @patch('app.main.fetch_match_analysis')
    @patch('app.main.fetch_polball_analysis')
    def test_analysis_command_with_polball(self, mock_polball, mock_analysis, mock_matches):
        mock_matches.return_value = [
            {"id": "1", "time": "22:00", "home_team": "Team A", "away_team": "Team B", "handicap": "0.25"}
        ]
        mock_analysis.return_value = {
            "gameInfo": {"taname": "Team A", "tbname": "Team B", "handicap": "0.25"},
            "gameTeamHistory": {}
        }
        mock_polball.return_value = {
            "tip": "รอง Team B",
            "score": "เสมอ 1-1"
        }
        
        res = process_user_command("วิเคราะห์ Team A", is_group=False)
        self.assertIn("ทรรศนะจากเว็บ Polball", res)
        self.assertIn("รอง Team B", res)

    @patch('app.main.fetch_today_matches')
    @patch('app.main.fetch_match_analysis')
    @patch('app.main.fetch_polball_analysis')
    def test_analysis_command_aliases(self, mock_polball, mock_analysis, mock_matches):
        mock_matches.return_value = [
            {"id": "1", "time": "22:00", "home_team": "Team A", "away_team": "Team B", "handicap": "0.25"}
        ]
        mock_analysis.return_value = {
            "gameInfo": {"taname": "Team A", "tbname": "Team B", "handicap": "0.25"},
            "gameTeamHistory": {}
        }
        mock_polball.return_value = None
        
        res_wi = process_user_command("วิ Team A", is_group=False)
        self.assertIn("วิเคราะห์แมตช์มาให้แล้วค่ะ", res_wi)
        
        res_vs = process_user_command("vs Team A", is_group=False)
        self.assertIn("วิเคราะห์แมตช์มาให้แล้วค่ะ", res_vs)

    @patch('app.main.fetch_finished_scores')
    def test_performance_command(self, mock_finished_scores):
        mock_finished_scores.return_value = {"1": "1-2"}
        from app.main import save_prediction
        
        save_prediction("1", "2026-08-05", "Team A", "Team B", -0.25, "Team B", 0.08, 0.55)
        
        res = process_user_command("ผลงาน", is_group=False)
        self.assertIn("สถิติผลงานการทำนาย", res)
        self.assertIn("ชนะ (WIN): 1 คู่", res)
        self.assertIn("Team A VS Team B", res)

    @patch('app.main.save_group_id')
    @patch('app.main.verify_signature', return_value=True)
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
        
        with patch('app.main.reply_message') as mock_reply:
            asyncio.run(webhook(mock_request, x_line_signature="valid"))
            mock_save.assert_called_with("G12345")

    @patch('app.main.save_group_id')
    @patch('app.main.verify_signature', return_value=True)
    def test_webhook_saves_group_id_on_join(self, mock_verify, mock_save):
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b"{}")
        mock_request.json = AsyncMock(return_value={
            "events": [
                {
                    "type": "join",
                    "source": {"type": "group", "groupId": "G99999"},
                    "replyToken": "reply_999"
                }
            ]
        })
        
        asyncio.run(webhook(mock_request, x_line_signature="valid"))
        mock_save.assert_called_with("G99999")

    @patch('app.main.get_group_ids')
    @patch('app.main.process_user_command')
    @patch('app.main.push_message')
    def test_send_daily_tips(self, mock_push, mock_process, mock_get_groups):
        from app.main import send_daily_tips
        mock_get_groups.return_value = ["G1", "G2"]
        mock_process.return_value = "ทีเด็ดวันนี้..."
        
        asyncio.run(send_daily_tips())
        
        mock_push.assert_any_call("G1", "ทีเด็ดวันนี้...")
        mock_push.assert_any_call("G2", "ทีเด็ดวันนี้...")
        self.assertEqual(mock_push.call_count, 2)

    @patch('app.main.asyncio.sleep', new_callable=AsyncMock)
    @patch('app.main.send_daily_tips', new_callable=AsyncMock)
    def test_scheduler_loop(self, mock_send, mock_sleep):
        from app.main import scheduler_loop
        
        call_count = 0
        async def side_effect(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise asyncio.CancelledError()
        mock_sleep.side_effect = side_effect
        
        try:
            asyncio.run(scheduler_loop())
        except asyncio.CancelledError:
            pass
            
        mock_sleep.assert_called()
        mock_send.assert_called_once()

if __name__ == '__main__':
    unittest.main()


