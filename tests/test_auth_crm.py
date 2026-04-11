import io
import re
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from contech import create_app
from contech.db import get_db


class ConTechAuthAndCrmTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = Path(__file__).resolve().parents[1] / ".test-tmp"
        self.temp_root.mkdir(exist_ok=True)
        self.temp_path = self.temp_root / f"test-{uuid4().hex}"
        self.temp_path.mkdir(parents=True, exist_ok=False)
        self.database_path = self.temp_path / "test.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DATABASE": str(self.database_path),
                "JOB_DOCUMENT_UPLOAD_FOLDER": str(self.temp_path / "uploads" / "job-documents"),
                "CUSTOMER_LOGO_UPLOAD_FOLDER": str(self.temp_path / "uploads" / "customer-logos"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_path, ignore_errors=True)

    def login(self, username, password):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def portal_login(self, email, password):
        return self.client.post(
            "/portal/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def test_admin_can_log_in_and_see_dashboard(self):
        response = self.login("admin", "ConTech!2026")
        workboard_response = self.client.get("/workboard")
        job_board_response = self.client.get("/jobs/board")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(workboard_response.status_code, 200)
        self.assertEqual(job_board_response.status_code, 200)
        self.assertIn(b"Workspace counts", response.data)
        self.assertIn(b"Customers", response.data)
        self.assertIn(b"Thomas Lawson", response.data)
        self.assertIn(b"Work Board", response.data)
        self.assertIn(b"Follow-Up Queue", workboard_response.data)
        self.assertIn(b"Job build board", job_board_response.data)

    def test_company_signup_creates_isolated_admin_workspace(self):
        signup_page = self.client.get("/signup")
        self.assertEqual(signup_page.status_code, 200)
        self.assertIn(b"Create your ConTech account", signup_page.data)

        response = self.client.post(
            "/signup",
            data={
                "company_name": "Pioneer Roofing Group",
                "full_name": "Avery Parker",
                "username": "avery@pioneer.example",
                "password": "PioneerAdmin!2026",
                "confirm_password": "PioneerAdmin!2026",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your company workspace is ready", response.data)
        self.assertIn(b"Avery Parker", response.data)
        self.assertNotIn(b"Morris Residence", response.data)

        customers_response = self.client.get("/customers")
        jobs_response = self.client.get("/jobs/board")
        inventory_response = self.client.get("/inventory")
        self.assertEqual(customers_response.status_code, 200)
        self.assertEqual(jobs_response.status_code, 200)
        self.assertEqual(inventory_response.status_code, 200)
        self.assertNotIn(b"Morris Residence", customers_response.data)
        self.assertNotIn(b"Morris Residence", jobs_response.data)
        self.assertNotIn(b"architectural", inventory_response.data.lower())

        with self.app.app_context():
            db = get_db()
            user = db.execute(
                """
                SELECT u.role_name, u.is_active, b.name AS branch_name
                FROM users u
                JOIN branches b ON b.id = u.branch_id
                WHERE u.username = ?
                """,
                ("avery@pioneer.example",),
            ).fetchone()
            branch_customer_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM customers
                WHERE branch_id = (SELECT branch_id FROM users WHERE username = ?)
                """,
                ("avery@pioneer.example",),
            ).fetchone()["count"]
        self.assertEqual(user["role_name"], "admin")
        self.assertEqual(user["is_active"], 1)
        self.assertEqual(user["branch_name"], "Pioneer Roofing Group")
        self.assertEqual(branch_customer_count, 0)

    def test_readiness_endpoint_reports_database_status(self):
        response = self.client.get("/api/ready")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["database"]["engine"], "sqlite")
        self.assertTrue(payload["database"]["schema_current"])
        self.assertEqual(payload["database"]["schema_version"], "2026.04.10.quote-line-items")
        self.assertEqual(payload["checks"]["database_connection"], "ok")
        self.assertTrue(payload["checks"]["uploads_writable"])

        with self.app.app_context():
            migration = get_db().execute(
                "SELECT version FROM schema_migrations WHERE version = ?",
                ("2026.04.10.quote-line-items",),
            ).fetchone()
        self.assertIsNotNone(migration)

    def test_bootstrap_admin_supports_empty_production_database(self):
        temp_path = self.temp_root / f"bootstrap-{uuid4().hex}"
        temp_path.mkdir(parents=True, exist_ok=False)
        try:
            database_path = temp_path / "bootstrap.sqlite3"
            app = create_app(
                {
                    "TESTING": True,
                    "SECRET_KEY": "test",
                    "DATABASE": str(database_path),
                    "AUTO_INIT_DB": True,
                    "SEED_DEMO_DATA": False,
                    "BOOTSTRAP_ADMIN_USERNAME": "admin",
                    "BOOTSTRAP_ADMIN_PASSWORD": "PilotAdmin!2026",
                    "BOOTSTRAP_ADMIN_FULL_NAME": "Thomas Lawson",
                    "JOB_DOCUMENT_UPLOAD_FOLDER": str(temp_path / "uploads" / "job-documents"),
                    "CUSTOMER_LOGO_UPLOAD_FOLDER": str(temp_path / "uploads" / "customer-logos"),
                }
            )
            client = app.test_client()
            response = client.post(
                "/login",
                data={"username": "admin", "password": "PilotAdmin!2026"},
                follow_redirects=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Thomas Lawson", response.data)

            with app.app_context():
                db = get_db()
                user_count = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
                customer_count = db.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"]
            self.assertEqual(user_count, 1)
            self.assertEqual(customer_count, 0)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_accounting_user_is_blocked_from_sales_crm_pages(self):
        self.login("accounting", "Ledger!2026")

        response = self.client.get("/customers")
        detail_response = self.client.get("/customers/1")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn(b"Customer 360", detail_response.data)

    def test_login_rate_limit_blocks_repeated_failures(self):
        for _ in range(5):
            response = self.login("admin", "WrongPassword!2026")
            self.assertEqual(response.status_code, 200)

        blocked_response = self.login("admin", "ConTech!2026")

        self.assertEqual(blocked_response.status_code, 200)
        self.assertIn(b"Too many failed sign-in attempts", blocked_response.data)

    def test_public_feedback_submission_is_visible_in_inbox(self):
        response = self.client.post(
            "/pilot-feedback",
            data={
                "submitter_name": "Jordan Blake",
                "submitter_email": "jordan@example.com",
                "company_name": "North Ridge Properties",
                "role_label": "Property manager",
                "page_url": "/jobs/12/execution",
                "summary": "Execution page felt strong but invoice links were easy to miss",
                "details": "I liked the structure of the job execution page, but I needed a more obvious billing handoff cue after reviewing the change order.",
                "rating": "4",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Feedback received", response.data)

        self.login("admin", "ConTech!2026")
        inbox_response = self.client.get("/feedback/inbox")
        self.assertEqual(inbox_response.status_code, 200)
        self.assertIn(b"Jordan Blake", inbox_response.data)
        self.assertIn(b"Execution page felt strong", inbox_response.data)

        with self.app.app_context():
            submission_id = get_db().execute(
                "SELECT id FROM feedback_submissions WHERE submitter_email = ?",
                ("jordan@example.com",),
            ).fetchone()["id"]

        update_response = self.client.post(
            f"/feedback/{submission_id}/status",
            data={
                "status": "in_review",
                "internal_notes": "Queueing a more visible invoice handoff action in execution.",
            },
            follow_redirects=True,
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertIn(b"Feedback status updated", update_response.data)

        with self.app.app_context():
            updated_submission = get_db().execute(
                "SELECT status, internal_notes, reviewed_by FROM feedback_submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
        self.assertEqual(updated_submission["status"], "in_review")
        self.assertEqual(updated_submission["internal_notes"], "Queueing a more visible invoice handoff action in execution.")
        self.assertEqual(updated_submission["reviewed_by"], "Thomas Lawson")

    def test_customer_360_supports_notes_tasks_email_and_calendar(self):
        self.login("admin", "ConTech!2026")

        detail_response = self.client.get("/customers/1")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn(b"Morris Residence", detail_response.data)
        self.assertIn(b"Email hub", detail_response.data)
        self.assertIn(b"Account Contacts", detail_response.data)

        contact_response = self.client.post(
            "/customers/1/contacts",
            data={
                "full_name": "Jordan Morris",
                "role_label": "Accounts payable",
                "phone": "(555) 102-9952",
                "email": "ap-morris@example.com",
                "notes": "Handles remittance and scheduling paperwork.",
            },
            follow_redirects=True,
        )
        self.assertEqual(contact_response.status_code, 200)
        self.assertIn(b"Jordan Morris", contact_response.data)

        note_response = self.client.post(
            "/customers/1/notes",
            data={
                "activity_type": "Note",
                "title": "Customer called about permit timing",
                "details": "Asked if install can move one day later because the driveway will be blocked.",
            },
            follow_redirects=True,
        )
        self.assertEqual(note_response.status_code, 200)
        self.assertIn(b"Customer called about permit timing", note_response.data)

        task_response = self.client.post(
            "/customers/1/tasks",
            data={
                "title": "Confirm driveway access window",
                "module_name": "Customer 360",
                "owner_name": "Thomas Lawson",
                "due_date": "2026-04-04",
                "reminder_at": "2026-04-04T08:00",
                "status": "open",
                "priority": "high",
                "details": "Need final answer before dispatch locks the first delivery route.",
            },
            follow_redirects=True,
        )
        self.assertEqual(task_response.status_code, 200)
        self.assertIn(b"Confirm driveway access window", task_response.data)

        with self.app.app_context():
            task_id = get_db().execute(
                "SELECT id FROM tasks WHERE title = ? ORDER BY id DESC LIMIT 1",
                ("Confirm driveway access window",),
            ).fetchone()["id"]

        toggle_response = self.client.post(
            f"/tasks/{task_id}/toggle",
            follow_redirects=True,
        )
        self.assertEqual(toggle_response.status_code, 200)
        self.assertIn(b"Task status updated", toggle_response.data)

        email_response = self.client.post(
            "/customers/1/emails",
            data={
                "direction": "Outbound",
                "contact_email": "denise@example.com",
                "subject": "Updated install timing",
                "body": "Sent revised timing options and asked the homeowner to confirm staging access.",
                "owner_name": "Thomas Lawson",
                "status": "Sent",
                "sent_at": "2026-04-03T10:15",
                "integration_status": "Manual log",
            },
            follow_redirects=True,
        )
        self.assertEqual(email_response.status_code, 200)
        self.assertIn(b"Updated install timing", email_response.data)

        calendar_response = self.client.post(
            "/customers/1/calendar",
            data={
                "title": "Driveway access confirmation call",
                "event_type": "Call",
                "starts_at": "2026-04-04T08:30",
                "ends_at": "2026-04-04T08:45",
                "owner_name": "Thomas Lawson",
                "location": "Phone",
                "status": "Planned",
                "notes": "Confirm whether delivery truck needs a different staging window.",
                "integration_status": "Manual log",
            },
            follow_redirects=True,
        )
        self.assertEqual(calendar_response.status_code, 200)
        self.assertIn(b"Driveway access confirmation call", calendar_response.data)

        with self.app.app_context():
            updated_task = get_db().execute(
                "SELECT status FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            contact_row = get_db().execute(
                "SELECT id FROM customer_contacts WHERE customer_id = ? AND full_name = ?",
                (1, "Jordan Morris"),
            ).fetchone()
            email_row = get_db().execute(
                "SELECT id FROM email_messages WHERE subject = ?",
                ("Updated install timing",),
            ).fetchone()
            event_row = get_db().execute(
                "SELECT id FROM calendar_events WHERE title = ?",
                ("Driveway access confirmation call",),
            ).fetchone()
        self.assertEqual(updated_task["status"], "completed")
        self.assertIsNotNone(contact_row)
        self.assertIsNotNone(email_row)
        self.assertIsNotNone(event_row)

    def test_customer_portal_is_customer_scoped(self):
        response = self.portal_login("denise@example.com", "Customer!2026")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Morris Residence", response.data)
        self.assertNotIn(b"Alder Creek HOA", response.data)

        staff_response = self.client.get("/customers", follow_redirects=False)
        self.assertEqual(staff_response.status_code, 302)
        self.assertIn("/login", staff_response.headers["Location"])

        message_response = self.client.post(
            "/portal/messages",
            data={
                "subject": "Question about driveway access",
                "message_body": "Can the delivery team confirm whether a car needs to be moved before material drop?",
            },
            follow_redirects=True,
        )
        self.assertEqual(message_response.status_code, 200)
        self.assertIn(b"Message sent to the ConTech team", message_response.data)
        self.assertIn(b"Question about driveway access", message_response.data)

        self.client.post("/portal/logout", follow_redirects=True)
        self.login("admin", "ConTech!2026")
        detail_response = self.client.get("/customers/1")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn(b"Customer Portal Messages", detail_response.data)
        self.assertIn(b"Question about driveway access", detail_response.data)

    def test_staff_can_create_customer_portal_access(self):
        self.login("admin", "ConTech!2026")
        create_response = self.client.post(
            "/customers/4/portal-users",
            data={
                "full_name": "Maria Lopez",
                "email": "portal-maria@example.com",
                "password": "PortalPass!2026",
                "is_active": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertIn(b"Customer portal access created", create_response.data)
        self.assertIn(b"portal-maria@example.com", create_response.data)

        self.client.post("/logout", follow_redirects=True)
        portal_response = self.portal_login("portal-maria@example.com", "PortalPass!2026")
        self.assertEqual(portal_response.status_code, 200)
        self.assertIn(b"Lopez Residence", portal_response.data)
        self.assertNotIn(b"Morris Residence", portal_response.data)

    def test_customer_invite_profile_setup_populates_quote_header(self):
        self.login("admin", "ConTech!2026")
        create_response = self.client.post(
            "/customers/4/portal-users",
            data={
                "full_name": "Maria Lopez",
                "email": "invite-maria@example.com",
                "role_label": "Owner",
                "phone": "(555) 908-3308",
            },
            follow_redirects=True,
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertIn(b"Customer portal invite created", create_response.data)
        match = re.search(rb'http://localhost(/portal/invite/[^"]+)', create_response.data)
        self.assertIsNotNone(match)
        invite_path = match.group(1).decode("utf-8")

        setup_response = self.client.post(
            invite_path,
            data={
                "full_name": "Maria Lopez",
                "email": "invite-maria@example.com",
                "role_label": "Owner",
                "phone": "(555) 908-3308",
                "company_name": "Lopez Residence LLC",
                "company_address": "17 Harbor Lane, Elk Grove, CA",
                "password": "CustomerSetup!2026",
                "confirm_password": "CustomerSetup!2026",
                "company_logo": (io.BytesIO(b"customer logo bytes"), "lopez-logo.png"),
            },
            follow_redirects=True,
        )
        self.assertEqual(setup_response.status_code, 200)
        self.assertIn(b"Your customer portal profile is ready", setup_response.data)
        self.assertIn(b"Lopez Residence LLC", setup_response.data)

        with self.app.app_context():
            db = get_db()
            customer = db.execute(
                "SELECT company_name, company_address, company_logo_filename FROM customers WHERE id = ?",
                (4,),
            ).fetchone()
            portal_user = db.execute(
                """
                SELECT is_active, invite_status, invite_token_hash, profile_completed_at, role_label, phone
                FROM customer_portal_users
                WHERE email = ?
                """,
                ("invite-maria@example.com",),
            ).fetchone()
        self.assertEqual(customer["company_name"], "Lopez Residence LLC")
        self.assertEqual(customer["company_address"], "17 Harbor Lane, Elk Grove, CA")
        self.assertTrue(customer["company_logo_filename"].endswith(".png"))
        self.assertTrue((Path(self.app.config["CUSTOMER_LOGO_UPLOAD_FOLDER"]) / customer["company_logo_filename"]).exists())
        self.assertEqual(portal_user["is_active"], 1)
        self.assertEqual(portal_user["invite_status"], "accepted")
        self.assertIsNone(portal_user["invite_token_hash"])
        self.assertIsNotNone(portal_user["profile_completed_at"])
        self.assertEqual(portal_user["role_label"], "Owner")
        self.assertEqual(portal_user["phone"], "(555) 908-3308")

        self.client.post("/portal/logout", follow_redirects=True)
        self.login("admin", "ConTech!2026")
        quotes_response = self.client.get("/quotes")
        self.assertEqual(quotes_response.status_code, 200)
        self.assertIn(b"Header: Lopez Residence LLC", quotes_response.data)

    def test_itemized_quote_builder_saves_lines_and_rollups(self):
        self.login("admin", "ConTech!2026")
        builder_page = self.client.get("/quotes/new")
        self.assertEqual(builder_page.status_code, 200)
        self.assertIn(b"Line Item Builder", builder_page.data)

        response = self.client.post(
            "/quotes/new",
            data={
                "opportunity_id": "1",
                "customer_id": "1",
                "quote_number": "Q-LINE-1001",
                "option_name": "Itemized roof package",
                "description": "Paradigm-style itemized roof package with tax breakout",
                "tax_rate_pct": "8.25",
                "deposit_required": "2000",
                "deposit_received": "0",
                "status": "Draft",
                "signed_date": "",
                "issue_date": "2026-04-10",
                "expiration_date": "2026-04-20",
                "line_inventory_item_id": ["", "1"],
                "line_sku": ["LAB-ROOF", ""],
                "line_item_name": ["Roof tear-off labor", ""],
                "line_description": ["Remove existing shingles and prep deck", "Roof field material package"],
                "line_quantity": ["1", "10"],
                "line_unit_label": ["job", "square"],
                "line_unit_cost": ["2500", "94"],
                "line_unit_price": ["3900", "134"],
                "line_discount_pct": ["0", "5"],
                "line_taxable": ["0", "1"],
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Q-LINE-1001", response.data)

        with self.app.app_context():
            db = get_db()
            quote = db.execute(
                """
                SELECT amount, estimated_cost, tax_total, grand_total, discount_total,
                       profit_amount, line_item_count, target_margin_pct
                FROM quotes
                WHERE quote_number = ?
                """,
                ("Q-LINE-1001",),
            ).fetchone()
            quote_id = db.execute(
                "SELECT id FROM quotes WHERE quote_number = ?",
                ("Q-LINE-1001",),
            ).fetchone()["id"]
            lines = db.execute(
                """
                SELECT item_name, taxable, line_subtotal, line_tax, line_total, line_cost, profit_amount
                FROM quote_line_items
                WHERE quote_id = ?
                ORDER BY sort_order
                """,
                (quote_id,),
            ).fetchall()

        self.assertAlmostEqual(quote["amount"], 5173.00, places=2)
        self.assertAlmostEqual(quote["estimated_cost"], 3440.00, places=2)
        self.assertAlmostEqual(quote["tax_total"], 105.02, places=2)
        self.assertAlmostEqual(quote["grand_total"], 5278.02, places=2)
        self.assertAlmostEqual(quote["discount_total"], 67.00, places=2)
        self.assertAlmostEqual(quote["profit_amount"], 1733.00, places=2)
        self.assertEqual(quote["line_item_count"], 2)
        self.assertAlmostEqual(quote["target_margin_pct"], 33.5, places=1)
        self.assertEqual(lines[0]["item_name"], "Roof tear-off labor")
        self.assertEqual(lines[0]["taxable"], 0)
        self.assertAlmostEqual(lines[1]["line_tax"], 105.02, places=2)

        contract_page = self.client.get(f"/quotes/{quote_id}/contract")
        edit_page = self.client.get(f"/quotes/{quote_id}/edit")
        self.assertEqual(edit_page.status_code, 200)
        self.assertIn(b"Line Item Builder", edit_page.data)
        self.assertEqual(contract_page.status_code, 200)
        self.assertIn(b"Roof tear-off labor", contract_page.data)
        self.assertIn(b"Grand total", contract_page.data)

    def test_customer_lead_opportunity_quote_job_invoice_workflow(self):
        self.login("admin", "ConTech!2026")

        customer_response = self.client.post(
            "/customers/new",
            data={
                "name": "North Ridge Apartments",
                "segment": "Commercial",
                "primary_contact": "Chris Dalton",
                "phone": "(555) 221-0098",
                "email": "cdalton@northridge.example",
                "service_address": "880 North Ridge Blvd, Sacramento, CA",
                "status": "active",
                "trade_mix": "Roofing, siding",
                "notes": "Large multifamily prospect",
                "is_repeat": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(customer_response.status_code, 200)
        self.assertIn(b"North Ridge Apartments", customer_response.data)

        with self.app.app_context():
            customer_id = get_db().execute(
                "SELECT id FROM customers WHERE name = ?",
                ("North Ridge Apartments",),
            ).fetchone()["id"]
            primary_contact = get_db().execute(
                "SELECT full_name, email FROM customer_contacts WHERE customer_id = ? AND is_primary = 1",
                (customer_id,),
            ).fetchone()
        self.assertEqual(primary_contact["full_name"], "Chris Dalton")
        self.assertEqual(primary_contact["email"], "cdalton@northridge.example")

        lead_response = self.client.post(
            "/leads/new",
            data={
                "customer_id": str(customer_id),
                "source": "Website leads",
                "trade_interest": "Commercial roof replacement",
                "stage": "Inspection",
                "assigned_rep": "Ramon",
                "inspection_date": "2026-04-10",
                "estimated_value": "182500",
                "is_commercial": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(lead_response.status_code, 200)
        self.assertIn(b"Commercial roof replacement", lead_response.data)

        with self.app.app_context():
            lead_id = get_db().execute(
                "SELECT id FROM leads WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
                (customer_id,),
            ).fetchone()["id"]

        opportunity_response = self.client.post(
            "/opportunities/new",
            data={
                "lead_id": str(lead_id),
                "customer_id": str(customer_id),
                "name": "North Ridge Apartments",
                "subtitle": "Commercial roof replacement / phased work",
                "stage": "Quoted",
                "close_date": "2026-04-18",
                "value": "182500",
                "priority": "85",
                "trade_mix": "Roofing",
                "rep": "Ramon",
            },
            follow_redirects=True,
        )
        self.assertEqual(opportunity_response.status_code, 200)
        self.assertIn(b"North Ridge Apartments", opportunity_response.data)

        with self.app.app_context():
            opportunity_id = get_db().execute(
                "SELECT id FROM opportunities WHERE lead_id = ?",
                (lead_id,),
            ).fetchone()["id"]

        edit_response = self.client.post(
            f"/opportunities/{opportunity_id}/edit",
            data={
                "lead_id": str(lead_id),
                "customer_id": str(customer_id),
                "name": "North Ridge Apartments - Phase 1",
                "subtitle": "Commercial roof replacement / building A first",
                "stage": "Negotiation",
                "close_date": "2026-04-20",
                "value": "176000",
                "priority": "90",
                "trade_mix": "Roofing",
                "rep": "Ramon",
            },
            follow_redirects=True,
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertIn(b"Phase 1", edit_response.data)

        quote_response = self.client.post(
            "/quotes/new",
            data={
                "opportunity_id": str(opportunity_id),
                "customer_id": str(customer_id),
                "quote_number": "Q-TEST-1001",
                "option_name": "Phase 1 contract",
                "description": "Commercial roof replacement / building A first",
                "amount": "176000",
                "estimated_cost": "118800",
                "deposit_required": "44000",
                "deposit_received": "0",
                "status": "Pending Signature",
                "signed_date": "",
                "issue_date": "2026-04-08",
                "expiration_date": "2026-04-20",
            },
            follow_redirects=True,
        )
        self.assertEqual(quote_response.status_code, 200)
        self.assertIn(b"Q-TEST-1001", quote_response.data)

        with self.app.app_context():
            quote_id = get_db().execute(
                "SELECT id FROM quotes WHERE quote_number = ?",
                ("Q-TEST-1001",),
            ).fetchone()["id"]

        contract_response = self.client.post(
            f"/quotes/{quote_id}/contract",
            data={
                "signed_date": "2026-04-12",
                "deposit_required": "44000",
                "deposit_received": "44000",
            },
            follow_redirects=True,
        )
        self.assertEqual(contract_response.status_code, 200)
        self.assertIn(b"Contract execution details updated", contract_response.data)

        job_response = self.client.post(
            "/jobs/new",
            data={
                "opportunity_id": str(opportunity_id),
                "quote_id": str(quote_id),
                "customer_id": str(customer_id),
                "name": "North Ridge Apartments - Phase 1",
                "scope": "Commercial roof replacement / building A first",
                "status": "Scheduled",
                "scheduled_start": "2026-04-22",
                "crew_name": "Crew North",
                "committed_revenue": "176000",
            },
            follow_redirects=True,
        )
        self.assertEqual(job_response.status_code, 200)
        self.assertIn(b"North Ridge Apartments - Phase 1", job_response.data)

        with self.app.app_context():
            job_row = get_db().execute(
                "SELECT id, status FROM jobs WHERE quote_id = ?",
                (quote_id,),
            ).fetchone()
            job_id = job_row["id"]
            updated_quote = get_db().execute(
                "SELECT status, signed_date, deposit_received FROM quotes WHERE id = ?",
                (quote_id,),
            ).fetchone()
            updated_opportunity = get_db().execute(
                "SELECT stage FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
        self.assertEqual(updated_quote["status"], "Approved")
        self.assertEqual(updated_quote["signed_date"], "2026-04-12")
        self.assertEqual(updated_quote["deposit_received"], 44000)
        self.assertEqual(updated_opportunity["stage"], "Won / Ready")

        execution_page = self.client.get(f"/jobs/{job_id}/execution")
        self.assertEqual(execution_page.status_code, 200)
        self.assertIn(b"Job Control Center", execution_page.data)
        self.assertIn(b"ERP job flow", execution_page.data)
        self.assertIn(b"Job build sheet", execution_page.data)
        self.assertIn(b"Change orders", execution_page.data)

        change_order_response = self.client.post(
            f"/jobs/{job_id}/change-orders",
            data={
                "change_number": "CO-TEST-1001",
                "title": "Tapered insulation adjustment",
                "description": "Field conditions require tapered insulation at the north parapet to correct ponding.",
                "status": "Approved",
                "requested_date": "2026-04-22",
                "approved_date": "2026-04-23",
                "amount": "13500",
                "cost_impact": "8200",
                "schedule_days": "2",
                "owner_name": "Thomas Lawson",
                "is_billable": "on",
                "notes": "Approved during field walk with ownership rep.",
            },
            follow_redirects=True,
        )
        self.assertEqual(change_order_response.status_code, 200)
        self.assertIn(b"CO-TEST-1001", change_order_response.data)

        with self.app.app_context():
            change_order_id = get_db().execute(
                "SELECT id FROM change_orders WHERE change_number = ?",
                ("CO-TEST-1001",),
            ).fetchone()["id"]

        change_order_edit_response = self.client.post(
            f"/change-orders/{change_order_id}/edit",
            data={
                "change_number": "CO-TEST-1001",
                "title": "Tapered insulation adjustment",
                "description": "Field conditions require tapered insulation at the north parapet and west drain line to correct ponding.",
                "status": "Approved",
                "requested_date": "2026-04-22",
                "approved_date": "2026-04-23",
                "amount": "14800",
                "cost_impact": "9100",
                "schedule_days": "3",
                "owner_name": "Thomas Lawson",
                "is_billable": "on",
                "notes": "Board and PM approved the revised insulation scope after field review.",
                "change_summary": "Expanded approved scope after PM walkthrough",
            },
            follow_redirects=True,
        )
        self.assertEqual(change_order_edit_response.status_code, 200)
        self.assertIn(b"Change order updated", change_order_edit_response.data)

        document_response = self.client.post(
            f"/jobs/{job_id}/documents",
            data={
                "record_type": "Photo",
                "title": "North parapet ponding condition",
                "file_reference": "photos/north-ridge/parapet-ponding-01.jpg",
                "captured_at": "2026-04-22T09:15",
                "owner_name": "Thomas Lawson",
                "status": "Logged",
                "notes": "Photo set captured during tear-off review for the added insulation scope.",
                "upload_file": (io.BytesIO(b"initial field image bytes"), "ponding-photo.jpg"),
            },
            follow_redirects=True,
        )
        self.assertEqual(document_response.status_code, 200)
        self.assertIn(b"North parapet ponding condition", document_response.data)

        customer_360_response = self.client.get(f"/customers/{customer_id}")
        self.assertEqual(customer_360_response.status_code, 200)
        self.assertIn(b"CO-TEST-1001", customer_360_response.data)
        self.assertIn(b"North parapet ponding condition", customer_360_response.data)

        with self.app.app_context():
            change_order_row = get_db().execute(
                "SELECT amount, schedule_days FROM change_orders WHERE id = ?",
                (change_order_id,),
            ).fetchone()
            change_order_version = get_db().execute(
                """
                SELECT version_number, change_summary
                FROM change_order_versions
                WHERE change_order_id = ?
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (change_order_id,),
            ).fetchone()
            document_id = get_db().execute(
                "SELECT id FROM job_documents WHERE job_id = ? ORDER BY id DESC LIMIT 1",
                (job_id,),
            ).fetchone()["id"]
            document_row = get_db().execute(
                "SELECT stored_file_name, original_filename FROM job_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        self.assertEqual(change_order_row["amount"], 14800)
        self.assertEqual(change_order_row["schedule_days"], 3)
        self.assertEqual(change_order_version["version_number"], 2)
        self.assertEqual(change_order_version["change_summary"], "Expanded approved scope after PM walkthrough")
        self.assertEqual(document_row["original_filename"], "ponding-photo.jpg")
        self.assertIsNotNone(document_row["stored_file_name"])
        self.assertTrue((Path(self.app.config["JOB_DOCUMENT_UPLOAD_FOLDER"]) / document_row["stored_file_name"]).exists())

        document_download_response = self.client.get(f"/job-documents/{document_id}/file")
        self.assertEqual(document_download_response.status_code, 200)
        self.assertEqual(document_download_response.data, b"initial field image bytes")
        document_download_response.close()

        document_edit_response = self.client.post(
            f"/job-documents/{document_id}/edit",
            data={
                "record_type": "Inspection",
                "title": "North parapet ponding inspection log",
                "file_reference": "inspections/north-ridge/parapet-log.txt",
                "captured_at": "2026-04-22T11:30",
                "owner_name": "Thomas Lawson",
                "status": "Pending Review",
                "notes": "Updated inspection narrative with drain-line observations.",
                "upload_file": (io.BytesIO(b"updated field image bytes"), "ponding-photo-rev2.jpg"),
            },
            follow_redirects=True,
        )
        self.assertEqual(document_edit_response.status_code, 200)
        self.assertIn(b"Field record updated", document_edit_response.data)

        with self.app.app_context():
            updated_document_row = get_db().execute(
                """
                SELECT title, record_type, status, stored_file_name, original_filename, file_reference
                FROM job_documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        self.assertEqual(updated_document_row["title"], "North parapet ponding inspection log")
        self.assertEqual(updated_document_row["record_type"], "Inspection")
        self.assertEqual(updated_document_row["status"], "Pending Review")
        self.assertEqual(updated_document_row["original_filename"], "ponding-photo-rev2.jpg")
        self.assertEqual(updated_document_row["file_reference"], "inspections/north-ridge/parapet-log.txt")
        self.assertTrue((Path(self.app.config["JOB_DOCUMENT_UPLOAD_FOLDER"]) / updated_document_row["stored_file_name"]).exists())

        updated_download_response = self.client.get(f"/job-documents/{document_id}/file")
        self.assertEqual(updated_download_response.status_code, 200)
        self.assertEqual(updated_download_response.data, b"updated field image bytes")
        updated_download_response.close()

        costing_response = self.client.post(
            f"/jobs/{job_id}/costs",
            data={
                "vendor_id": "1",
                "cost_code": "Material",
                "source_type": "Material",
                "description": "Starter cap and vent package",
                "quantity": "1",
                "unit_cost": "1850",
                "cost_date": "2026-04-22",
                "status": "Posted",
                "notes": "Initial production material package charged to the job.",
            },
            follow_redirects=True,
        )
        self.assertEqual(costing_response.status_code, 200)
        self.assertIn(b"Job cost entry added", costing_response.data)

        with self.app.app_context():
            cost_entry_id = get_db().execute(
                "SELECT id FROM job_cost_entries WHERE job_id = ? ORDER BY id DESC LIMIT 1",
                (job_id,),
            ).fetchone()["id"]

        inventory_response = self.client.post(
            "/inventory/new",
            data={
                "vendor_id": "1",
                "sku": "TEST-ROOF-01",
                "item_name": "Test architectural shingles",
                "category": "Roofing",
                "stock_on_hand": "12",
                "unit_cost": "92",
                "unit_price": "137",
                "status": "Healthy",
            },
            follow_redirects=True,
        )
        self.assertEqual(inventory_response.status_code, 200)
        self.assertIn(b"Test architectural shingles", inventory_response.data)

        with self.app.app_context():
            inventory_item_id = get_db().execute(
                "SELECT id FROM inventory_items WHERE sku = ?",
                ("TEST-ROOF-01",),
            ).fetchone()["id"]

        material_response = self.client.post(
            f"/jobs/{job_id}/materials",
            data={
                "inventory_item_id": str(inventory_item_id),
                "requested_qty": "18",
                "notes": "Phase one roof package",
                "purchase_priority": "high",
                "auto_purchase": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(material_response.status_code, 200)
        self.assertIn(b"still needs to be sourced", material_response.data)

        with self.app.app_context():
            reserved_item = get_db().execute(
                "SELECT reserved_qty FROM inventory_items WHERE id = ?",
                (inventory_item_id,),
            ).fetchone()
            material_row = get_db().execute(
                """
                SELECT id, reserved_qty, shortage_qty, status
                FROM job_materials
                WHERE job_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            material_job = get_db().execute(
                "SELECT status FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            purchase_request = get_db().execute(
                """
                SELECT id, status, owner_name, needed_by, job_id, job_material_id, inventory_item_id, requested_qty
                FROM purchase_requests
                WHERE job_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        self.assertEqual(reserved_item["reserved_qty"], 12)
        self.assertEqual(material_row["reserved_qty"], 12)
        self.assertEqual(material_row["shortage_qty"], 6)
        self.assertEqual(material_row["status"], "Partial")
        self.assertEqual(material_job["status"], "Materials reserved")
        self.assertIsNotNone(purchase_request)
        self.assertEqual(purchase_request["status"], "Open")
        self.assertEqual(purchase_request["owner_name"], "Thomas Lawson")
        self.assertEqual(purchase_request["needed_by"], "2026-04-22")
        self.assertEqual(purchase_request["job_id"], job_id)
        self.assertEqual(purchase_request["inventory_item_id"], inventory_item_id)
        self.assertEqual(purchase_request["requested_qty"], 6)

        purchase_edit_response = self.client.post(
            f"/purchasing/{purchase_request['id']}/edit",
            data={
                "job_id": str(job_id),
                "job_material_id": str(material_row["id"]),
                "inventory_item_id": str(inventory_item_id),
                "vendor_id": "1",
                "title": "North Ridge Apartments - Phase 1 shortage / TEST-ROOF-01",
                "details": "Test architectural shingles short by 6 squares for phase one start.",
                "requested_qty": "6",
                "ordered_qty": "6",
                "received_qty": "0",
                "priority": "high",
                "status": "Ordered",
                "owner_name": "Thomas Lawson",
                "needed_by": "2026-04-22",
                "eta_date": "2026-04-21",
                "vendor_notes": "Vendor confirmed pickup by 6:30 AM on install morning.",
            },
            follow_redirects=True,
        )
        self.assertEqual(purchase_edit_response.status_code, 200)
        self.assertIn(b"Purchase request updated", purchase_edit_response.data)

        delivery_response = self.client.post(
            "/dispatch/new",
            data={
                "job_id": str(job_id),
                "route_name": "Route 09 / North Ridge",
                "truck_name": "Truck 9",
                "eta": "2026-04-21T06:45",
                "status": "Scheduled",
                "load_percent": "85",
                "notes": "Deliver shingles and accessory bundle for phase one start.",
            },
            follow_redirects=True,
        )
        self.assertEqual(delivery_response.status_code, 200)
        self.assertIn(b"Route 09 / North Ridge", delivery_response.data)

        with self.app.app_context():
            delivery_id = get_db().execute(
                "SELECT id FROM deliveries WHERE job_id = ? ORDER BY id DESC LIMIT 1",
                (job_id,),
            ).fetchone()["id"]
            delivery_job = get_db().execute(
                "SELECT status FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        self.assertEqual(delivery_job["status"], "Delivery pending")

        delivered_response = self.client.post(
            f"/dispatch/{delivery_id}/edit",
            data={
                "job_id": str(job_id),
                "route_name": "Route 09 / North Ridge",
                "truck_name": "Truck 9",
                "eta": "2026-04-21T06:45",
                "status": "Delivered",
                "load_percent": "100",
                "notes": "Material delivered on site before crew arrival.",
            },
            follow_redirects=True,
        )
        self.assertEqual(delivered_response.status_code, 200)
        self.assertIn(b"Delivery updated", delivered_response.data)

        with self.app.app_context():
            delivered_job = get_db().execute(
                "SELECT status FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        self.assertEqual(delivered_job["status"], "Ready for production")

        invoice_response = self.client.post(
            "/invoices/new",
            data={
                "quote_id": str(quote_id),
                "change_order_id": "",
                "customer_id": str(customer_id),
                "job_id": str(job_id),
                "invoice_number": "INV-TEST-1001",
                "billing_type": "Progress",
                "application_number": "APP-01",
                "status": "Issued",
                "amount": "176000",
                "issued_date": "2026-04-23",
                "due_date": "2026-05-01",
                "billing_period_start": "2026-04-22",
                "billing_period_end": "2026-04-30",
                "retainage_pct": "10",
                "retainage_held": "17600",
                "remaining_balance": "176000",
            },
            follow_redirects=True,
        )
        self.assertEqual(invoice_response.status_code, 200)
        self.assertIn(b"INV-TEST-1001", invoice_response.data)

        with self.app.app_context():
            invoice_id = get_db().execute(
                "SELECT id FROM invoices WHERE invoice_number = ?",
                ("INV-TEST-1001",),
            ).fetchone()["id"]

        change_invoice_response = self.client.post(
            "/invoices/new",
            data={
                "quote_id": str(quote_id),
                "change_order_id": str(change_order_id),
                "customer_id": str(customer_id),
                "job_id": str(job_id),
                "invoice_number": "INV-TEST-1002",
                "billing_type": "Change Order",
                "application_number": "CO-APP-01",
                "status": "Issued",
                "amount": "14800",
                "issued_date": "2026-04-24",
                "due_date": "2026-05-02",
                "billing_period_start": "2026-04-22",
                "billing_period_end": "2026-04-23",
                "retainage_pct": "0",
                "retainage_held": "0",
                "remaining_balance": "14800",
            },
            follow_redirects=True,
        )
        self.assertEqual(change_invoice_response.status_code, 200)
        self.assertIn(b"INV-TEST-1002", change_invoice_response.data)

        payment_response = self.client.post(
            f"/invoices/{invoice_id}/payment",
            data={
                "payment_amount": "76000",
                "payment_date": "2026-04-24",
                "payment_method": "Wire",
                "deposit_account_id": "1",
                "reference_number": "WIRE-76000-A",
                "notes": "Commercial draw received and posted to operating cash.",
            },
            follow_redirects=True,
        )
        self.assertEqual(payment_response.status_code, 200)
        self.assertIn(b"Payment recorded", payment_response.data)

        with self.app.app_context():
            updated_invoice = get_db().execute(
                """
                SELECT remaining_balance, status, billing_type, application_number,
                       billing_period_start, billing_period_end, retainage_pct, retainage_held
                FROM invoices
                WHERE id = ?
                """,
                (invoice_id,),
            ).fetchone()
            change_invoice = get_db().execute(
                "SELECT change_order_id, billing_type, remaining_balance FROM invoices WHERE invoice_number = ?",
                ("INV-TEST-1002",),
            ).fetchone()
            payment_row = get_db().execute(
                """
                SELECT payment_amount, payment_method, reference_number, deposit_account_id
                FROM invoice_payments
                WHERE invoice_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (invoice_id,),
            ).fetchone()
            updated_change_order = get_db().execute(
                "SELECT status, amount FROM change_orders WHERE id = ?",
                (change_order_id,),
            ).fetchone()
            change_invoice_id = get_db().execute(
                "SELECT id FROM invoices WHERE invoice_number = ?",
                ("INV-TEST-1002",),
            ).fetchone()["id"]
        self.assertEqual(updated_invoice["remaining_balance"], 100000)
        self.assertEqual(updated_invoice["status"], "Partial Paid")
        self.assertEqual(updated_invoice["billing_type"], "Progress")
        self.assertEqual(updated_invoice["application_number"], "APP-01")
        self.assertEqual(updated_invoice["billing_period_start"], "2026-04-22")
        self.assertEqual(updated_invoice["billing_period_end"], "2026-04-30")
        self.assertEqual(updated_invoice["retainage_pct"], 10)
        self.assertEqual(updated_invoice["retainage_held"], 17600)
        self.assertEqual(change_invoice["change_order_id"], change_order_id)
        self.assertEqual(change_invoice["billing_type"], "Change Order")
        self.assertEqual(change_invoice["remaining_balance"], 14800)
        self.assertEqual(payment_row["payment_amount"], 76000)
        self.assertEqual(payment_row["payment_method"], "Wire")
        self.assertEqual(payment_row["reference_number"], "WIRE-76000-A")
        self.assertEqual(payment_row["deposit_account_id"], 1)
        self.assertEqual(updated_change_order["status"], "Invoiced")
        self.assertEqual(updated_change_order["amount"], 14800)

        blocked_delete = self.client.post(
            f"/customers/{customer_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(blocked_delete.status_code, 200)
        self.assertIn(b"cannot be deleted", blocked_delete.data)

        blocked_job_delete = self.client.post(
            f"/jobs/{job_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(blocked_job_delete.status_code, 200)
        self.assertIn(b"cannot be deleted", blocked_job_delete.data)

        blocked_inventory_delete = self.client.post(
            f"/inventory/{inventory_item_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(blocked_inventory_delete.status_code, 200)
        self.assertIn(b"cannot be deleted", blocked_inventory_delete.data)

        blocked_quote_delete = self.client.post(
            f"/quotes/{quote_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(blocked_quote_delete.status_code, 200)
        self.assertIn(b"cannot be deleted", blocked_quote_delete.data)

        self.client.post(f"/invoices/{invoice_id}/delete", follow_redirects=True)
        self.client.post(f"/invoices/{change_invoice_id}/delete", follow_redirects=True)
        self.client.post(f"/job-documents/{document_id}/delete", follow_redirects=True)
        self.client.post(f"/change-orders/{change_order_id}/delete", follow_redirects=True)
        self.client.post(f"/dispatch/{delivery_id}/delete", follow_redirects=True)
        self.client.post(f"/purchasing/{purchase_request['id']}/delete", follow_redirects=True)
        with self.app.app_context():
            material_id = get_db().execute(
                "SELECT id FROM job_materials WHERE job_id = ? ORDER BY id DESC LIMIT 1",
                (job_id,),
            ).fetchone()["id"]
        self.client.post(f"/job-materials/{material_id}/delete", follow_redirects=True)
        self.client.post(f"/job-costs/{cost_entry_id}/delete", follow_redirects=True)
        self.client.post(f"/inventory/{inventory_item_id}/delete", follow_redirects=True)
        self.client.post(f"/jobs/{job_id}/delete", follow_redirects=True)
        self.client.post(f"/quotes/{quote_id}/delete", follow_redirects=True)
        self.client.post(f"/opportunities/{opportunity_id}/delete", follow_redirects=True)
        self.client.post(f"/leads/{lead_id}/delete", follow_redirects=True)
        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM activity_feed WHERE customer_id = ?", (customer_id,))
            db.execute("DELETE FROM tasks WHERE customer_id = ?", (customer_id,))
            db.execute("DELETE FROM email_messages WHERE customer_id = ?", (customer_id,))
            db.execute("DELETE FROM calendar_events WHERE customer_id = ?", (customer_id,))
            db.execute("DELETE FROM customer_contacts WHERE customer_id = ?", (customer_id,))
            db.commit()
        delete_customer = self.client.post(f"/customers/{customer_id}/delete", follow_redirects=True)

        self.assertEqual(delete_customer.status_code, 200)
        with self.app.app_context():
            deleted_customer = get_db().execute(
                "SELECT id FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
            deleted_inventory = get_db().execute(
                "SELECT id FROM inventory_items WHERE id = ?",
                (inventory_item_id,),
            ).fetchone()
        self.assertIsNone(deleted_customer)
        self.assertIsNone(deleted_inventory)


if __name__ == "__main__":
    unittest.main()
