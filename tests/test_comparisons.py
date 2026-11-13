import os
import unittest

from flask import Flask
from sqlalchemy import text

from app import db
from app.models import AnnualRecord, Dataset, Facility, Unit
from app.routes.download import download_bp
from app.routes.explorer import explorer_bp
from app.routes.main import main_bp
from app.services.comparison_service import build_comparison


class ComparisonServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(
            __name__,
            template_folder=os.path.join(
                os.path.dirname(__file__), "..", "app", "templates"
            ),
            static_folder=os.path.join(
                os.path.dirname(__file__), "..", "app", "static"
            ),
        )
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY="comparison-test-key",
        )
        db.init_app(cls.app)
        cls.app.register_blueprint(main_bp)
        cls.app.register_blueprint(explorer_bp)
        cls.app.register_blueprint(download_bp)
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()
            db.session.remove()

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()
        db.session.execute(text("DROP TABLE IF EXISTS calc_data_annual"))
        db.session.execute(text("DROP TABLE IF EXISTS calc_data_hourly"))
        db.session.execute(text(
            'CREATE TABLE calc_data_annual ('
            '"State" TEXT, "Year" INTEGER, '
            '"Gross Load (MWh)" REAL, "Steam Load (1000 lb)" REAL, '
            '"SO2 Mass (short tons)" REAL, "CO2 Mass (short tons)" REAL, '
            '"NOx Mass (short tons)" REAL, "Heat Input (mmBtu)" REAL, '
            'id INTEGER PRIMARY KEY)'
        ))
        db.session.execute(text(
            'INSERT INTO calc_data_annual '
            '("State", "Year", "Gross Load (MWh)", "CO2 Mass (short tons)") '
            'VALUES '
            '("KY", 2023, 100, 20), '
            '("KY", 2024, 0, 10), '
            '("TN", 2024, 100, 50)'
        ))
        db.session.execute(text(
            'CREATE TABLE calc_data_hourly ('
            '"State" TEXT, "Date" TEXT, "Hour" INTEGER, '
            '"Gross Load (MW)" INTEGER, "Steam Load (1000 lb/hr)" TEXT, '
            '"SO2 Mass (lbs)" REAL, "CO2 Mass (short tons)" REAL, '
            '"NOx Mass (lbs)" REAL, "Heat Input (mmBtu)" REAL, '
            'id INTEGER PRIMARY KEY)'
        ))
        db.session.execute(text(
            'INSERT INTO calc_data_hourly '
            '("State", "Date", "Gross Load (MW)", "CO2 Mass (short tons)") '
            'VALUES ("KY", "2023-01-01", 100, 4), '
            '("KY", "2024-01-01", 100, 8)'
        ))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_computes_group_statistics_and_reference_differences(self):
        result = build_comparison(
            dataset_key="annual_state",
            metric_key="co2_mass",
            group_key="state",
            aggregation="mean",
            baseline="KY",
            year_from=None,
            year_to=None,
        )
        by_group = {summary["group"]: summary for summary in result["summaries"]}

        self.assertEqual(by_group["KY"]["count"], 2)
        self.assertEqual(by_group["KY"]["missing_count"], 0)
        self.assertEqual(by_group["KY"]["mean"], 15)
        self.assertEqual(by_group["KY"]["difference"], 0)
        self.assertAlmostEqual(
            by_group["TN"]["percentage_difference"],
            (50 - 15) / 15 * 100,
        )
        self.assertEqual(result["units"], "short tons")

    def test_intensity_omits_zero_denominators(self):
        result = build_comparison(
            dataset_key="annual_state",
            metric_key="co2_intensity",
            group_key="state",
            aggregation="mean",
            baseline="KY",
            year_from=None,
            year_to=None,
        )
        by_group = {summary["group"]: summary for summary in result["summaries"]}

        self.assertEqual(by_group["KY"]["count"], 1)
        self.assertEqual(by_group["KY"]["missing_count"], 1)
        self.assertEqual(by_group["KY"]["mean"], 0.2)
        self.assertEqual(result["units"], "short tons / MWh")

    def test_hourly_dataset_groups_by_year_from_date(self):
        result = build_comparison(
            dataset_key="hourly_state",
            metric_key="co2_mass",
            group_key="year",
            aggregation="sum",
            baseline="2023",
            year_from=2023,
            year_to=2024,
        )
        by_group = {summary["group"]: summary for summary in result["summaries"]}

        self.assertEqual(by_group["2023"]["comparison_value"], 4)
        self.assertEqual(by_group["2024"]["comparison_value"], 8)
        self.assertEqual(by_group["2024"]["difference"], 4)

    def test_unit_records_group_by_fuel_and_control_status(self):
        dataset = Dataset(
            dataset_name="comparison fixture",
            data_source="test",
        )
        db.session.add(dataset)
        db.session.flush()
        facility = Facility(
            dataset_id=dataset.id,
            epa_facility_id="1",
            facility_name="Plant",
            state="KY",
        )
        db.session.add(facility)
        db.session.flush()
        coal_unit = Unit(
            facility_id=facility.id,
            epa_unit_id="1",
            primary_fuel="Coal",
        )
        gas_unit = Unit(
            facility_id=facility.id,
            epa_unit_id="2",
            primary_fuel="Gas",
        )
        db.session.add_all((coal_unit, gas_unit))
        db.session.flush()
        db.session.add_all((
            AnnualRecord(
                unit_id=coal_unit.id,
                reporting_year=2024,
                gross_load=100,
                co2_mass=50,
                so2_control=None,
            ),
            AnnualRecord(
                unit_id=gas_unit.id,
                reporting_year=2024,
                gross_load=100,
                co2_mass=20,
                so2_control="No",
            ),
        ))
        db.session.commit()

        result = build_comparison(
            dataset_key="unit_annual",
            metric_key="co2_intensity",
            group_key="so2_control_status",
            aggregation="mean",
            baseline="Not specified",
            year_from=2024,
            year_to=2024,
        )
        by_group = {summary["group"]: summary for summary in result["summaries"]}

        self.assertIn("Not specified", by_group)
        self.assertIn("Without control", by_group)
        self.assertEqual(by_group["Not specified"]["mean"], 0.5)

    def test_comparison_route_renders_all_records_and_chart(self):
        response = self.app.test_client().get(
            "/comparisons?dataset=annual_state&metric=co2_intensity"
            "&group_by=&aggregation=mean"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"All records", response.data)
        self.assertIn(b"comparisonChart", response.data)
