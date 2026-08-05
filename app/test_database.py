import unittest
import os
import json
import sqlite3
from app.database import (
    init_db,
    save_prediction_db,
    update_predictions_db,
    get_stats_db,
    get_recent_predictions_db
)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_predictions.db"
        self.json_path = "test_predictions_history.json"
        
        # Cleanup any existing test files
        self._cleanup()
        
    def tearDown(self):
        self._cleanup()
        
    def _cleanup(self):
        for path in [self.db_path, self.json_path, self.json_path + ".bak"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def test_init_db_creates_table(self):
        init_db(self.db_path, self.json_path)
        
        # Verify table exists
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'")
        table = cursor.fetchone()
        self.assertIsNotNone(table)
        conn.close()

    def test_json_migration(self):
        # Create a mock legacy JSON file
        legacy_data = {
            "match_1": {
                "id": "match_1",
                "date": "2026-08-04",
                "home_team": "Team A",
                "away_team": "Team B",
                "handicap_value": -0.25,
                "rec_team": "Team A",
                "edge_val": 0.07,
                "win_prob": 0.54,
                "actual_score": "2-1",
                "result": "WIN"
            }
        }
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)
            
        # Run init_db which triggers migration
        init_db(self.db_path, self.json_path)
        
        # Check that data was migrated into SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE match_id = 'match_1'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[2], "Team A") # home_team
        self.assertEqual(row[3], "Team B") # away_team
        self.assertEqual(row[4], -0.25) # handicap_value
        self.assertEqual(row[8], "2-1") # actual_score
        self.assertEqual(row[9], "WIN") # result
        conn.close()
        
        # Verify JSON file was backed up and renamed
        self.assertFalse(os.path.exists(self.json_path))
        self.assertTrue(os.path.exists(self.json_path + ".bak"))

    def test_save_and_update_prediction(self):
        init_db(self.db_path, self.json_path)
        
        # 1. Save prediction
        save_prediction_db(
            match_id="m_100",
            date_str="2026-08-05",
            home_team="Chelsea",
            away_team="Arsenal",
            handicap_val=-0.5,
            rec_team="Chelsea",
            edge_val=0.08,
            win_prob=0.55,
            db_path=self.db_path
        )
        
        # Check initial state
        stats = get_stats_db(self.db_path)
        self.assertEqual(stats, {}) # No resolved matches yet
        
        # 2. Update with finished score
        finished = {"m_100": "1-0"}
        update_predictions_db(finished, self.db_path)
        
        # Check resolved state
        stats = get_stats_db(self.db_path)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 0)
        self.assertEqual(stats["draws"], 0)
        self.assertEqual(stats["win_rate"], 100.0)
        
        # Check recent predictions output format
        recent = get_recent_predictions_db(5, self.db_path)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["match_id"], "m_100")
        self.assertEqual(recent[0]["result"], "WIN")
        self.assertEqual(recent[0]["actual_score"], "1-0")

    def test_draw_resolution(self):
        init_db(self.db_path, self.json_path)
        
        # Handicap is 0.0 (เสมอ)
        save_prediction_db("m_200", "2026-08-05", "Real Madrid", "Barcelona", 0.0, "Real Madrid", 0.05, 0.45, self.db_path)
        update_predictions_db({"m_200": "1-1"}, self.db_path)
        
        stats = get_stats_db(self.db_path)
        self.assertEqual(stats["draws"], 1)
        self.assertEqual(stats["wins"], 0)
        self.assertEqual(stats["losses"], 0)
        
    def test_away_win_resolution(self):
        init_db(self.db_path, self.json_path)
        
        # Handicap is 0.25 (เสมอควบครึ่ง - home receives 0.25)
        # Recommendation is Away (Barcelona)
        # Score is 0-0
        save_prediction_db("m_300", "2026-08-05", "Real Madrid", "Barcelona", 0.25, "Barcelona", 0.06, 0.50, self.db_path)
        update_predictions_db({"m_300": "0-0"}, self.db_path)
        
        # diff = 0 - 0 + 0.25 = +0.25. Since diff > 0, Home wins. Since we recommended Away, we lose.
        recent = get_recent_predictions_db(5, self.db_path)
        self.assertEqual(recent[0]["result"], "LOSE")
