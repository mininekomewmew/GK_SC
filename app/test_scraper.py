import unittest
from unittest.mock import patch, MagicMock
from app.scraper import fetch_match_analysis

class TestScraper(unittest.TestCase):
    @patch('app.scraper.requests.get')
    def test_parse_javascript_variables(self, mock_get):
        # Simulated HTML content with javascript variables
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = """
        <html>
        <head>
        <script type="text/javascript">
        var gameInfo = {"taname":"Team A","tbname":"Team B","handicap":"0.25","updatedtime":"04/08/2026"};
        var gamehistory = {"historymatch": {}};
        var gameTeamHistory = {"A":{"all":{"history":{"liveA":[1],"liveB":[0]}}},"B":{"all":{"history":{"liveA":[0],"liveB":[2]}}}};
        var gamePrediction = {"p":"เสมอ","cf":"★★★★★","ct":"วิเคราะห์เกม..."};
        </script>
        </head>
        </html>
        """
        data = fetch_match_analysis("12345")
        self.assertEqual(data["gameInfo"]["taname"], "Team A")
        self.assertEqual(data["gameTeamHistory"]["A"]["all"]["history"]["liveA"], [1])
        self.assertNotIn("gamePrediction", data)

    def test_extract_json_block_robustness(self):
        from app.scraper import extract_json_block
        html_input = """
        var nested = {"a": {"b": "escaped \\" quote"}, "c": 3};
        """
        parsed = extract_json_block(html_input, "nested")
        self.assertEqual(parsed["a"]["b"], 'escaped " quote')
        self.assertEqual(parsed["c"], 3)

    @patch('app.scraper.requests.get')
    def test_caching_fetch_today_matches(self, mock_get):
        from app.scraper import fetch_today_matches, clear_cache
        clear_cache()
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<html><tr class='utable_tr' id='123'><td class='utable_f1'>22:00</td><td class='utable_f2'><span>Team A</span></td><td class='classodds'>0.25</td><td class='utable_f4'><span>Team B</span></td></tr></html>"
        
        # First call: hits the mocked request
        res1 = fetch_today_matches()
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["home_team"], "Team A")
        
        # Change mock response to verify cache is used instead of making new request
        mock_get.return_value.content = b"<html></html>"
        res2 = fetch_today_matches()
        # Should return cached data
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["home_team"], "Team A")
        
        # Clear cache and verify it fails to find data (or returns empty list now)
        clear_cache()
        res3 = fetch_today_matches()
        self.assertEqual(len(res3), 0)

    @patch('app.scraper.requests.get')
    def test_fetch_polball_analysis(self, mock_get):
        from app.scraper import fetch_polball_analysis, clear_cache
        clear_cache()
        
        mock_home = MagicMock()
        mock_home.status_code = 200
        mock_home.text = """
        <html>
            <a href="https://www.polball.club/123/ผลบอล-วิเคราะห์บอล-เอจีเอฟ-อาร์ฮุส--vs--ซาบาห์">วิเคราะห์บอล : เอจีเอฟ อาร์ฮุส -vs- ซาบาห์</a>
        </html>
        """
        
        mock_detail = MagicMock()
        mock_detail.status_code = 200
        mock_detail.text = """
        <html>
            <p>ทีเด็ดบอล : รอง ซาบาห์</p>
            <p>ผลที่คาด : เสมอ 1-1</p>
        </html>
        """
        
        mock_get.side_effect = [mock_home, mock_detail]
        
        res = fetch_polball_analysis("อาร์ฮุส", "ซาบาห์")
        self.assertIsNotNone(res)
        self.assertEqual(res["tip"], "รอง ซาบาห์")
        self.assertEqual(res["score"], "เสมอ 1-1")

if __name__ == '__main__':
    unittest.main()

