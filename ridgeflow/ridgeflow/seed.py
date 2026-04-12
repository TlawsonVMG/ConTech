from datetime import datetime

from .services.pdf_pipeline import analyze_blueprint_bytes, record_analysis_corrections, record_blueprint_analysis
from .services.takeoff import create_takeoff_run


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _seed_pdf_bytes(text):
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        + f"4 0 obj << /Length {len(escaped_text) + 12} >> stream\nBT ({escaped_text}) Tj ET\nendstream\nendobj\n".encode("latin-1")
        + b"trailer << /Root 1 0 R >>\n%%EOF"
    )


def seed_demo_data(db):
    now = _now()

    team_id = db.execute(
        "INSERT INTO teams (name, slug, created_at) VALUES (?, ?, ?)",
        ("RidgeFlow Demo Team", "ridgeflow-demo", now),
    ).lastrowid

    users = [
        ("Ava Cole", "ava@ridgeflow.local", "Estimator", "AC"),
        ("Jordan Reed", "jordan@ridgeflow.local", "Project Manager", "JR"),
        ("Luis Benton", "luis@ridgeflow.local", "Operations", "LB"),
    ]
    user_ids = []
    for full_name, email, role_name, initials in users:
        user_id = db.execute(
            """
            INSERT INTO users (team_id, full_name, email, role_name, avatar_initials, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (team_id, full_name, email, role_name, initials, now),
        ).lastrowid
        user_ids.append(user_id)

    projects = [
        {
            "name": "West Ridge Apartments",
            "client_name": "West Ridge Property Group",
            "project_type": "Bid",
            "roof_system": "TPO",
            "address": "1450 Canyon View Dr, Sacramento, CA",
            "status": "Estimator Review",
            "estimator_name": "Ava Cole",
            "bid_date": "2026-04-18",
            "due_date": "2026-04-16",
            "notes": "Large low-slope reroof with parapet coping and staged tenant access.",
        },
        {
            "name": "Canyon Market Retrofit",
            "client_name": "Canyon Market LLC",
            "project_type": "Production Support",
            "roof_system": "Standing Seam Metal",
            "address": "804 Grant Ave, Roseville, CA",
            "status": "Approved",
            "estimator_name": "Ava Cole",
            "bid_date": "2026-04-12",
            "due_date": "2026-04-14",
            "notes": "Panel replacement package and flashing review before procurement.",
        },
        {
            "name": "Maple Street Residence",
            "client_name": "Rachel Howard",
            "project_type": "Bid",
            "roof_system": "Architectural Shingles",
            "address": "2811 Maple St, Folsom, CA",
            "status": "Blueprint Review",
            "estimator_name": "Ava Cole",
            "bid_date": "2026-04-20",
            "due_date": "2026-04-19",
            "notes": "Residential reroof with ridge vent, starter, and ice barrier.",
        },
    ]

    project_ids = []
    for project in projects:
        project_id = db.execute(
            """
            INSERT INTO projects (
                team_id, name, client_name, project_type, roof_system, address, status,
                estimator_name, bid_date, due_date, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team_id,
                project["name"],
                project["client_name"],
                project["project_type"],
                project["roof_system"],
                project["address"],
                project["status"],
                project["estimator_name"],
                project["bid_date"],
                project["due_date"],
                project["notes"],
                now,
                now,
            ),
        ).lastrowid
        project_ids.append(project_id)

    blueprint_ids = []
    blueprint_analysis_ids = []
    blueprints = [
        (project_ids[0], "WRA_Roof_Set_v3.pdf", "Permit", "v3", "Ready for AI", 24, 18_400_000, "Roof plan, details, and edge metal sheets."),
        (project_ids[1], "Canyon_Market_Panels_v2.pdf", "Issued for Pricing", "v2", "Ready for AI", 12, 9_700_000, "Metal panel elevations and trim schedules."),
        (project_ids[2], "Maple_Residence_Reroof_v1.pdf", "Bid Set", "v1", "Uploaded", 8, 4_100_000, "Basic plan set awaiting AI run."),
    ]
    for row in blueprints:
        blueprint_id = db.execute(
            """
            INSERT INTO blueprints (
                project_id, stored_filename, original_filename, phase_label, version_label,
                status, page_count, file_size_bytes, notes, uploaded_at
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*row, now),
        ).lastrowid
        blueprint_ids.append(blueprint_id)

    seeded_pdf_text = [
        "R1.1 Roof Plan TPO membrane roof area 184 squares perimeter 610 lf parapet detail and drain notes.",
        "R2.1 Standing seam metal roof plan roof area 9600 sq ft perimeter 422 lf ridge 168 lf valley 44 lf.",
        "R1.0 Architectural shingle roof plan roof area 32 squares eave 116 lf ridge 52 lf starter strip notes.",
    ]
    for blueprint_id, project, text in zip(blueprint_ids, projects, seeded_pdf_text):
        analysis = analyze_blueprint_bytes(
            _seed_pdf_bytes(text),
            roof_system_hint=project["roof_system"],
            original_filename=f"seed-{blueprint_id}.pdf",
        )
        blueprint_analysis_ids.append(record_blueprint_analysis(db, blueprint_id, analysis))

    record_analysis_corrections(
        db,
        blueprint_id=blueprint_ids[0],
        blueprint_analysis_id=blueprint_analysis_ids[0],
        corrected_by_name="Ava Cole",
        values={
            "roof_area_squares": 188.0,
            "parapet_feet": 610.0,
            "flashing_types": ["edge metal", "coping", "counterflashing"],
        },
        notes="Permit revision confirmed parapet and edge conditions.",
    )
    record_analysis_corrections(
        db,
        blueprint_id=blueprint_ids[1],
        blueprint_analysis_id=blueprint_analysis_ids[1],
        corrected_by_name="Ava Cole",
        values={
            "valley_feet": 52.0,
            "ridge_feet": 172.0,
        },
        notes="Trim schedule updated after estimator review.",
    )

    create_takeoff_run(
        db=db,
        project_id=project_ids[0],
        blueprint_id=blueprint_ids[0],
        blueprint_analysis_id=blueprint_analysis_ids[0],
        system_type="TPO",
        roof_area_squares=184,
        waste_pct=6,
        perimeter_feet=610,
        ridge_feet=0,
        valley_feet=0,
        eave_feet=610,
        ai_model="Blueprint Vision v1",
        status="Review Required",
        source_mode="blueprint-analysis",
    )
    create_takeoff_run(
        db=db,
        project_id=project_ids[1],
        blueprint_id=blueprint_ids[1],
        blueprint_analysis_id=blueprint_analysis_ids[1],
        system_type="Standing Seam Metal",
        roof_area_squares=96,
        waste_pct=9,
        perimeter_feet=422,
        ridge_feet=168,
        valley_feet=44,
        eave_feet=211,
        ai_model="Blueprint Vision v1",
        status="Approved",
        source_mode="blueprint-analysis",
    )

    tasks = [
        (project_ids[0], user_ids[0], "Review parapet coping takeoff before pricing release", "in_progress", "high", "2026-04-13", "Needs detail sheet confirmation."),
        (project_ids[0], user_ids[1], "Confirm tenant access notes with client", "todo", "medium", "2026-04-15", "Operations handoff blocker."),
        (project_ids[1], user_ids[2], "Cross-check trim coil quantities with supplier pack sizes", "done", "medium", "2026-04-11", "Completed during approval review."),
        (project_ids[2], user_ids[0], "Upload structural notes addendum", "blocked", "high", "2026-04-14", "Waiting on revised PDF from client."),
    ]
    for task in tasks:
        db.execute(
            """
            INSERT INTO tasks (project_id, owner_user_id, title, status, priority, due_date, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*task, now),
        )

    messages = [
        (project_ids[0], user_ids[0], "Initial TPO quantities are in. I want one more pass on parapet wall flashing before we lock the order."),
        (project_ids[0], user_ids[1], "I can review tenant access notes this afternoon and update the handoff task."),
        (project_ids[1], user_ids[2], "Metal trim counts match vendor bundles. This one is ready for ordering."),
    ]
    for project_id, user_id, body in messages:
        db.execute(
            "INSERT INTO project_messages (project_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
            (project_id, user_id, body, now),
        )

    activity = [
        (project_ids[0], "Ava Cole", "takeoff_run", "Generated native AI takeoff from permit blueprint set."),
        (project_ids[0], "RidgeFlow AI", "blueprint_analyzed", "Analyzed permit set and extracted TPO takeoff signals."),
        (project_ids[1], "RidgeFlow AI", "blueprint_analyzed", "Analyzed metal panel set and detected ridge and valley lengths."),
        (project_ids[0], "Jordan Reed", "task_created", "Added tenant access coordination task."),
        (project_ids[1], "Luis Benton", "takeoff_approved", "Approved standing seam takeoff for ordering."),
        (project_ids[2], "Ava Cole", "blueprint_uploaded", "Uploaded bid set PDF for residential reroof."),
        (project_ids[2], "RidgeFlow AI", "blueprint_analyzed", "Analyzed residential bid set and suggested architectural shingles."),
    ]
    for project_id, actor_name, event_type, event_text in activity:
        db.execute(
            """
            INSERT INTO project_activity (project_id, actor_name, event_type, event_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, actor_name, event_type, event_text, now),
        )

    db.commit()
