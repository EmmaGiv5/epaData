import os
import unittest
from unittest.mock import patch

from flask import Flask

from app import db
from app.routes.download import download_bp
from app.routes.explorer import explorer_bp
from app.routes.main import main_bp


class SearchNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_dir = os.path.join(os.path.dirname(__file__), "..", "app")
        cls.app = Flask(
            __name__,
            template_folder=os.path.join(app_dir, "templates"),
            static_folder=os.path.join(app_dir, "static"),
        )
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY="search-navigation-test-key",
        )
        db.init_app(cls.app)
        cls.app.register_blueprint(main_bp)
        cls.app.register_blueprint(explorer_bp)
        cls.app.register_blueprint(download_bp)

    def test_basic_results_back_link_opens_search_form_without_rerunning(self):
        record = {"facilityName": "Coal Plant", "co2Mass": 100}
        client = self.app.test_client()

        with patch(
            "app.routes.main._fetch_annual_facility_records",
            return_value=([record], 1),
        ) as fetch_records:
            response = client.get(
                "/results?search_type=basic&query=Kentucky"
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"edit=1", response.data)

            back_response = client.get(
                "/basic-search?query=Kentucky&edit=1"
            )

        self.assertEqual(back_response.status_code, 200)
        self.assertIn(b"Basic &amp; Description-Based Search", back_response.data)
        self.assertNotIn(b"Basic Search Results", back_response.data)
        self.assertEqual(fetch_records.call_count, 1)

    def test_advanced_results_back_link_opens_prefilled_form(self):
        record = {"facilityName": "Coal Plant", "co2Mass": 100}
        client = self.app.test_client()

        with patch(
            "app.routes.main._fetch_annual_facility_records",
            return_value=([record], 1),
        ) as fetch_records:
            response = client.get(
                "/results?search_type=advanced&state=KY"
                "&year_from=2024&year_to=2024"
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"edit=1", response.data)

            back_response = client.get(
                "/advanced-search?state=KY&year_from=2024"
                "&year_to=2024&edit=1"
            )

        self.assertEqual(back_response.status_code, 200)
        self.assertIn(b"Advanced Search", back_response.data)
        self.assertNotIn(b"Advanced Search Results", back_response.data)
        self.assertEqual(fetch_records.call_count, 1)

    def test_search_forms_link_back_to_search_options(self):
        client = self.app.test_client()

        for path in (
            "/basic-search?edit=1",
            "/advanced-search?edit=1",
            "/campd-search",
        ):
            with self.subTest(path=path):
                response = client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertIn(b'href="/search"', response.data)
