import io
import os
import re
import tempfile
import unittest

import pandas as pd
from flask import Flask

from app import db
from app.models import AnnualRecord, Dataset, Facility, Unit
from app.routes.campd import campd_bp
from app.routes.download import download_bp
from app.routes.explorer import explorer_bp
from app.routes.main import main_bp


class UploadImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template_folder = os.path.join(
            os.path.dirname(__file__),
            "..",
            "app",
            "templates",
        )
        cls.app = Flask(
            __name__,
            template_folder=template_folder,
        )
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY="upload-test-key",
        )
        db.init_app(cls.app)
        cls.app.register_blueprint(main_bp)
        cls.app.register_blueprint(explorer_bp)
        cls.app.register_blueprint(download_bp)
        cls.app.register_blueprint(campd_bp)

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
        self.upload_directory = tempfile.TemporaryDirectory()
        self.app.config["UPLOAD_FOLDER"] = self.upload_directory.name
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()
        self.upload_directory.cleanup()

    def test_upload_validate_and_approve_reuses_and_updates_records(self):
        existing_dataset = Dataset(
            dataset_name="previous",
            data_source="EPA uploaded file",
        )
        db.session.add(existing_dataset)
        db.session.flush()

        facility = Facility(
            dataset_id=existing_dataset.id,
            epa_facility_id="54",
            facility_name="Smith Generating Facility",
            state="KY",
        )
        db.session.add(facility)
        db.session.flush()

        unit = Unit(
            facility_id=facility.id,
            epa_unit_id="1",
            unit_type="Boiler",
        )
        db.session.add(unit)
        db.session.flush()

        db.session.add(AnnualRecord(
            unit_id=unit.id,
            reporting_year=2024,
            gross_load=100.0,
        ))
        db.session.commit()

        dataframe = pd.DataFrame([{
            "epa_facility_id": "54",
            "facility_name": "Smith Generating Facility",
            "state": "KY",
            "epa_unit_id": "1",
            "unit_type": "Boiler",
            "primary_fuel": "Coal",
            "secondary_fuel": float("nan"),
            "reporting_year": 2024,
            "operating_time": 10.0,
            "gross_load": 200.0,
            "steam_load": float("nan"),
            "heat_input": 20.0,
            "co2_mass": 30.0,
            "so2_mass": 1.0,
            "nox_mass": 2.0,
            "so2_control": float("nan"),
            "nox_control": float("nan"),
            "pm_control": float("nan"),
            "program_code": "ARP",
        }])

        client = self.app.test_client()
        upload_response = client.post(
            "/upload",
            data={
                "file": (
                    io.BytesIO(dataframe.to_csv(index=False).encode("utf-8")),
                    "updated.csv",
                ),
            },
            content_type="multipart/form-data",
        )

        upload_html = upload_response.get_data(as_text=True)
        self.assertEqual(upload_response.status_code, 200)
        self.assertIn("Validation Passed", upload_html)
        saved_filename_match = re.search(
            r'name="saved_filename"\s+value="([^"]+)"',
            upload_html,
        )
        self.assertIsNotNone(saved_filename_match)

        approval_response = client.post(
            "/upload",
            data={
                "action": "approve",
                "saved_filename": saved_filename_match.group(1),
                "original_filename": "updated.csv",
            },
        )

        self.assertEqual(approval_response.status_code, 302)
        result_response = client.get(approval_response.headers["Location"])
        result_html = result_response.get_data(as_text=True)
        self.assertIn("Import successful. 1 annual records were processed;", result_html)
        self.assertIn("1 existing records were updated.", result_html)
        self.assertEqual(Facility.query.count(), 1)
        self.assertEqual(Unit.query.count(), 1)
        self.assertEqual(AnnualRecord.query.count(), 1)
        self.assertEqual(
            AnnualRecord.query.one().gross_load,
            200.0,
        )

        duplicate_upload_response = client.post(
            "/upload",
            data={
                "file": (
                    io.BytesIO(dataframe.to_csv(index=False).encode("utf-8")),
                    "updated.csv",
                ),
            },
            content_type="multipart/form-data",
        )

        duplicate_upload_html = duplicate_upload_response.get_data(
            as_text=True
        )
        duplicate_saved_filename_match = re.search(
            r'name="saved_filename"\s+value="([^"]+)"',
            duplicate_upload_html,
        )
        self.assertIsNotNone(duplicate_saved_filename_match)

        duplicate_approval_response = client.post(
            "/upload",
            data={
                "action": "approve",
                "saved_filename": duplicate_saved_filename_match.group(1),
                "original_filename": "updated.csv",
            },
        )

        self.assertEqual(duplicate_approval_response.status_code, 302)
        duplicate_result_response = client.get(
            duplicate_approval_response.headers["Location"]
        )
        self.assertIn(
            "This dataset has already been imported.",
            duplicate_result_response.get_data(as_text=True),
        )
        self.assertEqual(Dataset.query.count(), 2)
