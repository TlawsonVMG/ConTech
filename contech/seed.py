import json

from werkzeug.security import generate_password_hash


def seed_demo_data(db):
    db.execute(
        """
        INSERT INTO branches (id, name, code, address, city, state, postal_code)
        VALUES (1, 'ConTech Main Branch', 'MAIN', '1880 Trade Yard Way', 'Sacramento', 'CA', '95828')
        """
    )

    users = [
        (1, 1, "admin", generate_password_hash("ConTech!2026"), "Thomas Lawson", "admin", 1),
        (2, 1, "micah", generate_password_hash("Roofing!2026"), "Micah Harper", "sales", 1),
        (3, 1, "andrea", generate_password_hash("Siding!2026"), "Andrea Cole", "sales", 1),
        (4, 1, "ramon", generate_password_hash("Commercial!2026"), "Ramon Ellis", "sales", 1),
        (5, 1, "dispatch", generate_password_hash("Dispatch!2026"), "Dana Porter", "dispatch", 1),
        (6, 1, "inventory", generate_password_hash("Inventory!2026"), "Ivy Brooks", "inventory", 1),
        (7, 1, "accounting", generate_password_hash("Ledger!2026"), "Avery Stone", "accounting", 1),
    ]
    db.executemany(
        """
        INSERT INTO users (id, branch_id, username, password_hash, full_name, role_name, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        users,
    )

    customers = [
        (1, 1, "Morris Residence", "Residential", 1, "Denise Morris", "(555) 102-9941", "denise@example.com", "428 Juniper Ridge Dr, Sacramento, CA", "active", "Roofing, fascia, gutters", "2 projects in 4 years / strong referral source"),
        (2, 1, "Alder Creek HOA", "Commercial", 0, "Melissa Tran", "(555) 215-7730", "board@aldercreekhoa.org", "215 Alder Creek Pkwy, Sacramento, CA", "active", "Storm restoration", "Requires board approval and milestone billing"),
        (3, 1, "Summit Dental Plaza", "Commercial", 0, "Owen Taylor", "(555) 984-2284", "otaylor@summitdental.com", "918 Market Plaza, Sacramento, CA", "active", "Commercial siding and membrane repair", "Tight delivery windows and tenant notice needs"),
        (4, 1, "Lopez Residence", "Residential", 0, "Maria Lopez", "(555) 908-3308", "mlopez@example.com", "17 Harbor Lane, Elk Grove, CA", "active", "Siding repair", "High engagement, financing questions open"),
        (5, 1, "Bennett Duplex", "Residential", 0, "Adam Bennett", "(555) 443-1880", "adam@example.com", "91 El Camino Ct, Roseville, CA", "active", "Roof + gutters", "Deposit received and moving into production"),
        (6, 1, "Crescent Bistro", "Commercial", 0, "Jules Carter", "(555) 616-5549", "jules@crescentbistro.com", "601 Main St, Sacramento, CA", "active", "Facade repairs", "Storefront schedule is sensitive to lunch traffic"),
    ]
    db.executemany(
        """
        INSERT INTO customers (
            id, branch_id, name, segment, is_repeat, primary_contact, phone, email,
            service_address, status, trade_mix, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    customer_contacts = [
        (1, 1, 1, "Denise Morris", "Primary contact", "(555) 102-9941", "denise@example.com", 1, "Homeowner and decision maker."),
        (2, 1, 2, "Melissa Tran", "Board president", "(555) 215-7730", "board@aldercreekhoa.org", 1, "Leads board approval and scope review."),
        (3, 1, 2, "Nadia Keller", "Accounts payable", "(555) 215-7781", "ap@aldercreekhoa.org", 0, "Needs progress billing backup before release."),
        (4, 1, 2, "Victor Stone", "Site superintendent", "(555) 215-7794", "vstone@aldercreekhoa.org", 0, "Coordinates resident notices and staging windows."),
        (5, 1, 3, "Owen Taylor", "Property manager", "(555) 984-2284", "otaylor@summitdental.com", 1, "Main commercial contact for scheduling."),
        (6, 1, 3, "Janine Brooks", "Office manager", "(555) 984-2290", "jbrooks@summitdental.com", 0, "Needs tenant-facing delivery timing notice."),
        (7, 1, 4, "Maria Lopez", "Primary contact", "(555) 908-3308", "mlopez@example.com", 1, "Customer still comparing financing options."),
        (8, 1, 5, "Adam Bennett", "Primary contact", "(555) 443-1880", "adam@example.com", 1, "Repeatable duplex operator contact."),
        (9, 1, 6, "Jules Carter", "Owner", "(555) 616-5549", "jules@crescentbistro.com", 1, "Needs lunch-rush aware install timing."),
        (10, 1, 6, "Alicia Rowe", "Bookkeeper", "(555) 616-5572", "books@crescentbistro.com", 0, "Handles payment remittance and invoice packets."),
    ]
    db.executemany(
        """
        INSERT INTO customer_contacts (
            id, branch_id, customer_id, full_name, role_label, phone, email, is_primary, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customer_contacts,
    )

    portal_users = [
        (
            1,
            1,
            1,
            "denise@example.com",
            generate_password_hash("Customer!2026"),
            "Denise Morris",
            1,
            "2026-04-09 09:00",
            None,
        ),
        (
            2,
            1,
            2,
            "board@aldercreekhoa.org",
            generate_password_hash("Customer!2026"),
            "Melissa Tran",
            1,
            "2026-04-09 09:10",
            None,
        ),
    ]
    db.executemany(
        """
        INSERT INTO customer_portal_users (
            id, branch_id, customer_id, email, password_hash, full_name, is_active, created_at, last_login_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        portal_users,
    )

    leads = [
        (1, 1, 1, "Referrals", "Roof replacement", "Quoted", "Micah", "2026-03-31", 22400, 0),
        (2, 1, 2, "Insurance agents", "Storm restoration", "Negotiation", "Ramon", "2026-03-30", 118000, 1),
        (3, 1, 3, "Website leads", "Commercial siding patch + membrane repair", "Inspection", "Ramon", "2026-04-01", 46900, 1),
        (4, 1, 4, "Retail partner", "Siding hail claim", "Inspection", "Andrea", "2026-04-02", 18900, 0),
        (5, 1, 5, "Referrals", "Roof + gutters", "Won / Ready", "Micah", "2026-03-28", 27600, 0),
        (6, 1, 6, "Website leads", "Facade repairs", "Won / Ready", "Ramon", "2026-03-29", 41500, 1),
        (7, 1, None, "Website leads", "Board and batten siding", "New Leads", "Andrea", "2026-04-03", 31700, 0),
        (8, 1, None, "Referrals", "Metal roof retrofit", "New Leads", "Andrea", "2026-04-03", 54200, 1),
    ]
    db.executemany(
        """
        INSERT INTO leads (
            id, branch_id, customer_id, source, trade_interest, stage, assigned_rep,
            inspection_date, estimated_value, is_commercial
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        leads,
    )

    opportunities = [
        (1, 1, 1, 1, "Morris Residence", "Full roof replacement + fascia", "Quoted", "2026-04-04", 22400, 88, "Roofing", "Micah"),
        (2, 1, 3, 3, "Summit Dental Plaza", "Commercial siding patch + membrane repair", "Inspection", "2026-04-08", 46900, 72, "Roofing + Siding", "Ramon"),
        (3, 1, 2, 2, "Alder Creek HOA", "Building C storm restoration", "Negotiation", "2026-04-06", 118000, 94, "Roofing", "Ramon"),
        (4, 1, 7, None, "Meyer Barn Conversion", "Board and batten siding", "New Leads", "2026-04-10", 31700, 54, "Siding", "Andrea"),
        (5, 1, 5, 5, "Bennett Duplex", "Roof + gutters", "Won / Ready", "2026-04-02", 27600, 81, "Roofing + Gutters", "Micah"),
        (6, 1, 6, 6, "Crescent Bistro", "Storefront facade repairs", "Won / Ready", "2026-04-03", 41500, 78, "Siding", "Ramon"),
        (7, 1, 4, 4, "Lopez Residence", "Roof leak + soffit", "Inspection", "2026-04-05", 14300, 63, "Roofing", "Andrea"),
        (8, 1, 8, None, "Bayside Auto Spa", "Metal roof retrofit", "New Leads", "2026-04-11", 54200, 67, "Roofing", "Andrea"),
        (9, 1, None, 4, "Jordan Residence", "Siding hail claim", "New Leads", "2026-04-10", 18900, 55, "Siding", "Micah"),
        (10, 1, None, None, "Edison Church", "Fiber cement siding", "Quoted", "2026-04-07", 39800, 69, "Siding", "Andrea"),
    ]
    db.executemany(
        """
        INSERT INTO opportunities (
            id, branch_id, lead_id, customer_id, name, subtitle, stage, close_date, value,
            priority, trade_mix, rep
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        opportunities,
    )

    quotes = [
        (1, 1, 1, 1, "Quote #8891", "Roof replacement contract", "Owens Corning Duration / upgraded venting / fixed-margin package", 22400, 14560, 35.0, 8.25, 1501.50, 23901.50, 0, 7840, 3, 5600, 5600, "Approved", "2026-04-02", "2026-04-01", "2026-04-08"),
        (2, 1, 3, 2, "Quote #8904", "Storm restoration contract", "Building C restoration scope with board-ready billing schedule", 118000, 80240, 32.0, 8.25, 5197.50, 123197.50, 0, 37760, 4, 23600, 23600, "Approved", "2026-04-02", "2026-04-01", "2026-04-10"),
        (3, 1, 7, 4, "Quote #8917", "Repair and trim contract", "Roof leak repair with soffit and fascia cleanup", 14300, 9438, 34.0, 8.25, 750.75, 15050.75, 0, 4862, 3, 3575, 0, "Draft", None, "2026-04-02", "2026-04-12"),
    ]
    db.executemany(
        """
        INSERT INTO quotes (
            id, branch_id, opportunity_id, customer_id, quote_number, option_name, description,
            amount, estimated_cost, target_margin_pct, tax_rate_pct, tax_total, grand_total,
            discount_total, profit_amount, line_item_count, deposit_required, deposit_received,
            status, signed_date, issue_date, expiration_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        quotes,
    )

    jobs = [
        (1, 1, 1, 1, 1, "Morris Residence", "Roof replacement", "Delivery pending", "2026-04-07", "Crew Red", 22400),
        (2, 1, 5, None, 5, "Bennett Duplex", "Roof + gutters", "Ready for production", "2026-04-06", "Crew White", 27600),
        (3, 1, 6, None, 6, "Crescent Bistro", "Facade repairs", "Delivery pending", "2026-04-05", "Crew North", 41500),
        (4, 1, 3, 2, 2, "Alder Creek HOA", "Storm restoration", "Delivery pending", "2026-04-08", "Crew Slate", 118000),
    ]
    db.executemany(
        """
        INSERT INTO jobs (
            id, branch_id, opportunity_id, quote_id, customer_id, name, scope, status, scheduled_start,
            crew_name, committed_revenue
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        jobs,
    )

    change_orders = [
        (
            1,
            1,
            4,
            2,
            2,
            "CO-1001",
            "Deck sheathing replacement",
            "Field inspection uncovered wet deck sections that need replacement before dry-in.",
            "Approved",
            "2026-04-02",
            "2026-04-03",
            4200,
            2950,
            1,
            "Ramon Ellis",
            1,
            "Board approved the field condition change after photo review.",
        ),
        (
            2,
            1,
            3,
            6,
            None,
            "CO-1002",
            "Additional storefront flashing",
            "Add flashing detail around the east storefront return for water diversion.",
            "Pending Approval",
            "2026-04-02",
            None,
            1850,
            1120,
            0,
            "Dana Porter",
            1,
            "Owner review still pending before fabrication starts.",
        ),
        (
            3,
            1,
            1,
            1,
            1,
            "CO-1003",
            "Ventilation upgrade",
            "Upgrade intake and ridge ventilation package to meet attic airflow target.",
            "Draft",
            "2026-04-02",
            None,
            980,
            540,
            0,
            "Micah Harper",
            1,
            "Sales is preparing homeowner approval backup.",
        ),
    ]
    db.executemany(
        """
        INSERT INTO change_orders (
            id, branch_id, job_id, customer_id, quote_id, change_number, title, description, status,
            requested_date, approved_date, amount, cost_impact, schedule_days, owner_name, is_billable, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        change_orders,
    )
    change_order_fields = (
        "id",
        "branch_id",
        "job_id",
        "customer_id",
        "quote_id",
        "change_number",
        "title",
        "description",
        "status",
        "requested_date",
        "approved_date",
        "amount",
        "cost_impact",
        "schedule_days",
        "owner_name",
        "is_billable",
        "notes",
    )
    change_order_versions = [
        (
            change_order[0],
            1,
            change_order[0],
            1,
            change_order[9],
            change_order[14],
            "Initial seeded version",
            json.dumps(dict(zip(change_order_fields, change_order))),
        )
        for change_order in change_orders
    ]
    db.executemany(
        """
        INSERT INTO change_order_versions (
            id, branch_id, change_order_id, version_number, changed_at, changed_by, change_summary, snapshot_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        change_order_versions,
    )

    deliveries = [
        (1, 1, 1, "Route 02 / South Yard", "Truck 2", "2026-04-02 07:30", "En route", 91, "Shingles + ridge cap to Morris Residence"),
        (2, 1, 3, "Route 04 / Downtown", "Truck 4", "2026-04-02 08:15", "Loading", 73, "Facade repair material packs for Crescent Bistro"),
        (3, 1, 2, "Route 07 / North Loop", "Truck 7", "2026-04-02 10:00", "Delivered", 100, "Dumpster swap + underlayment refill"),
        (4, 1, 4, "Route 05 / East Yard", "Truck 5", "2026-04-02 13:30", "Scheduled", 84, "Stage materials for Alder Creek HOA"),
    ]
    db.executemany(
        """
        INSERT INTO deliveries (
            id, branch_id, job_id, route_name, truck_name, eta, status,
            load_percent, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        deliveries,
    )

    job_documents = [
        (
            1,
            1,
            1,
            1,
            "Photo",
            "Pre-tearoff roof overview",
            "photos/morris/pretearoff-01.jpg",
            None,
            None,
            "2026-04-02 07:10",
            "Crew Red",
            "Logged",
            "Field photo set captured before tear-off started.",
        ),
        (
            2,
            1,
            4,
            2,
            "Permit",
            "HOA staging permit",
            "permits/alder-creek-building-c.pdf",
            None,
            None,
            "2026-04-02 10:00",
            "Ramon Ellis",
            "Approved",
            "Board and city permit packet approved for Building C staging.",
        ),
        (
            3,
            1,
            3,
            6,
            "Inspection",
            "Downtown facade waterproofing check",
            "inspections/crescent-bistro-east-return.txt",
            None,
            None,
            "2026-04-02 15:15",
            "Dana Porter",
            "Pending Review",
            "Need PM review before storefront closes out.",
        ),
        (
            4,
            1,
            2,
            5,
            "Material Receipt",
            "Gutter bundle delivery receipt",
            "receipts/bennett-duplex-gutters.pdf",
            None,
            None,
            "2026-04-02 11:40",
            "Dana Porter",
            "Closed",
            "Delivery received and checked into the job packet.",
        ),
    ]
    db.executemany(
        """
        INSERT INTO job_documents (
            id, branch_id, job_id, customer_id, record_type, title, file_reference, stored_file_name,
            original_filename, captured_at, owner_name, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        job_documents,
    )

    vendors = [
        (1, 1, "Beacon West", "Supplier", 23800, "2026-04-06"),
        (2, 1, "South Supply", "Supplier", 15480, "2026-04-05"),
        (3, 1, "ABC Branch Transfer", "Supplier", 8000, "2026-04-07"),
    ]
    db.executemany(
        """
        INSERT INTO vendors (id, branch_id, name, category, amount_due, due_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        vendors,
    )

    inventory_items = [
        (1, 1, 1, "SH-CHAR-30", "Charcoal laminate shingles", "Roofing", 18, 32, 94, 134, "Low"),
        (2, 1, 1, "FA-WHT-6", "White 6in fascia coil", "Trim", 44, 19, 71, 109, "Cost spike"),
        (3, 1, 2, "UL-SYN-500", "Synthetic underlayment", "Roofing", 122, 41, 27, 49, "Healthy"),
        (4, 1, 2, "SD-FCL-8", "Fiber cement lap siding", "Siding", 64, 58, 213, 296, "Watch"),
    ]
    db.executemany(
        """
        INSERT INTO inventory_items (
            id, branch_id, vendor_id, sku, item_name, category, stock_on_hand,
            reserved_qty, unit_cost, unit_price, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        inventory_items,
    )

    quote_line_items = [
        (1, 1, 1, None, 1, "", "Tear-off + disposal", "Remove existing roofing, haul-off debris, and protect landscaping before install.", "job", 1, 2800, 4200, 0, 0, 8.25, 2800, 4200, 0, 4200, 1400, 33.3),
        (2, 1, 1, 1, 2, "SH-CHAR-30", "Charcoal laminate shingles", "Roof field shingle package with starter, ridge, and accessory bundle.", "lot", 1, 7560, 11900, 0, 1, 8.25, 7560, 11900, 981.75, 12881.75, 4340, 36.5),
        (3, 1, 1, 2, 3, "FA-WHT-6", "Fascia + ventilation package", "Fascia metal, venting accessories, and finish trim allowance.", "lot", 1, 4200, 6300, 0, 1, 8.25, 4200, 6300, 519.75, 6819.75, 2100, 33.3),
        (4, 1, 2, None, 1, "", "Labor + tear-off crew", "Commercial tear-off, dry-in labor, and haul-off sequencing for Building C.", "job", 1, 17760, 24600, 0, 0, 8.25, 17760, 24600, 0, 24600, 6840, 27.8),
        (5, 1, 2, 1, 2, "SH-CHAR-30", "Roof field material package", "Primary shingle field package with underlayment and accessory allowance.", "lot", 1, 29680, 44800, 0, 1, 8.25, 29680, 44800, 3696, 48496, 15120, 33.8),
        (6, 1, 2, 4, 3, "SD-FCL-8", "Siding + trim replacement", "Fiber cement siding sections, trim stock, and building-envelope accessories.", "lot", 1, 12040, 18200, 0, 1, 8.25, 12040, 18200, 1501.50, 19701.50, 6160, 33.8),
        (7, 1, 2, None, 4, "", "Staging + permits", "Lift staging, safety setup, board paperwork, and permit coordination.", "job", 1, 20760, 30400, 0, 0, 8.25, 20760, 30400, 0, 30400, 9640, 31.7),
        (8, 1, 3, None, 1, "", "Leak repair labor", "Targeted roof leak repair, decking prep, and detail waterproofing labor.", "job", 1, 3510, 5200, 0, 0, 8.25, 3510, 5200, 0, 5200, 1690, 32.5),
        (9, 1, 3, 2, 2, "FA-WHT-6", "Soffit + fascia materials", "Trim metal, soffit sections, and finish accessories for repair scope.", "lot", 1, 3318, 5100, 0, 1, 8.25, 3318, 5100, 420.75, 5520.75, 1782, 34.9),
        (10, 1, 3, None, 3, "", "Sealant + cleanup", "Sealant, touch-up, and final cleanup allowance.", "job", 1, 2610, 4000, 0, 1, 8.25, 2610, 4000, 330, 4330, 1390, 34.8),
    ]
    db.executemany(
        """
        INSERT INTO quote_line_items (
            id, branch_id, quote_id, inventory_item_id, sort_order, sku, item_name, description,
            unit_label, quantity, unit_cost, unit_price, discount_pct, taxable, tax_rate_pct,
            line_cost, line_subtotal, line_tax, line_total, profit_amount, margin_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        quote_line_items,
    )

    job_materials = [
        (1, 1, 1, 1, 12, 12, 0, "Reserved", "Shingles staged for south slope tear-off"),
        (2, 1, 1, 3, 6, 6, 0, "Reserved", "Underlayment for Morris residence day-one delivery"),
        (3, 1, 2, 1, 20, 20, 0, "Reserved", "Roof field squares reserved for duplex install"),
        (4, 1, 2, 2, 19, 19, 0, "Reserved", "Fascia coil bundled with gutter package"),
        (5, 1, 3, 4, 28, 28, 0, "Reserved", "Commercial siding pallets for storefront repair"),
        (6, 1, 3, 3, 35, 35, 0, "Reserved", "Underlayment rolls set aside for facade weatherproofing"),
        (7, 1, 4, 4, 30, 30, 0, "Reserved", "Fiber cement siding staged for HOA building C"),
    ]
    db.executemany(
        """
        INSERT INTO job_materials (
            id, branch_id, job_id, inventory_item_id, requested_qty, reserved_qty,
            shortage_qty, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        job_materials,
    )

    purchase_requests = [
        (
            1,
            1,
            2,
            4,
            7,
            4,
            "Alder Creek HOA siding replenishment",
            "Fiber cement siding short by 12 panels for Building C storm restoration.",
            12,
            12,
            0,
            "high",
            "Open",
            "Ivy Brooks",
            "2026-04-05",
            "2026-04-05",
            "South Supply can release material on the noon truck if the PO is sent before 9 AM.",
        ),
        (
            2,
            1,
            3,
            3,
            6,
            3,
            "Crescent Bistro underlayment transfer",
            "Move 12 rolls of underlayment to South Yard for downtown facade weatherproofing.",
            12,
            12,
            12,
            "medium",
            "Received",
            "Dana Porter",
            "2026-04-04",
            "2026-04-04",
            "Branch transfer approved and received into the yard this morning.",
        ),
        (
            3,
            1,
            2,
            None,
            None,
            2,
            "South Supply fascia quote request",
            "Compare fascia coil pricing before the next branch PO.",
            24,
            0,
            0,
            "medium",
            "Quoted",
            "Ivy Brooks",
            "2026-04-06",
            "2026-04-07",
            "Waiting on final coil color availability from vendor sales desk.",
        ),
    ]
    db.executemany(
        """
        INSERT INTO purchase_requests (
            id, branch_id, vendor_id, job_id, job_material_id, inventory_item_id, title, details,
            requested_qty, ordered_qty, received_qty, priority, status, owner_name, needed_by, eta_date,
            vendor_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        purchase_requests,
    )

    job_cost_entries = [
        (1, 1, 1, 1, "Material", "Material", "Roof field shingles and accessories", 1, 1486, 1486, "2026-04-02", "Posted", "Initial supplier pickup already loaded to job."),
        (2, 1, 1, None, "Labor", "Labor", "Tear-off and decking prep crew", 12, 38, 456, "2026-04-03", "Committed", "Crew Red first-day labor estimate."),
        (3, 1, 3, 2, "Material", "Material", "Commercial sealant and trim stock", 1, 2140, 2140, "2026-04-02", "Posted", "Downtown facade material bundle."),
        (4, 1, 4, None, "Subcontract", "Subcontract", "Lift rental for HOA elevation work", 1, 1850, 1850, "2026-04-04", "Committed", "Rental booked pending final delivery slot."),
    ]
    db.executemany(
        """
        INSERT INTO job_cost_entries (
            id, branch_id, job_id, vendor_id, cost_code, source_type, description, quantity,
            unit_cost, total_cost, cost_date, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        job_cost_entries,
    )

    invoices = [
        (1, 1, None, None, 5, 2, "Invoice #1042", "Standard", None, "Partial Paid", 8280, "2026-04-01", "2026-04-02", None, None, 0, 0, "Current", 5620),
        (2, 1, None, None, 6, 3, "Sales Order #225", "Progress", "APP-02", "Partial Paid", 41500, "2026-04-01", "2026-04-04", "2026-03-25", "2026-04-01", 10, 4150, "Current", 12200),
        (3, 1, 2, None, 1, 1, "Quote #8891", "Standard", None, "Issued", 22400, "2026-04-01", "2026-04-03", None, None, 0, 0, "Current", 22400),
        (4, 1, None, None, 2, 4, "Progress Invoice #990", "Progress", "APP-01", "Issued", 29600, "2026-04-01", "2026-04-05", "2026-04-01", "2026-04-07", 10, 2960, "1-30 days", 29600),
        (5, 1, None, None, 4, None, "Invoice #1030", "Standard", None, "Issued", 3480, "2026-03-01", "2026-03-15", None, None, 0, 0, "31-60 days", 3480),
    ]
    db.executemany(
        """
        INSERT INTO invoices (
            id, branch_id, quote_id, change_order_id, customer_id, job_id, invoice_number, billing_type,
            application_number, status, amount, issued_date, due_date, billing_period_start, billing_period_end,
            retainage_pct, retainage_held, aging_bucket, remaining_balance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        invoices,
    )

    bank_accounts = [
        (1, 1, "Operating Cash", "Checking", 184200, 179400),
        (2, 1, "Payroll Account", "Checking", 42980, 42980),
    ]
    db.executemany(
        """
        INSERT INTO bank_accounts (
            id, branch_id, account_name, account_type, current_balance, available_balance
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        bank_accounts,
    )

    invoice_payments = [
        (1, 1, 1, 5, 1, "2026-04-01", 2660, "ACH", "ACH-1042-A", "Avery Stone", "Initial partial payment applied from the operating account."),
        (2, 1, 2, 6, 1, "2026-04-01", 29300, "Wire", "WIRE-225-A", "Avery Stone", "Commercial progress draw received and posted."),
    ]
    db.executemany(
        """
        INSERT INTO invoice_payments (
            id, branch_id, invoice_id, customer_id, deposit_account_id, payment_date,
            payment_amount, payment_method, reference_number, posted_by, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        invoice_payments,
    )

    company_cards = [
        (1, 1, "Fuel Card", "4 active drivers / $1,280 this month", 1280),
        (2, 1, "Materials Card", "Used for emergency supplier pickups only", 3920),
        (3, 1, "Office Card", "Low activity / policy compliant", 420),
    ]
    db.executemany(
        """
        INSERT INTO company_cards (id, branch_id, card_name, note, spend_month_to_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        company_cards,
    )

    employees = [
        (1, 1, "Micah Harper", "Sales", "commission", 0),
        (2, 1, "Andrea Cole", "Sales", "commission", 0),
        (3, 1, "Ramon Ellis", "Sales", "commission", 0),
        (4, 1, "Crew Red", "Production", "hourly", 34),
        (5, 1, "Crew White", "Production", "hourly", 32),
        (6, 1, "Crew North", "Production", "hourly", 38),
    ]
    db.executemany(
        """
        INSERT INTO employees (id, branch_id, full_name, role_name, pay_type, pay_rate)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        employees,
    )

    payroll_runs = [
        (1, 1, "Weekly Payroll", "2026-04-03", 18900, "scheduled", "Overtime elevated on storm work this week."),
    ]
    db.executemany(
        """
        INSERT INTO payroll_runs (
            id, branch_id, period_label, process_date, gross_pay, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        payroll_runs,
    )

    ledger_accounts = [
        (1, 1, "1000", "Cash", "asset", 1),
        (2, 1, "1100", "Accounts Receivable", "asset", 1),
        (3, 1, "2000", "Accounts Payable", "liability", 1),
        (4, 1, "4000", "Sales Revenue", "revenue", 1),
        (5, 1, "5000", "Cost of Goods Sold", "expense", 1),
        (6, 1, "6100", "Payroll Expense", "expense", 1),
    ]
    db.executemany(
        """
        INSERT INTO ledger_accounts (id, branch_id, code, account_name, account_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ledger_accounts,
    )

    journal_entries = [
        (1, 1, "2026-04-01", "DEP-1042", "Customer deposit recorded", "posted"),
        (2, 1, "2026-04-01", "VEND-880", "Beacon West payable booked", "posted"),
    ]
    db.executemany(
        """
        INSERT INTO journal_entries (id, branch_id, entry_date, reference_code, memo, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        journal_entries,
    )

    journal_lines = [
        (1, 1, 1, 8280, 0),
        (2, 1, 4, 0, 8280),
        (3, 2, 5, 15480, 0),
        (4, 2, 3, 0, 15480),
    ]
    db.executemany(
        """
        INSERT INTO journal_entry_lines (
            id, journal_entry_id, ledger_account_id, debit_amount, credit_amount
        ) VALUES (?, ?, ?, ?, ?)
        """,
        journal_lines,
    )

    tasks = [
        (1, 1, 2, "Send revised HOA contract for board review", "Customer 360", "Ramon", "2026-04-03", "2026-04-03 08:30", "open", "high", "Board packet needs the updated scope line and payment milestones before noon."),
        (2, 1, 1, "Call Morris Residence before contract expires", "Customer 360", "Micah", "2026-04-03", "2026-04-03 14:00", "open", "high", "Confirm signature timing and delivery access before the weekend."),
        (3, 1, 4, "Confirm insurance paperwork and photo set", "Customer 360", "Andrea", "2026-04-04", "2026-04-04 09:00", "open", "medium", "Customer still owes final claim packet for soffit and fascia repair."),
        (4, 1, 5, "Move Bennett Duplex from deposit paid to production ready", "Operations", "Micah", "2026-04-03", "2026-04-03 11:15", "open", "high", "Check that gutters and shingles are fully reserved before dispatch locks the route."),
    ]
    db.executemany(
        """
        INSERT INTO tasks (
            id, branch_id, customer_id, title, module_name, owner_name, due_date, reminder_at, status, priority, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tasks,
    )

    activity_feed = [
        (1, 1, 1, "2026-03-31 15:10", "Inspection", "Micah", "Inspection completed", "Photos and ventilation notes uploaded from mobile."),
        (2, 1, 1, "2026-04-01 09:30", "Email", "Micah", "Contract email sent", "Fixed-margin contract delivered by email with customer notes on staging and cleanup."),
        (3, 1, 1, "2026-04-02 14:00", "Reminder", "Micah", "Follow-up scheduled", "Rep reminder set for 2:00 PM to close before weekend."),
        (4, 1, 2, "2026-04-02 11:20", "Note", "Ramon", "Board contact updated", "HOA board requested a cleaner payment schedule summary for the revised contract."),
        (5, 1, 6, "2026-04-02 16:40", "Dispatch", "Dana Porter", "Delivery timing confirmed", "Downtown load-in needs to happen before lunch traffic starts."),
    ]
    db.executemany(
        """
        INSERT INTO activity_feed (
            id, branch_id, customer_id, activity_date, activity_type, owner_name, title, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        activity_feed,
    )

    email_messages = [
        (1, 1, 1, "Outbound", "denise@example.com", "Roof replacement contract and install timing", "Sent fixed-margin contract and asked customer to confirm driveway and material drop access.", "Micah", "Sent", "2026-04-01 09:30", "Manual log"),
        (2, 1, 2, "Inbound", "board@aldercreekhoa.org", "Board review questions for building C", "Board requested updated scope copy and a cleaner milestone billing summary.", "Ramon", "Needs follow-up", "2026-04-02 11:05", "Manual log"),
        (3, 1, 6, "Outbound", "jules@crescentbistro.com", "Facade repair delivery window", "Shared an early-morning delivery window to avoid lunch rush disruption.", "Dana Porter", "Sent", "2026-04-02 16:30", "Manual log"),
    ]
    db.executemany(
        """
        INSERT INTO email_messages (
            id, branch_id, customer_id, direction, contact_email, subject, body, owner_name,
            status, sent_at, integration_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        email_messages,
    )

    calendar_events = [
        (1, 1, 1, "Contract follow-up call", "Call", "2026-04-03 14:00", "2026-04-03 14:30", "Micah", "Phone", "Planned", "Follow up on signature timing and confirm install week availability.", "Manual log"),
        (2, 1, 2, "HOA board review window", "Meeting", "2026-04-04 10:00", "2026-04-04 11:00", "Ramon", "Zoom", "Confirmed", "Walk the board through revised scope and payment milestones.", "Manual log"),
        (3, 1, 6, "Downtown site delivery window", "Site Visit", "2026-04-05 07:15", "2026-04-05 08:00", "Dana Porter", "Crescent Bistro loading zone", "Confirmed", "Delivery must finish before breakfast rush and dock restrictions.", "Manual log"),
    ]
    db.executemany(
        """
        INSERT INTO calendar_events (
            id, branch_id, customer_id, title, event_type, starts_at, ends_at, owner_name,
            location, status, notes, integration_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        calendar_events,
    )

    report_months = [
        (1, 1, "Jan", 342000, 35.2, 91),
        (2, 1, "Feb", 401000, 34.7, 93),
        (3, 1, "Mar", 468000, 33.8, 92),
        (4, 1, "Apr", 311000, 33.4, 92),
    ]
    db.executemany(
        """
        INSERT INTO report_months (
            id, branch_id, month_label, revenue_amount, gross_margin_pct, on_time_delivery_pct
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        report_months,
    )
