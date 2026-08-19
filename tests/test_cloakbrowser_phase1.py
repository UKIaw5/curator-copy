import unittest
from cloakbrowser import launch

class TestCloakBrowserPhase1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # テスト全体で1回起動
        cls.browser = launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        # 全テスト終了時にブラウザを破棄
        cls.browser.close()

    def test_launch_and_navigate(self):
        page = self.browser.new_page()
        response = page.goto("https://example.com")
        self.assertEqual(response.status, 200)
        self.assertIn("Example Domain", page.title())
        page.close()

if __name__ == "__main__":
    unittest.main()