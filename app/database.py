import os
import sqlite3
import sys

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            is_testing = "unittest" in sys.modules or "pytest" in sys.modules or "test" in sys.argv[0]
            default_db = "test_predictions.db" if is_testing else "predictions.db"
            self.db_path = os.environ.get("DB_PATH", default_db)
        else:
            self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                match_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                handicap_value REAL NOT NULL,
                rec_team TEXT NOT NULL,
                edge_val REAL NOT NULL,
                win_prob REAL NOT NULL,
                actual_score TEXT,
                result TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_ids (
                group_id TEXT PRIMARY KEY
            )
        """)
        try:
            cursor.execute("ALTER TABLE predictions ADD COLUMN is_best_tip INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def save_prediction(self, match_id: str, date_str: str, home_team: str, away_team: str, 
                        handicap_val: float, rec_team: str, edge_val: float, win_prob: float, is_best_tip: bool = False):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO predictions (
                match_id, date, home_team, away_team, handicap_value,
                rec_team, edge_val, win_prob, is_best_tip, actual_score, result
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                (SELECT actual_score FROM predictions WHERE match_id = ?),
                (SELECT result FROM predictions WHERE match_id = ?)
            )
        """, (
            match_id, date_str, home_team, away_team, handicap_val,
            rec_team, edge_val, win_prob, 1 if is_best_tip else 0, match_id, match_id
        ))
        conn.commit()
        conn.close()

    def update_predictions(self, finished_scores: dict):
        if not finished_scores:
            return
            
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE actual_score IS NULL")
        rows = cursor.fetchall()
        
        updated_count = 0
        for row in rows:
            m_id = row["match_id"]
            if m_id in finished_scores:
                score = finished_scores[m_id]
                try:
                    h_score, a_score = map(int, score.split("-"))
                    hdcp = row["handicap_value"]
                    diff = h_score - a_score + hdcp
                    
                    rec_team = row["rec_team"]
                    home_team = row["home_team"]
                    
                    if rec_team == home_team:
                        result = "WIN" if diff > 0 else "LOSE" if diff < 0 else "DRAW"
                    else:
                        result = "WIN" if diff < 0 else "LOSE" if diff > 0 else "DRAW"
                            
                    cursor.execute("""
                        UPDATE predictions
                        SET actual_score = ?, result = ?
                        WHERE match_id = ?
                    """, (score, result, m_id))
                    updated_count += 1
                except Exception:
                    pass
                    
        if updated_count > 0:
            conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        def fetch_stats(condition: str = ""):
            where_clause = f"WHERE result IS NOT NULL {condition}"
            cursor.execute(f"SELECT COUNT(*) FROM predictions {where_clause}")
            total = cursor.fetchone()[0]
            if total == 0:
                return {"total": 0, "wins": 0, "losses": 0, "draws": 0, "win_rate": 0.0}
                
            cursor.execute(f"SELECT COUNT(*) FROM predictions {where_clause} AND result = 'WIN'")
            wins = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM predictions {where_clause} AND result = 'LOSE'")
            losses = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM predictions {where_clause} AND result = 'DRAW'")
            draws = cursor.fetchone()[0]
            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0.0
            }
            
        stats = {
            "all": fetch_stats(""),
            "best": fetch_stats("AND is_best_tip = 1"),
            "other": fetch_stats("AND is_best_tip = 0")
        }
        conn.close()
        return stats

    def get_recent_predictions(self, limit: int = 5, is_best_tip: bool = None) -> list:
        conn = self.get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM predictions WHERE result IS NOT NULL"
        params = []
        if is_best_tip is not None:
            query += " AND is_best_tip = ?"
            params.append(1 if is_best_tip else 0)
        query += " ORDER BY date DESC, match_id DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def save_group_id(self, group_id: str):
        if not group_id:
            return
        conn = self.get_connection()
        conn.execute("INSERT OR IGNORE INTO group_ids (group_id) VALUES (?)", (group_id,))
        conn.commit()
        conn.close()

    def get_group_ids(self) -> list:
        conn = self.get_connection()
        rows = [row[0] for row in conn.execute("SELECT group_id FROM group_ids").fetchall()]
        conn.close()
        return rows
