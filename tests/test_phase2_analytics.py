import os
import unittest

from flask import Flask
from sqlalchemy import text

from app import db
from app.models import AnnualRecord, Dataset, Facility, Unit
from app.routes.download import download_bp
from app.routes.explorer import explorer_bp
from app.routes.main import (
    _read_traci_factors,
    _traci_impact_unit,
    main_bp,
)
from app.services.analysis_service import build_analysis


class PhaseTwoAnalyticsTests(unittest.TestCase):
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
            SECRET_KEY="phase-two-test-key",
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
        db.session.execute(text("DROP TABLE IF EXISTS calc_data_annual"))
        db.create_all()

        dataset = Dataset(dataset_name="analysis fixture", data_source="test")
        db.session.add(dataset)
        db.session.flush()
        facility = Facility(
            dataset_id=dataset.id,
            epa_facility_id="101",
            facility_name="River Station",
            state="KY",
            latitude=37.5,
            longitude=-85.0,
        )
        db.session.add(facility)
        db.session.flush()
        coal_unit = Unit(
            facility_id=facility.id,
            epa_unit_id="1",
            unit_type="Boiler",
            primary_fuel="Coal",
        )
        gas_unit = Unit(
            facility_id=facility.id,
            epa_unit_id="2",
            unit_type="Turbine",
            primary_fuel="Gas",
        )
        db.session.add_all((coal_unit, gas_unit))
        db.session.flush()
        db.session.add_all((
            AnnualRecord(
                unit_id=coal_unit.id,
                reporting_year=2023,
                operating_time=4000,
                gross_load=100,
                heat_input=150,
                co2_mass=20,
                so2_mass=1,
                nox_mass=2,
                so2_control="Scrubber",
                nox_control="SCR",
                program_code="ARP",
            ),
            AnnualRecord(
                unit_id=coal_unit.id,
                reporting_year=2024,
                operating_time=4400,
                gross_load=200,
                heat_input=300,
                co2_mass=30,
                so2_mass=None,
                nox_mass=4,
                so2_control="Scrubber",
                nox_control="SCR",
                program_code="ARP",
            ),
            AnnualRecord(
                unit_id=gas_unit.id,
                reporting_year=2024,
                operating_time=None,
                gross_load=0,
                heat_input=100,
                co2_mass=10,
                so2_mass=2,
                nox_mass=1,
                program_code="CSAPR",
            ),
        ))
        db.session.commit()
        self.coal_unit_id = coal_unit.id

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_analysis_filters_and_derived_year_over_year_values(self):
        result = build_analysis({
            "state": "KY",
            "fuel": "Coal",
            "year_from": "2024",
            "year_to": "2024",
            "min_gross_load": "100",
            "variable": "co2_intensity",
            "group_by": "fuel",
            "chart": "bar",
            "control": "SCR",
            "program_code": "ARP",
            "percentiles": "25, 90",
        })

        self.assertEqual(result["summary"], {
            "records": 1,
            "facilities": 1,
            "units": 1,
            "years": 1,
        })
        row = result["rows"][0]
        self.assertEqual(row["co2_intensity"], 0.15)
        self.assertAlmostEqual(row["previous_year_value"], 0.2)
        self.assertAlmostEqual(row["year_over_year_absolute"], -0.05)
        self.assertAlmostEqual(row["year_over_year_percent"], -25)
        self.assertAlmostEqual(
            row["operating_utilization"],
            4400 / 8784 * 100,
        )
        self.assertEqual(result["stats"][0]["percentiles"]["25"], 0.15)
        self.assertEqual(
            next(
                item for item in result["missing_summary"]
                if item["key"] == "so2_mass"
            )["missing"],
            1,
        )

    def test_zero_gross_load_leaves_intensity_missing(self):
        result = build_analysis({
            "unit_id": str(self.coal_unit_id + 1),
            "year_from": "2024",
            "year_to": "2024",
            "variable": "co2_intensity",
        })

        self.assertEqual(result["summary"]["records"], 1)
        self.assertIsNone(result["rows"][0]["co2_intensity"])
        self.assertEqual(result["stats"][0]["count"], 0)
        self.assertEqual(result["stats"][0]["missing_count"], 1)

    def test_builder_page_renders_summary_statistics_and_selected_chart(self):
        response = self.app.test_client().get(
            "/analysis-builder?state=KY&variable=co2_mass"
            "&group_by=year&chart=box"
        )

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Selected dataset", html)
        self.assertIn("Missing-value summary", html)
        self.assertIn("Year-over-year change", html)
        self.assertIn("Analysis Builder", html)
        self.assertIn("2024", html)

    def test_calculation_pages_link_back_to_calculations_menu(self):
        db.session.execute(text(
            'CREATE TABLE calc_data_annual ('
            '"State" TEXT, "Year" INTEGER, '
            '"Gross Load (MWh)" REAL, "CO2 Mass (short tons)" REAL, '
            '"SO2 Mass (short tons)" REAL, "NOx Mass (short tons)" REAL, '
            '"Heat Input (mmBtu)" REAL)'
        ))
        db.session.commit()
        client = self.app.test_client()
        for path in (
            "/analysis-builder",
            "/descriptive-stats",
            "/factored-calculations",
            "/comparisons",
        ):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    b'href="/calculate"> \xe2\x86\x90  Back To Calculations',
                    response.data,
                )

    def test_builder_renders_each_visualization_mode(self):
        client = self.app.test_client()
        for chart_type in (
            "bar",
            "line",
            "histogram",
            "scatter",
            "box",
            "heatmap",
            "ranking",
            "map",
        ):
            with self.subTest(chart=chart_type):
                response = client.get(
                    f"/analysis-builder?state=KY&chart={chart_type}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(chart_type.encode(), response.data)

    def test_analysis_csv_download_preserves_the_filter_query(self):
        response = self.app.test_client().get(
            "/analysis-download?state=KY&year_from=2024"
            "&year_to=2024&fuel=Coal"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn("attachment; filename=\"analysis-records.csv\"",
                      response.headers["Content-Disposition"])
        self.assertIn("River Station", response.get_data(as_text=True))
        self.assertIn("year_over_year_percent", response.get_data(as_text=True))

    def test_traci_factors_match_exact_pollutants_and_air_media(self):
        factors = _read_traci_factors()
        climate_category = next(
            category for category in factors
            if category.startswith("Global Climate Air")
        )
        acidification_category = next(
            category for category in factors
            if category.startswith("Acidification Air")
        )

        self.assertEqual(
            factors[climate_category]["CARBON DIOXIDE"],
            1.0,
        )
        self.assertEqual(
            factors[acidification_category]["SULFUR DIOXIDE"],
            1.0,
        )
        self.assertEqual(
            factors[acidification_category]["NITROGEN OXIDES"],
            0.7,
        )
        self.assertEqual(
            _traci_impact_unit(climate_category),
            "kg CO2 eq",
        )
        self.assertFalse(any(
            "Emission to cont. freshwater" in category
            for category in factors
        ))

    def test_traci_calculation_includes_factor_version_and_mass_intensity(self):
        response = self.app.test_client().post(
            "/factored-calculations",
            data={
                "state": "KY",
                "year_from": "2024",
                "year_to": "2024",
                "unit_id": str(self.coal_unit_id),
                "group_by": "unit",
            },
        )

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("TRACI 2.2", html)
        self.assertIn("907.18474 kg/short ton", html)
        self.assertIn("Impact per MWh", html)
        self.assertIn("Global Climate Air", html)
        self.assertIn("CO2", html)

    def test_calculations_hub_forwards_legacy_post_fields(self):
        response = self.app.test_client().post(
            "/calculate",
            data={
                "state": "KY",
                "year": "2024",
                "group_by": "unit",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TRACI 2.2", response.data)
        self.assertIn(b"2024", response.data)

    def test_traci_calculation_supports_state_level_annual_table(self):
        AnnualRecord.query.delete()
        db.session.execute(text(
            'CREATE TABLE calc_data_annual ('
            '"State" TEXT, "Year" INTEGER, '
            '"Gross Load (MWh)" REAL, "SO2 Mass (short tons)" REAL, '
            '"CO2 Mass (short tons)" REAL, "NOx Mass (short tons)" REAL)'
        ))
        db.session.execute(text(
            'INSERT INTO calc_data_annual '
            '("State", "Year", "Gross Load (MWh)", '
            '"SO2 Mass (short tons)", "CO2 Mass (short tons)", '
            '"NOx Mass (short tons)") '
            'VALUES ("TN", 2024, 100, 1, 2, 3)'
        ))
        db.session.commit()

        response = self.app.test_client().post(
            "/factored-calculations",
            data={
                "state": "TN",
                "year_from": "2024",
                "year_to": "2024",
                "group_by": "state",
            },
        )

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Only state-level impact calculations", html)
        self.assertIn("Global Climate Air", html)
        self.assertIn("kg CO2 eq", html)


if __name__ == "__main__":
    unittest.main()
