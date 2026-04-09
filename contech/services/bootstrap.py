from datetime import datetime

from ..db import get_db


def _money(value):
    value = value or 0
    return f"${value:,.0f}"


def _money_2(value):
    value = value or 0
    return f"${value:,.2f}"


def _time_label(timestamp):
    dt = datetime.fromisoformat(timestamp)
    return dt.strftime("%I:%M").lstrip("0")


def _rows(query, params=()):
    return get_db().execute(query, params).fetchall()


def _row(query, params=()):
    return get_db().execute(query, params).fetchone()


def _value(row, key, default=0):
    if row is None:
        return default
    return row[key] if row[key] is not None else default


def _build_overview_metrics():
    pipeline = _row("SELECT COALESCE(SUM(value), 0) AS total FROM opportunities WHERE stage != 'Won / Ready'")
    pending_quotes = _row("SELECT COUNT(*) AS total FROM quotes WHERE status = 'Pending Signature'")
    deliveries = _row("SELECT COUNT(*) AS total FROM deliveries")
    receivables = _row("SELECT COALESCE(SUM(remaining_balance), 0) AS total FROM invoices")

    return [
        {"label": "Active Pipeline", "value": _money(_value(pipeline, "total")), "trend": "Single-branch live snapshot"},
        {"label": "Quotes Awaiting Signature", "value": str(_value(pending_quotes, "total")), "trend": "Backed by quote records"},
        {"label": "Deliveries This Week", "value": str(_value(deliveries, "total")), "trend": "Dispatch-linked jobs"},
        {"label": "AR Due in 7 Days", "value": _money(_value(receivables, "total")), "trend": "Receivables from live accounting data"},
    ]


def _build_dashboard():
    follow_ups = _row("SELECT COUNT(*) AS total FROM tasks WHERE status = 'open'")
    jobs_ready = _row("SELECT COUNT(*) AS total FROM jobs WHERE status IN ('Sales handoff', 'Ready for production', 'Materials reserved', 'Delivery pending')")
    vendor_due = _row("SELECT COALESCE(SUM(amount_due), 0) AS total FROM vendors")
    margin = _row("SELECT gross_margin_pct FROM report_months ORDER BY id DESC LIMIT 1")

    hot_pipeline = [
        {
            "name": row["name"],
            "subtitle": row["subtitle"],
            "stage": row["stage"],
            "close": row["close_date"],
            "value": _money(row["value"]),
            "priority": row["priority"],
        }
        for row in _rows(
            """
            SELECT name, subtitle, stage, close_date, value, priority
            FROM opportunities
            ORDER BY priority DESC
            LIMIT 4
            """
        )
    ]

    # Windows Python supports %#d rather than %-d, so normalize separately.
    for item, row in zip(
        hot_pipeline,
        _rows(
            """
            SELECT close_date
            FROM opportunities
            ORDER BY priority DESC
            LIMIT 4
            """
        ),
    ):
        item["close"] = datetime.fromisoformat(row["close_date"]).strftime("%b %d").replace(" 0", " ")

    dispatch = [
        {
            "time": _time_label(row["eta"]),
            "title": row["route_name"],
            "copy": row["notes"],
            "status": row["status"],
        }
        for row in _rows(
            """
            SELECT route_name, eta, notes, status
            FROM deliveries
            ORDER BY eta
            LIMIT 3
            """
        )
    ]

    inventory_risk = [
        {
            "title": row["item_name"],
            "copy": f"{row['stock_on_hand']:,.0f} on hand, {row['reserved_qty']:,.0f} reserved",
            "tone": "danger" if row["status"] == "Low" else "warning" if row["status"] in {"Watch", "Cost spike"} else "success",
        }
        for row in _rows(
            """
            SELECT item_name, stock_on_hand, reserved_qty, status
            FROM inventory_items
            ORDER BY CASE status
                WHEN 'Low' THEN 1
                WHEN 'Cost spike' THEN 2
                WHEN 'Watch' THEN 3
                ELSE 4
            END
            LIMIT 3
            """
        )
    ]

    overdue = _row(
        """
        SELECT COALESCE(SUM(remaining_balance), 0) AS total
        FROM invoices
        WHERE aging_bucket != 'Current'
        """
    )
    deposits = _row(
        """
        SELECT COALESCE(SUM(amount - remaining_balance), 0) AS total
        FROM invoices
        WHERE amount > remaining_balance
        """
    )
    payroll = _row("SELECT gross_pay FROM payroll_runs ORDER BY process_date DESC LIMIT 1")

    return {
        "focusAreas": [
            "Lead intake -> inspection",
            "Quote -> signed contract",
            "Material order -> delivery",
            "Invoice -> payment",
        ],
        "teamPulse": [
            {"label": "Sales follow-ups due", "value": str(_value(follow_ups, "total")), "copy": "Open task count from the CRM queue"},
            {"label": "Jobs ready for production", "value": str(_value(jobs_ready, "total")), "copy": "Sales handoff and ready jobs in the branch"},
            {"label": "Vendor bills due this week", "value": _money(_value(vendor_due, "total")), "copy": "Backed by open vendor payables"},
            {"label": "Gross margin forecast", "value": f"{_value(margin, 'gross_margin_pct'):.1f}%", "copy": "Latest report-month margin snapshot"},
        ],
        "hotPipeline": hot_pipeline,
        "dispatch": dispatch,
        "inventoryRisk": inventory_risk,
        "cashSignals": [
            {"label": "Deposits collected", "value": _money(_value(deposits, "total")), "tag": "Tied to invoice records"},
            {"label": "Invoices overdue", "value": _money(_value(overdue, "total")), "tag": "Receivables aging buckets"},
            {"label": "Open vendor bills", "value": _money(_value(vendor_due, "total")), "tag": "Vendor obligations across the branch"},
            {"label": "Payroll due Friday", "value": _money(_value(payroll, "gross_pay")), "tag": "Current payroll run scheduled"},
        ],
    }


def _build_sales():
    lanes = []
    for stage in ["New Leads", "Inspection", "Quoted", "Won / Ready"]:
        stage_rows = _rows(
            """
            SELECT name, subtitle, rep, value
            FROM opportunities
            WHERE stage = ?
            ORDER BY priority DESC
            """,
            (stage,),
        )
        total = sum(row["value"] for row in stage_rows)
        lanes.append(
            {
                "title": stage,
                "count": f"{len(stage_rows)} jobs / {_money(total)}",
                "cards": [
                    {
                        "name": row["name"],
                        "type": row["subtitle"],
                        "rep": row["rep"],
                        "value": _money(row["value"]),
                    }
                    for row in stage_rows
                ],
            }
        )

    channel_counts = _rows(
        """
        SELECT source, COUNT(*) AS total
        FROM leads
        GROUP BY source
        ORDER BY total DESC
        """
    )
    max_count = max((row["total"] for row in channel_counts), default=1)

    return {
        "lanes": lanes,
        "quoteOptions": [
            {
                "name": row["option_name"],
                "copy": row["description"],
                "amount": _money(row["amount"]),
                "tone": "warning" if row["option_name"] == "Good" else "success" if row["option_name"] == "Better" else "default",
            }
            for row in _rows("SELECT option_name, description, amount FROM quotes ORDER BY amount")
        ],
        "orders": [
            {
                "customer": row["name"],
                "doc": row["invoice_number"],
                "status": row["status"],
                "amount": _money(row["amount"]),
            }
            for row in _rows(
                """
                SELECT c.name, i.invoice_number, i.status, i.amount
                FROM invoices i
                JOIN customers c ON c.id = i.customer_id
                ORDER BY i.amount DESC
                LIMIT 4
                """
            )
        ],
        "channels": [
            {"label": row["source"], "value": round((row["total"] / max_count) * 100)}
            for row in channel_counts
        ],
        "actions": [row["title"] for row in _rows("SELECT title FROM tasks WHERE status = 'open' ORDER BY due_date, id LIMIT 4")],
    }


def _build_customers():
    cards = []
    for row in _rows(
        """
        SELECT name, segment, is_repeat, notes, trade_mix
        FROM customers
        ORDER BY id
        LIMIT 4
        """
    ):
        cards.append(
            {
                "name": row["name"],
                "line1": f"{row['segment']} {'/ repeat customer' if row['is_repeat'] else '/ active account'}",
                "line2": row["notes"],
                "tags": [part.strip() for part in row["trade_mix"].split(",")] if row["trade_mix"] else [],
            }
        )

    profile_customer = _row("SELECT * FROM customers ORDER BY id LIMIT 1")
    repeat_rate = _row("SELECT AVG(is_repeat) * 100 AS pct FROM customers")

    profile = []
    timeline = []
    if profile_customer:
        profile = [
            {"label": "Primary contact", "value": f"{profile_customer['primary_contact'] or 'Not set'} / {profile_customer['phone'] or 'Not set'}"},
            {"label": "Property", "value": profile_customer["service_address"]},
            {"label": "Trade mix", "value": profile_customer["trade_mix"] or "Not set"},
            {"label": "Open items", "value": "Review Customer 360 for next steps"},
        ]
        timeline = [
            {
                "time": datetime.fromisoformat(row["activity_date"]).strftime("%b %d").replace(" 0", " "),
                "title": row["title"],
                "copy": row["details"],
            }
            for row in _rows(
                """
                SELECT activity_date, title, details
                FROM activity_feed
                WHERE customer_id = ?
                ORDER BY activity_date
                """,
                (profile_customer["id"],),
            )
        ]
    else:
        profile = [
            {"label": "Primary contact", "value": "Create the first customer"},
            {"label": "Property", "value": "No service address on file yet"},
            {"label": "Trade mix", "value": "Roofing / siding"},
            {"label": "Open items", "value": "Start with Customer 360"},
        ]

    return {
        "cards": cards,
        "profile": profile,
        "timeline": timeline,
        "loyalty": [
            {"label": "Repeat-customer rate", "value": f"{_value(repeat_rate, 'pct'):.0f}%"},
            {"label": "Churn watch accounts", "value": "0"},
            {"label": "Avg response SLA", "value": "Not measured"},
            {"label": "Reviews requested", "value": "0"},
        ],
    }


def _build_reports():
    total_opps = _row("SELECT COUNT(*) AS total FROM opportunities")
    won_opps = _row("SELECT COUNT(*) AS total FROM opportunities WHERE stage = 'Won / Ready'")
    on_time = _row("SELECT on_time_delivery_pct AS pct FROM report_months ORDER BY id DESC LIMIT 1")
    total_opportunity_count = _value(total_opps, "total")
    win_rate = (_value(won_opps, "total") / total_opportunity_count) * 100 if total_opportunity_count else 0

    return {
        "kpis": [
            {"label": "Quote win rate", "value": f"{win_rate:.1f}%"},
            {"label": "Avg days to close", "value": "Not measured"},
            {"label": "Customer churn", "value": "0.0%"},
            {"label": "On-time delivery", "value": f"{_value(on_time, 'pct'):.0f}%"},
        ],
        "revenueBars": [
            {
                "label": row["month_label"],
                "value": round((row["revenue_amount"] / 500000) * 100),
                "amount": _money(row["revenue_amount"]),
            }
            for row in _rows("SELECT month_label, revenue_amount FROM report_months ORDER BY id")
        ],
        "marginByTrade": [
            {"label": "Roof replacement", "value": "35.4%"},
            {"label": "Storm restoration", "value": "31.9%"},
            {"label": "Siding install", "value": "29.6%"},
            {"label": "Repair work", "value": "42.1%"},
        ],
        "library": [
            "Profit by job and trade",
            "Sales by rep and lead source",
            "Material spend by supplier",
            "Inventory adjustments and shrinkage",
            "Accounts receivable aging",
            "Customer churn and repeat rate",
        ],
        "notes": [
            {"title": "Margin drift warning", "copy": "Commercial siding jobs are under target margin because material costs spiked this month."},
            {"title": "Healthy pipeline mix", "copy": "Referral leads continue to close faster and at higher average contract value."},
            {"title": "Retention focus", "copy": "Seven prior customers have gone 12+ months without a follow-up touch."},
        ],
    }


def _build_dispatch():
    route_rows = _rows(
        """
        SELECT route_name, notes, load_percent
        FROM deliveries
        ORDER BY eta
        LIMIT 3
        """
    )

    return {
        "routes": [
            {"title": row["route_name"], "copy": row["notes"], "value": row["load_percent"]}
            for row in route_rows
        ],
        "board": [
            {
                "time": _time_label(row["eta"]),
                "title": job_row["name"] if job_row else row["route_name"],
                "copy": row["notes"],
                "tag": row["truck_name"],
            }
            for row in _rows(
                """
                SELECT id, job_id, eta, truck_name, notes, route_name
                FROM deliveries
                ORDER BY eta
                """
            )
            for job_row in [_row("SELECT name FROM jobs WHERE id = ?", (row["job_id"],)) if row["job_id"] else None]
        ],
        "crews": [
            {"label": "Crew Red", "value": "2 roof installs / 1 repair"},
            {"label": "Crew White", "value": "Siding prep / 6.5 labor hrs booked"},
            {"label": "Crew Slate", "value": "Storm punch list / open afternoon slot"},
            {"label": "Crew North", "value": "Commercial sealant work / after-hours"},
        ],
        "notices": [
            {"title": "Customer text updates", "copy": "11 customers will receive ETA windows automatically today.", "tone": "success"},
            {"title": "Weather alert", "copy": "Possible wind delay after 2 PM for north loop deliveries.", "tone": "warning"},
            {"title": "Dock access note", "copy": "Summit Dental loading zone closes at 11:30 AM sharp.", "tone": "danger"},
        ],
    }


def _build_inventory():
    stock_rows = _rows(
        """
        SELECT sku, item_name, stock_on_hand, reserved_qty, unit_cost, unit_price, status
        FROM inventory_items
        ORDER BY id
        """
    )

    return {
        "stockRows": [
            {
                "item": row["item_name"],
                "sku": row["sku"],
                "stock": f"{row['stock_on_hand']:,.0f}",
                "reserved": f"{row['reserved_qty']:,.0f}",
                "cost": _money_2(row["unit_cost"]),
                "price": _money_2(row["unit_price"]),
                "status": row["status"],
            }
            for row in stock_rows
        ],
        "purchasing": [
            {"title": row["title"], "copy": row["details"]}
            for row in _rows("SELECT title, details FROM purchase_requests ORDER BY id")
        ],
        "controls": [
            {"label": "Warehouse stock lists", "value": "5 templates"},
            {"label": "Truck restock cycles", "value": "Nightly"},
            {"label": "Reserved job stock", "value": _money(sum(row["unit_cost"] * row["reserved_qty"] for row in stock_rows))},
            {"label": "Potential shrinkage", "value": "$2,140"},
        ],
        "marginSignals": [
            "Surface vendor price changes directly in the estimate workflow.",
            "Reserve stock against approved jobs before crews are scheduled.",
            "Flag jobs where real material cost erodes the quoted margin.",
        ],
    }


def _build_accounting():
    operating_cash = _row("SELECT current_balance FROM bank_accounts WHERE account_name = 'Operating Cash'")
    receivables = _row("SELECT COALESCE(SUM(remaining_balance), 0) AS total FROM invoices")
    payables = _row("SELECT COALESCE(SUM(amount_due), 0) AS total FROM vendors")
    payroll = _row("SELECT gross_pay, process_date FROM payroll_runs ORDER BY process_date DESC LIMIT 1")

    return {
        "balances": [
            {"label": "Operating cash", "value": _money(_value(operating_cash, "current_balance")), "copy": "After pending deposits clear"},
            {"label": "Receivables open", "value": _money(_value(receivables, "total")), "copy": "Invoice balance across active accounts"},
            {"label": "Payables open", "value": _money(_value(payables, "total")), "copy": "Vendor bills due this week"},
            {
                "label": "Payroll next run",
                "value": _money(_value(payroll, "gross_pay")),
                "copy": f"Scheduled for {_value(payroll, 'process_date', 'not scheduled')}",
            },
        ],
        "cards": [
            {"title": row["card_name"], "copy": row["note"]}
            for row in _rows("SELECT card_name, note FROM company_cards ORDER BY id")
        ],
        "aging": [
            {
                "customer": row["name"],
                "bucket": row["aging_bucket"],
                "amount": _money(row["remaining_balance"]),
                "status": row["status"],
            }
            for row in _rows(
                """
                SELECT c.name, i.aging_bucket, i.remaining_balance, i.status
                FROM invoices i
                JOIN customers c ON c.id = i.customer_id
                ORDER BY i.id
                LIMIT 4
                """
            )
        ],
        "payroll": [
            {"title": "Production labor", "copy": "Overtime elevated on storm work this week."},
            {"title": "Sales commissions", "copy": "Three reps eligible after Morris and Bennett close."},
            {"title": "Vendor payments", "copy": "Beacon West and South Supply due before Monday."},
        ],
    }


def build_bootstrap_payload():
    return {
        "overviewMetrics": _build_overview_metrics(),
        "dashboard": _build_dashboard(),
        "sales": _build_sales(),
        "customers": _build_customers(),
        "reports": _build_reports(),
        "dispatch": _build_dispatch(),
        "inventory": _build_inventory(),
        "accounting": _build_accounting(),
    }
