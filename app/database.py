import os
import json
import sqlite3

def get_db_path() -> str:
    return os.environ.get("DB_PATH", "predictions.db")

def get_db_connection(db_path: str = None):
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = None, json_history_path: str = "predictions_history.json"):
    if db_path is None:
        db_path = get_db_path()
    conn = get_db_connection(db_path)
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
    conn.commit()
    
    # Check for legacy JSON history to migrate
    if os.path.exists(json_history_path):
        try:
            with open(json_history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
            
            migrated_count = 0
            for m_id, item in history.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO predictions (
                        match_id, date, home_team, away_team, handicap_value,
                        rec_team, edge_val, win_prob, actual_score, result
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    m_id,
                    item.get("date", ""),
                    item.get("home_team", ""),
                    item.get("away_team", ""),
                    item.get("handicap_value", 0.0),
                    item.get("rec_team", ""),
                    item.get("edge_val", 0.0),
                    item.get("win_prob", 0.0),
                    item.get("actual_score"),
                    item.get("result")
                ))
                if cursor.rowcount > 0:
                    migrated_count += 1
            
            conn.commit()
            if migrated_count > 0:
                print(f"Migrated {migrated_count} legacy predictions from JSON to SQLite.")
                
            # Rename legacy file to avoid migrating next time
            legacy_bak = json_history_path + ".bak"
            if os.path.exists(legacy_bak):
                os.remove(legacy_bak)
            os.rename(json_history_path, legacy_bak)
        except Exception as e:
            print(f"Error during legacy JSON migration: {e}")
            
    conn.close()

def save_prediction_db(
    match_id: str,
    date_str: str,
    home_team: str,
    away_team: str,
    handicap_val: float,
    rec_team: str,
    edge_val: float,
    win_prob: float,
    db_path: str = None
):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO predictions (
            match_id, date, home_team, away_team, handicap_value,
            rec_team, edge_val, win_prob, actual_score, result
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            (SELECT actual_score FROM predictions WHERE match_id = ?),
            (SELECT result FROM predictions WHERE match_id = ?)
        )
    """, (
        match_id, date_str, home_team, away_team, handicap_val,
        rec_team, edge_val, win_prob, match_id, match_id
    ))
    conn.commit()
    conn.close()

def update_predictions_db(finished_scores: dict, db_path: str = None):
    if not finished_scores:
        return
        
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Query all predictions without an actual_score
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
                    if diff > 0:
                        result = "WIN"
                    elif diff < 0:
                        result = "LOSE"
                    else:
                        result = "DRAW"
                else:
                    if diff < 0:
                        result = "WIN"
                    elif diff > 0:
                        result = "LOSE"
                    else:
                        result = "DRAW"
                        
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

def get_stats_db(db_path: str = None) -> dict:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE result IS NOT NULL")
    total = cursor.fetchone()[0]
    
    if total == 0:
        conn.close()
        return {}
        
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE result = 'WIN'")
    wins = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE result = 'LOSE'")
    losses = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE result = 'DRAW'")
    draws = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0.0
    }

def get_recent_predictions_db(limit: int = 5, db_path: str = None) -> list:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM predictions
        WHERE result IS NOT NULL
        ORDER BY date DESC, match_id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
