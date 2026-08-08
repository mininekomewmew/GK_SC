import unittest
from unittest.mock import MagicMock, patch
from app.model import PredictionEngine
from app.club_elo import EloService
from app.scraper import CacheManager

class TestModel(unittest.TestCase):
    def setUp(self):
        self.cache = CacheManager()
        self.elo = EloService(self.cache)
        self.engine = PredictionEngine(self.elo)

    def test_poisson_and_edge_calculation(self):
        mock_analysis = {
            "gameInfo": {
                "taname": "Team A", "tbname": "Team B", "handicap": "0.25",
                "updatedtime": "04/08/2026", "neutral": 0, "taid": 1, "tbid": 2
            },
            "gameTeamHistory": {
                "A": {"all": {"history": {"liveA": [2, 1, 3, 0, 1], "liveB": [1, 1, 0, 2, 0]}}},
                "B": {"all": {"history": {"liveA": [0, 1, 2, 0, 1], "liveB": [2, 3, 1, 2, 1]}}}
            },
            "gamehistory": {
                "historymatch": {"aid": [1, 2], "bid": [2, 1], "liveA": [2, 1], "liveB": [1, 3]}
            }
        }
        result = self.engine.calculate_prediction(mock_analysis)
        self.assertIn("home_xg", result)
        self.assertIn("away_xg", result)
        self.assertGreater(result["home_xg"], 0)

    def test_odds_implied_probability_calculation(self):
        mock_analysis = {
            "gameInfo": {"taname": "Team A", "tbname": "Team B", "handicap": "0.25", "updatedtime": "04/08/2026"},
            "gameTeamHistory": {}, "gamehistory": {}
        }
        result = self.engine.calculate_prediction(mock_analysis, home_odds=1.25, away_odds=0.72)
        self.assertIn("edge_value", result)

    @patch('app.club_elo.EloService.get_match_elo_ratings')
    def test_elo_rating_adjustments(self, mock_elo):
        mock_elo.return_value = (1900.0, 1700.0)
        mock_analysis = {
            "gameInfo": {"taname": "เชลซี", "tbname": "ลิเวอร์พูล", "handicap": "0", "updatedtime": "06/08/2026"},
            "gameTeamHistory": {}, "gamehistory": {}
        }
        result = self.engine.calculate_prediction(mock_analysis)
        self.assertAlmostEqual(result["home_xg"], 1.37, places=2)
        self.assertAlmostEqual(result["away_xg"], 0.76, places=2)
        self.assertEqual(result["home_elo"], 1900.0)
        self.assertEqual(result["away_elo"], 1700.0)

if __name__ == '__main__':
    unittest.main()
