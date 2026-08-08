import unittest
import os
import sqlite3
from app.database import DatabaseManager

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_predictions.db"
        self.db = DatabaseManager(self.db_path)
        self._cleanup()
        
    def tearDown(self):
        self._cleanup()
        
    def _cleanup(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_init_db_creates_table(self):
        self.db.init_db()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'")
        table = cursor.fetchone()
        self.assertIsNotNone(table)
        conn.close()

    def test_save_and_update_prediction(self):
        self.db.init_db()
        self.db.save_prediction(
            match_id="m_100", date_str="2026-08-05", home_team="Chelsea", away_team="Arsenal",
            handicap_val=-0.5, rec_team="Chelsea", edge_val=0.08, win_prob=0.55, is_best_tip=False
        )
        
        stats = self.db.get_stats()
        self.assertEqual(stats["all"]["total"], 0)
        
        self.db.update_predictions({"m_100": "1-0"})
        stats = self.db.get_stats()
        self.assertEqual(stats["all"]["total"], 1)
        self.assertEqual(stats["all"]["wins"], 1)
        
        recent = self.db.get_recent_predictions(5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["match_id"], "m_100")
        self.assertEqual(recent[0]["result"], "WIN")
        self.assertEqual(recent[0]["actual_score"], "1-0")

    def test_draw_resolution(self):
        self.db.init_db()
        self.db.save_prediction("m_200", "2026-08-05", "Real Madrid", "Barcelona", 0.0, "Real Madrid", 0.05, 0.45)
        self.db.update_predictions({"m_200": "1-1"})
        stats = self.db.get_stats()
        self.assertEqual(stats["all"]["draws"], 1)

    def test_away_win_resolution(self):
        self.db.init_db()
        self.db.save_prediction("m_300", "2026-08-05", "Real Madrid", "Barcelona", 0.25, "Barcelona", 0.06, 0.50)
        self.db.update_predictions({"m_300": "0-0"})
        recent = self.db.get_recent_predictions(5)
        self.assertEqual(recent[0]["result"], "LOSE")

if __name__ == '__main__':
    unittest.main()
