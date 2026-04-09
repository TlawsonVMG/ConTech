PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS journal_entry_lines;
DROP TABLE IF EXISTS journal_entries;
DROP TABLE IF EXISTS ledger_accounts;
DROP TABLE IF EXISTS report_months;
DROP TABLE IF EXISTS calendar_events;
DROP TABLE IF EXISTS email_messages;
DROP TABLE IF EXISTS activity_feed;
DROP TABLE IF EXISTS feedback_submissions;
DROP TABLE IF EXISTS auth_attempts;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS customer_contacts;
DROP TABLE IF EXISTS payroll_runs;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS company_cards;
DROP TABLE IF EXISTS invoice_payments;
DROP TABLE IF EXISTS bank_accounts;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS job_documents;
DROP TABLE IF EXISTS change_order_versions;
DROP TABLE IF EXISTS change_orders;
DROP TABLE IF EXISTS job_cost_entries;
DROP TABLE IF EXISTS job_materials;
DROP TABLE IF EXISTS purchase_requests;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS deliveries;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS quotes;
DROP TABLE IF EXISTS opportunities;
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS schema_migrations;
DROP TABLE IF EXISTS branches;

PRAGMA foreign_keys = ON;

CREATE TABLE branches (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    postal_code TEXT NOT NULL
);

CREATE TABLE schema_migrations (
    id INTEGER PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    name TEXT NOT NULL,
    segment TEXT NOT NULL,
    is_repeat INTEGER NOT NULL DEFAULT 0,
    primary_contact TEXT,
    phone TEXT,
    email TEXT,
    service_address TEXT NOT NULL,
    status TEXT NOT NULL,
    trade_mix TEXT,
    notes TEXT
);

CREATE TABLE customer_contacts (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    full_name TEXT NOT NULL,
    role_label TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE auth_attempts (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    attempted_at TEXT NOT NULL,
    was_success INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE feedback_submissions (
    id INTEGER PRIMARY KEY,
    submitted_at TEXT NOT NULL,
    submitter_name TEXT NOT NULL,
    submitter_email TEXT NOT NULL,
    company_name TEXT,
    role_label TEXT,
    page_url TEXT,
    summary TEXT NOT NULL,
    details TEXT NOT NULL,
    rating INTEGER,
    status TEXT NOT NULL,
    internal_notes TEXT,
    reviewed_at TEXT,
    reviewed_by TEXT
);

CREATE TABLE leads (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    customer_id INTEGER REFERENCES customers (id),
    source TEXT NOT NULL,
    trade_interest TEXT NOT NULL,
    stage TEXT NOT NULL,
    assigned_rep TEXT NOT NULL,
    inspection_date TEXT,
    estimated_value REAL NOT NULL,
    is_commercial INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    lead_id INTEGER REFERENCES leads (id),
    customer_id INTEGER REFERENCES customers (id),
    name TEXT NOT NULL,
    subtitle TEXT NOT NULL,
    stage TEXT NOT NULL,
    close_date TEXT NOT NULL,
    value REAL NOT NULL,
    priority INTEGER NOT NULL,
    trade_mix TEXT NOT NULL,
    rep TEXT NOT NULL
);

CREATE TABLE quotes (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    opportunity_id INTEGER REFERENCES opportunities (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    quote_number TEXT NOT NULL,
    option_name TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    estimated_cost REAL NOT NULL,
    target_margin_pct REAL NOT NULL,
    deposit_required REAL NOT NULL,
    deposit_received REAL NOT NULL,
    status TEXT NOT NULL,
    signed_date TEXT,
    issue_date TEXT,
    expiration_date TEXT
);

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    opportunity_id INTEGER REFERENCES opportunities (id),
    quote_id INTEGER REFERENCES quotes (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    name TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    scheduled_start TEXT,
    crew_name TEXT,
    committed_revenue REAL NOT NULL
);

CREATE TABLE deliveries (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    job_id INTEGER REFERENCES jobs (id),
    route_name TEXT NOT NULL,
    truck_name TEXT NOT NULL,
    eta TEXT NOT NULL,
    status TEXT NOT NULL,
    load_percent INTEGER NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE change_orders (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    job_id INTEGER NOT NULL REFERENCES jobs (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    quote_id INTEGER REFERENCES quotes (id),
    change_number TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_date TEXT NOT NULL,
    approved_date TEXT,
    amount REAL NOT NULL,
    cost_impact REAL NOT NULL,
    schedule_days INTEGER NOT NULL DEFAULT 0,
    owner_name TEXT NOT NULL,
    is_billable INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL
);

CREATE TABLE change_order_versions (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    change_order_id INTEGER NOT NULL REFERENCES change_orders (id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    changed_at TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    change_summary TEXT,
    snapshot_json TEXT NOT NULL
);

CREATE TABLE job_documents (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    job_id INTEGER NOT NULL REFERENCES jobs (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    record_type TEXT NOT NULL,
    title TEXT NOT NULL,
    file_reference TEXT,
    stored_file_name TEXT,
    original_filename TEXT,
    captured_at TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE vendors (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_due REAL NOT NULL,
    due_date TEXT NOT NULL
);

CREATE TABLE inventory_items (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    vendor_id INTEGER REFERENCES vendors (id),
    sku TEXT NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    stock_on_hand REAL NOT NULL,
    reserved_qty REAL NOT NULL,
    unit_cost REAL NOT NULL,
    unit_price REAL NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE job_materials (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    job_id INTEGER NOT NULL REFERENCES jobs (id),
    inventory_item_id INTEGER NOT NULL REFERENCES inventory_items (id),
    requested_qty REAL NOT NULL,
    reserved_qty REAL NOT NULL,
    shortage_qty REAL NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE purchase_requests (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    vendor_id INTEGER REFERENCES vendors (id),
    job_id INTEGER REFERENCES jobs (id),
    job_material_id INTEGER REFERENCES job_materials (id),
    inventory_item_id INTEGER REFERENCES inventory_items (id),
    title TEXT NOT NULL,
    details TEXT NOT NULL,
    requested_qty REAL,
    ordered_qty REAL NOT NULL DEFAULT 0,
    received_qty REAL NOT NULL DEFAULT 0,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    needed_by TEXT,
    eta_date TEXT,
    vendor_notes TEXT NOT NULL
);

CREATE TABLE job_cost_entries (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    job_id INTEGER NOT NULL REFERENCES jobs (id),
    vendor_id INTEGER REFERENCES vendors (id),
    cost_code TEXT NOT NULL,
    source_type TEXT NOT NULL,
    description TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    cost_date TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    quote_id INTEGER REFERENCES quotes (id),
    change_order_id INTEGER REFERENCES change_orders (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    job_id INTEGER REFERENCES jobs (id),
    invoice_number TEXT NOT NULL,
    billing_type TEXT NOT NULL,
    application_number TEXT,
    status TEXT NOT NULL,
    amount REAL NOT NULL,
    issued_date TEXT,
    due_date TEXT NOT NULL,
    billing_period_start TEXT,
    billing_period_end TEXT,
    retainage_pct REAL NOT NULL DEFAULT 0,
    retainage_held REAL NOT NULL DEFAULT 0,
    aging_bucket TEXT NOT NULL,
    remaining_balance REAL NOT NULL
);

CREATE TABLE bank_accounts (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    current_balance REAL NOT NULL,
    available_balance REAL NOT NULL
);

CREATE TABLE invoice_payments (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    invoice_id INTEGER NOT NULL REFERENCES invoices (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    deposit_account_id INTEGER REFERENCES bank_accounts (id),
    payment_date TEXT NOT NULL,
    payment_amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    reference_number TEXT,
    posted_by TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE company_cards (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    card_name TEXT NOT NULL,
    note TEXT NOT NULL,
    spend_month_to_date REAL NOT NULL
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    full_name TEXT NOT NULL,
    role_name TEXT NOT NULL,
    pay_type TEXT NOT NULL,
    pay_rate REAL NOT NULL
);

CREATE TABLE payroll_runs (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    period_label TEXT NOT NULL,
    process_date TEXT NOT NULL,
    gross_pay REAL NOT NULL,
    status TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE ledger_accounts (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    code TEXT NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE journal_entries (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    entry_date TEXT NOT NULL,
    reference_code TEXT NOT NULL,
    memo TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE journal_entry_lines (
    id INTEGER PRIMARY KEY,
    journal_entry_id INTEGER NOT NULL REFERENCES journal_entries (id),
    ledger_account_id INTEGER NOT NULL REFERENCES ledger_accounts (id),
    debit_amount REAL NOT NULL DEFAULT 0,
    credit_amount REAL NOT NULL DEFAULT 0
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    customer_id INTEGER REFERENCES customers (id),
    title TEXT NOT NULL,
    module_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    due_date TEXT NOT NULL,
    reminder_at TEXT,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    details TEXT NOT NULL
);

CREATE TABLE activity_feed (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    activity_date TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    title TEXT NOT NULL,
    details TEXT NOT NULL
);

CREATE TABLE email_messages (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    direction TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    status TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    integration_status TEXT NOT NULL
);

CREATE TABLE calendar_events (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    owner_name TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL,
    integration_status TEXT NOT NULL
);

CREATE TABLE report_months (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches (id),
    month_label TEXT NOT NULL,
    revenue_amount REAL NOT NULL,
    gross_margin_pct REAL NOT NULL,
    on_time_delivery_pct REAL NOT NULL
);
