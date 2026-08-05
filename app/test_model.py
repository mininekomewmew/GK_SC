import unittest
from app.model import calculate_prediction

class TestModel(unittest.TestCase):
    def test_poisson_and_edge_calculation(self):
        mock_analysis = {
            "gameInfo": {
                "taname": "Team A",
                "tbname": "Team B",
                "handicap": "0.25",
                "updatedtime": "04/08/2026"
            },
            "gameTeamHistory": {
                "A": {
                    "all": {
                        "history": {
                            "liveA": [2, 1, 3, 0, 1],
                            "liveB": [1, 1, 0, 2, 0]
                        }
                    }
                },
                "B": {
                    "all": {
                        "history": {
                            "liveA": [0, 1, 2, 0, 1],
                            "liveB": [2, 3, 1, 2, 1]
                        }
                    }
                }
            },
            "gamePrediction": {
                "p": "เสมอ",
                "ct": "ฟอร์มสูสี"
            }
        }
        result = calculate_prediction(mock_analysis)
        self.assertIn("home_xg", result)
        self.assertIn("away_xg", result)
        self.assertIn("value_recommendation", result)
        self.assertGreater(result["home_xg"], 0)

    def test_odds_implied_probability_calculation(self):
        mock_analysis = {
            "gameInfo": {
                "taname": "Team A",
                "tbname": "Team B",
                "handicap": "0.25",
                "updatedtime": "04/08/2026"
            },
            "gameTeamHistory": {},
            "gamePrediction": {}
        }
        # Pass Home Odds = 1.25 and Away Odds = 0.72
        result = calculate_prediction(mock_analysis, home_odds=1.25, away_odds=0.72)
        self.assertIn("edge_value", result)

if __name__ == '__main__':
    unittest.main()

