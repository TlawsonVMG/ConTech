from io import BytesIO
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from ridgeflow import create_app
from ridgeflow.db import get_db
from ridgeflow.services.feedback_ranking import build_feedback_profile, rank_feedback_priorities
from ridgeflow.services.pdf_pipeline import analyze_blueprint_bytes, get_latest_blueprint_analysis
from ridgeflow.services.revision_compare import get_blueprint_revision_compare
from ridgeflow.services.takeoff import build_takeoff_items
from ridgeflow.services.worker_pipeline import process_next_worker_job


class RidgeFlowAppTests(unittest.TestCase):
    def setUp(self):
        base_path = Path(__file__).resolve().parents[1] / ".test-tmp" / uuid4().hex
        base_path.mkdir(parents=True, exist_ok=True)
        self.temp_dir = base_path
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "DATABASE": ":memory:",
                "UPLOAD_FOLDER": str(base_path / "uploads"),
                "BLUEPRINT_UPLOAD_FOLDER": str(base_path / "uploads" / "blueprints"),
                "BLUEPRINT_PAGE_IMAGE_FOLDER": str(base_path / "uploads" / "blueprint-pages"),
                "SEED_DEMO_DATA": True,
                "AUTO_INIT_DB": True,
                "RASTERIZER_BACKEND": "mock",
                "OCR_BACKEND": "mock",
                "VISION_BACKEND": "mock",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _sample_pdf_bytes(self, text):
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
            + f"4 0 obj << /Length {len(escaped) + 12} >> stream\nBT ({escaped}) Tj ET\nendstream\nendobj\n".encode("latin-1")
            + b"trailer << /Root 1 0 R >>\n%%EOF"
        )

    def test_dashboard_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"RidgeFlow", response.data)

    def test_project_creation_flow(self):
        response = self.client.post(
            "/projects/new",
            data={
                "name": "Harbor View Office",
                "client_name": "Harbor View Group",
                "project_type": "Bid",
                "roof_system": "EPDM",
                "address": "101 Harbor View Dr",
                "estimator_name": "Ava Cole",
                "bid_date": "2026-04-25",
                "due_date": "2026-04-24",
                "notes": "Waterproofing review required.",
            },
        )

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            project = get_db().execute(
                "SELECT * FROM projects WHERE name = ?",
                ("Harbor View Office",),
            ).fetchone()
            self.assertIsNotNone(project)
            self.assertEqual(project["roof_system"], "EPDM")

    def test_takeoff_generator_returns_materials(self):
        items = build_takeoff_items(
            system_type="Architectural Shingles",
            roof_area_squares=28,
            waste_pct=8,
            perimeter_feet=240,
            ridge_feet=52,
            valley_feet=18,
            eave_feet=116,
        )

        self.assertGreaterEqual(len(items), 5)
        self.assertEqual(items[0]["material_name"], "Laminated shingles")

    def test_pdf_pipeline_extracts_measurement_hints(self):
        analysis = analyze_blueprint_bytes(
            self._sample_pdf_bytes(
                "R1.1 Roof Plan TPO roof area 12500 sq ft perimeter 430 lf ridge 0 lf eave 215 lf waste 6%. "
                "Detail sheet includes coping, edge metal, and 4 drains."
            ),
            roof_system_hint="TPO",
        )

        self.assertEqual(analysis["roof_system_suggestion"], "TPO")
        self.assertEqual(analysis["page_count"], 1)
        self.assertEqual(analysis["measurement_data"]["roof_area_sqft"], 12500.0)
        self.assertEqual(analysis["measurement_data"]["perimeter_feet"], 430.0)
        self.assertEqual(analysis["structured_data"]["drains_count"], 4.0)
        self.assertIn("edge metal", analysis["structured_data"]["flashing_types"])
        self.assertGreaterEqual(analysis["field_confidence"]["roof_area_sqft"], 0.75)
        self.assertGreaterEqual(analysis["page_role_summary"]["roof_plan"], 1)
        self.assertIn("R1.1", analysis["sheet_labels"])

    def test_blueprint_upload_triggers_analysis(self):
        response = self.client.post(
            "/projects/1/blueprints",
            data={
                "phase_label": "Permit",
                "version_label": "v4",
                "page_count": "1",
                "notes": "Upload from test",
                "blueprint_file": (
                    BytesIO(
                        self._sample_pdf_bytes(
                            "R4.1 Roof Plan EPDM roof area 82 squares perimeter 360 lf eave 180 lf."
                        )
                    ),
                    "epdm-test.pdf",
                ),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            blueprint = get_db().execute(
                "SELECT * FROM blueprints WHERE original_filename = ?",
                ("epdm-test.pdf",),
            ).fetchone()
            self.assertIsNotNone(blueprint)
            self.assertEqual(blueprint["analysis_status"], "Completed")
            analysis_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM blueprint_analyses WHERE blueprint_id = ?",
                (blueprint["id"],),
            ).fetchone()["count"]
            self.assertEqual(analysis_count, 1)

    def test_takeoff_from_blueprint_analysis_flow(self):
        response = self.client.post("/projects/3/blueprints/3/takeoff-from-analysis")
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            takeoff = get_db().execute(
                """
                SELECT *
                FROM takeoff_runs
                WHERE project_id = ? AND blueprint_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (3, 3),
            ).fetchone()
            self.assertIsNotNone(takeoff)
            self.assertEqual(takeoff["source_mode"], "blueprint-analysis")
            self.assertIsNotNone(takeoff["blueprint_analysis_id"])

    def test_worker_pipeline_processes_queued_blueprint(self):
        response = self.client.post(
            "/projects/1/blueprints",
            data={
                "phase_label": "Issued for Pricing",
                "version_label": "v5",
                "page_count": "1",
                "notes": "Worker test upload",
                "blueprint_file": (
                    BytesIO(
                        self._sample_pdf_bytes(
                            "R7.1 Roof Plan TPO roof area 156 squares perimeter 510 lf ridge 0 lf eave 255 lf."
                        )
                    ),
                    "worker-test.pdf",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            blueprint = get_db().execute(
                "SELECT * FROM blueprints WHERE original_filename = ?",
                ("worker-test.pdf",),
            ).fetchone()
            self.assertIsNotNone(blueprint)

            processed = []
            while True:
                result = process_next_worker_job()
                if result is None:
                    break
                processed.append(result["job_type"])

            self.assertEqual(
                processed,
                [
                    "rasterize_blueprint",
                    "ocr_blueprint_pages",
                    "vision_blueprint_pages",
                    "consolidate_blueprint_analysis",
                ],
            )

            render_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM blueprint_page_renders WHERE blueprint_id = ?",
                (blueprint["id"],),
            ).fetchone()["count"]
            extraction_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM blueprint_page_extractions WHERE blueprint_id = ?",
                (blueprint["id"],),
            ).fetchone()["count"]
            self.assertGreaterEqual(render_count, 1)
            self.assertGreaterEqual(extraction_count, 2)

            latest_analysis = get_latest_blueprint_analysis(get_db(), blueprint["id"])
            self.assertEqual(latest_analysis["parser_name"], "worker-enhanced-pipeline")

    def test_estimator_correction_updates_effective_takeoff_seed(self):
        response = self.client.post(
            "/projects/3/blueprints/3/analysis-corrections",
            data={
                "roof_area_squares": "41.5",
                "perimeter_feet": "388",
                "waste_pct": "9",
                "flashing_types": "drip edge, step flashing",
                "corrected_by_name": "Ava Cole",
                "notes": "Confirmed from roof plan and edge detail.",
            },
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            analysis = get_latest_blueprint_analysis(get_db(), 3)
            self.assertEqual(analysis["effective_structured_data"]["roof_area_squares"], 41.5)
            self.assertEqual(analysis["effective_structured_data"]["perimeter_feet"], 388.0)
            self.assertIn("step flashing", analysis["effective_structured_data"]["flashing_types"])
            self.assertEqual(analysis["takeoff_seed"]["roof_area_squares"], 41.5)
            self.assertEqual(analysis["takeoff_seed"]["waste_pct"], 9.0)

        response = self.client.post("/projects/3/blueprints/3/takeoff-from-analysis")
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            takeoff = get_db().execute(
                """
                SELECT *
                FROM takeoff_runs
                WHERE project_id = ? AND blueprint_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (3, 3),
            ).fetchone()
            self.assertIsNotNone(takeoff)
            self.assertEqual(takeoff["roof_area_squares"], 41.5)
            self.assertEqual(takeoff["perimeter_feet"], 388.0)

    def test_revision_compare_created_for_new_blueprint_version(self):
        response = self.client.post(
            "/projects/1/blueprints",
            data={
                "phase_label": "Permit",
                "version_label": "v4",
                "page_count": "1",
                "notes": "Revision compare upload",
                "blueprint_file": (
                    BytesIO(
                        self._sample_pdf_bytes(
                            "R1.1 Roof Plan TPO roof area 205 squares perimeter 648 lf eave 640 lf waste 7%. "
                            "Detail sheets add edge metal, counterflashing, and 6 drains."
                        )
                    ),
                    "west-ridge-v4.pdf",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            blueprint = get_db().execute(
                "SELECT * FROM blueprints WHERE original_filename = ?",
                ("west-ridge-v4.pdf",),
            ).fetchone()
            self.assertIsNotNone(blueprint)

            revision_compare = get_blueprint_revision_compare(get_db(), blueprint["id"])
            self.assertIsNotNone(revision_compare)
            self.assertEqual(revision_compare["base_blueprint_id"], 1)
            self.assertEqual(revision_compare["status"], "Review Required")
            self.assertIn("Compared v4 to v3", revision_compare["summary"])
            self.assertGreater(
                revision_compare["metric_deltas"]["roof_area_squares"]["candidate_value"],
                revision_compare["metric_deltas"]["roof_area_squares"]["base_value"],
            )
            self.assertTrue(revision_compare["review_flags"])

        page = self.client.get("/projects/1")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Revision Compare", page.data)

    def test_feedback_ranking_uses_estimator_correction_history(self):
        with self.app.app_context():
            db = get_db()
            project = db.execute("SELECT * FROM projects WHERE id = ?", (1,)).fetchone()
            analysis = get_latest_blueprint_analysis(db, 1)
            profile = build_feedback_profile(db, project["roof_system"])
            priorities = rank_feedback_priorities(db, project["roof_system"], analysis, limit=20, feedback_profile=profile)

            self.assertGreaterEqual(profile["total_corrections"], 3)
            self.assertGreaterEqual(len(priorities), 3)
            field_names = [priority["field_name"] for priority in priorities]
            self.assertIn("roof_area_squares", field_names)
            self.assertIn("flashing_types", field_names)

        page = self.client.get("/projects/1")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Feedback Priority", page.data)
        self.assertIn(b"Estimator Driven", page.data)


if __name__ == "__main__":
    unittest.main()
