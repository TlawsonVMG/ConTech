import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ..auth import login_required, roles_required
from ..db import get_db
from ..services.bootstrap import build_bootstrap_payload

bp = Blueprint("crm", __name__)

CRM_ROLES = ("admin", "sales")
ALL_APP_ROLES = ("admin", "sales", "dispatch", "inventory", "accounting")
JOB_ROLES = ("admin", "sales", "dispatch")
MATERIAL_ROLES = ("admin", "dispatch", "inventory")
INVENTORY_MANAGE_ROLES = ("admin", "inventory")
INVOICE_ROLES = ("admin", "sales", "accounting")
DISPATCH_MANAGE_ROLES = ("admin", "dispatch")
CUSTOMER_SEGMENTS = ("Residential", "Commercial")
CUSTOMER_STATUSES = ("active", "prospect", "inactive")
LEAD_STAGES = ("New Leads", "Inspection", "Quoted", "Negotiation", "Won / Ready", "Lost")
LEAD_SOURCES = ("Referrals", "Website leads", "Retail partner", "Insurance agents", "Walk-in", "Other")
OPPORTUNITY_STAGES = ("New Leads", "Inspection", "Quoted", "Negotiation", "Won / Ready", "Lost")
QUOTE_STATUSES = ("Draft", "Sent", "Pending Signature", "Pending Deposit", "Approved", "Rejected", "Expired")
JOB_STATUSES = (
    "Sales handoff",
    "Scheduled",
    "Ready for production",
    "Materials reserved",
    "Delivery pending",
    "In progress",
    "Completed",
    "Cancelled",
)
INVOICE_STATUSES = ("Draft", "Issued", "Partial Paid", "Paid", "Void")
DELIVERY_STATUSES = ("Scheduled", "Loading", "En route", "Delivered", "Delayed", "Cancelled")
INVENTORY_CATEGORIES = ("Roofing", "Siding", "Trim", "Gutters", "Accessories", "Wrap", "Fasteners")
INVENTORY_STATUSES = ("Healthy", "Watch", "Low", "Cost spike", "Out of stock")
PURCHASE_PRIORITIES = ("low", "medium", "high")
PURCHASE_REQUEST_STATUSES = ("Open", "Quoted", "Ordered", "Received", "Closed", "Cancelled")
JOB_COST_SOURCE_TYPES = ("Material", "Labor", "Subcontract", "Equipment", "Permit", "Disposal", "Misc")
JOB_COST_STATUSES = ("Committed", "Posted", "Variance")
TASK_STATUSES = ("open", "scheduled", "completed", "cancelled")
TASK_PRIORITIES = ("low", "medium", "high")
TASK_MODULES = ("Customer 360", "Sales", "Operations", "Accounting", "Dispatch")
ACTIVITY_TYPES = ("Note", "Reminder", "Email", "Call", "Meeting", "Dispatch", "Inspection", "System")
EMAIL_DIRECTIONS = ("Outbound", "Inbound")
EMAIL_STATUSES = ("Draft", "Sent", "Received", "Needs follow-up", "Archived")
INTEGRATION_STATUSES = ("Manual log", "Ready for sync", "Synced")
CALENDAR_EVENT_TYPES = ("Call", "Meeting", "Site Visit", "Inspection", "Delivery Window", "Reminder")
CALENDAR_EVENT_STATUSES = ("Planned", "Confirmed", "Completed", "Cancelled")
PURCHASING_ROLES = ("admin", "dispatch", "inventory", "accounting")
COSTING_MANAGE_ROLES = ("admin", "dispatch", "inventory", "accounting")
FIELD_EXECUTION_MANAGE_ROLES = ("admin", "sales", "dispatch")
CONTACT_ROLE_OPTIONS = (
    "Primary contact",
    "Property manager",
    "Board president",
    "Accounts payable",
    "Site superintendent",
    "Office manager",
    "Owner",
    "Tenant coordinator",
    "Other",
)
PAYMENT_METHODS = ("Check", "ACH", "Wire", "Credit Card", "Cash")
CHANGE_ORDER_STATUSES = ("Draft", "Pending Approval", "Approved", "Rejected", "Invoiced")
JOB_DOCUMENT_TYPES = ("Photo", "Permit", "Inspection", "Material Receipt", "Contract", "Warranty", "Other")
JOB_DOCUMENT_STATUSES = ("Logged", "Pending Review", "Approved", "Closed")
INVOICE_BILLING_TYPES = ("Standard", "Deposit", "Progress", "Change Order", "Retainage Release", "Final")
JOB_DOCUMENT_UPLOAD_EXTENSIONS = (".jpg", ".jpeg", ".png", ".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx")


def _format_currency(value):
    return f"${value:,.0f}"


def _optional_int(value):
    value = (value or "").strip()
    return int(value) if value else None


def _optional_float(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _optional_date(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _optional_datetime(value):
    value = (value or "").strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return None


def _checkbox_value(form, key):
    return 1 if form.get(key) == "on" else 0


def _customer_choices():
    return get_db().execute(
        """
        SELECT id, name, segment
        FROM customers
        ORDER BY name
        """
    ).fetchall()


def _sales_rep_choices():
    rows = get_db().execute(
        """
        SELECT username, full_name
        FROM users
        WHERE role_name IN ('admin', 'sales') AND is_active = 1
        ORDER BY full_name
        """
    ).fetchall()
    return [
        {
            "username": row["username"],
            "label": row["full_name"],
            "rep_value": row["full_name"].split(" ")[0],
        }
        for row in rows
    ]


def _owner_choices():
    return get_db().execute(
        """
        SELECT username, full_name, role_name
        FROM users
        WHERE is_active = 1
        ORDER BY full_name
        """
    ).fetchall()


def _lead_choices():
    return get_db().execute(
        """
        SELECT id, source, trade_interest, stage, assigned_rep
        FROM leads
        ORDER BY id DESC
        """
    ).fetchall()


def _customer_form_data(form):
    return {
        "name": form.get("name", "").strip(),
        "segment": form.get("segment", "Residential"),
        "is_repeat": _checkbox_value(form, "is_repeat"),
        "primary_contact": form.get("primary_contact", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "service_address": form.get("service_address", "").strip(),
        "status": form.get("status", "active"),
        "trade_mix": form.get("trade_mix", "").strip(),
        "notes": form.get("notes", "").strip(),
    }


def _validate_customer_form(data):
    errors = []
    if not data["name"]:
        errors.append("Customer name is required.")
    if data["segment"] not in CUSTOMER_SEGMENTS:
        errors.append("Customer segment must be residential or commercial.")
    if not data["service_address"]:
        errors.append("Service address is required.")
    if data["status"] not in CUSTOMER_STATUSES:
        errors.append("Customer status is invalid.")
    return errors


def _customer_contact_form_data(form):
    return {
        "full_name": form.get("full_name", "").strip(),
        "role_label": form.get("role_label", "Primary contact").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "is_primary": _checkbox_value(form, "is_primary"),
        "notes": form.get("notes", "").strip(),
    }


def _validate_customer_contact_form(data):
    errors = []
    if not data["full_name"]:
        errors.append("Contact name is required.")
    if not data["role_label"]:
        errors.append("Contact role is required.")
    if not data["phone"] and not data["email"]:
        errors.append("Add at least a phone number or email for the contact.")
    return errors


def _lead_form_data(form):
    return {
        "customer_id": _optional_int(form.get("customer_id")),
        "source": form.get("source", "Referrals").strip(),
        "trade_interest": form.get("trade_interest", "").strip(),
        "stage": form.get("stage", "New Leads").strip(),
        "assigned_rep": form.get("assigned_rep", "").strip(),
        "inspection_date": _optional_date(form.get("inspection_date")),
        "estimated_value": _optional_float(form.get("estimated_value")),
        "is_commercial": _checkbox_value(form, "is_commercial"),
    }


def _validate_lead_form(data):
    errors = []
    if data["source"] not in LEAD_SOURCES:
        errors.append("Lead source is invalid.")
    if not data["trade_interest"]:
        errors.append("Trade interest is required.")
    if data["stage"] not in LEAD_STAGES:
        errors.append("Lead stage is invalid.")
    if not data["assigned_rep"]:
        errors.append("Assigned rep is required.")
    if data["estimated_value"] is None or data["estimated_value"] < 0:
        errors.append("Estimated value must be a positive number.")
    return errors


def _opportunity_form_data(form):
    return {
        "lead_id": _optional_int(form.get("lead_id")),
        "customer_id": _optional_int(form.get("customer_id")),
        "name": form.get("name", "").strip(),
        "subtitle": form.get("subtitle", "").strip(),
        "stage": form.get("stage", "New Leads").strip(),
        "close_date": _optional_date(form.get("close_date")),
        "value": _optional_float(form.get("value")),
        "priority": _optional_int(form.get("priority")),
        "trade_mix": form.get("trade_mix", "").strip(),
        "rep": form.get("rep", "").strip(),
    }


def _validate_opportunity_form(data):
    errors = []
    if not data["name"]:
        errors.append("Opportunity name is required.")
    if not data["subtitle"]:
        errors.append("Opportunity subtitle is required.")
    if data["stage"] not in OPPORTUNITY_STAGES:
        errors.append("Opportunity stage is invalid.")
    if not data["close_date"]:
        errors.append("Close date is required.")
    if data["value"] is None or data["value"] < 0:
        errors.append("Opportunity value must be a positive number.")
    if data["priority"] is None or not 0 <= data["priority"] <= 100:
        errors.append("Priority must be a number between 0 and 100.")
    if not data["trade_mix"]:
        errors.append("Trade mix is required.")
    if not data["rep"]:
        errors.append("Rep is required.")
    return errors


def _quote_form_data(form):
    return {
        "opportunity_id": _optional_int(form.get("opportunity_id")),
        "customer_id": _optional_int(form.get("customer_id")),
        "quote_number": form.get("quote_number", "").strip(),
        "option_name": form.get("option_name", "").strip(),
        "description": form.get("description", "").strip(),
        "amount": _optional_float(form.get("amount")),
        "estimated_cost": _optional_float(form.get("estimated_cost")),
        "deposit_required": _optional_float(form.get("deposit_required")),
        "deposit_received": _optional_float(form.get("deposit_received")),
        "status": form.get("status", "Draft").strip(),
        "signed_date": _optional_date(form.get("signed_date")),
        "issue_date": _optional_date(form.get("issue_date")),
        "expiration_date": _optional_date(form.get("expiration_date")),
    }


def _calculate_margin_pct(amount, estimated_cost):
    if amount in (None, 0) or estimated_cost is None:
        return 0
    return round(((amount - estimated_cost) / amount) * 100, 1)


def _validate_quote_form(data):
    errors = []
    if data["customer_id"] is None:
        errors.append("Customer is required for a quote.")
    if not data["quote_number"]:
        errors.append("Quote number is required.")
    if not data["option_name"]:
        errors.append("Quote title is required.")
    if not data["description"]:
        errors.append("Quote description is required.")
    if data["amount"] is None or data["amount"] < 0:
        errors.append("Quote amount must be a positive number.")
    if data["estimated_cost"] is None or data["estimated_cost"] < 0:
        errors.append("Estimated cost must be a positive number.")
    if data["amount"] is not None and data["estimated_cost"] is not None and data["estimated_cost"] > data["amount"]:
        errors.append("Estimated cost cannot exceed contract amount.")
    if data["deposit_required"] is None or data["deposit_required"] < 0:
        errors.append("Required deposit must be zero or a positive number.")
    if data["amount"] is not None and data["deposit_required"] is not None and data["deposit_required"] > data["amount"]:
        errors.append("Required deposit cannot exceed contract amount.")
    if data["deposit_received"] is None or data["deposit_received"] < 0:
        errors.append("Received deposit must be zero or a positive number.")
    if data["amount"] is not None and data["deposit_received"] is not None and data["deposit_received"] > data["amount"]:
        errors.append("Received deposit cannot exceed contract amount.")
    if data["status"] == "Approved" and not data["signed_date"]:
        errors.append("Approved contracts need a signed date.")
    if data["status"] not in QUOTE_STATUSES:
        errors.append("Quote status is invalid.")
    return errors


def _job_form_data(form):
    return {
        "opportunity_id": _optional_int(form.get("opportunity_id")),
        "quote_id": _optional_int(form.get("quote_id")),
        "customer_id": _optional_int(form.get("customer_id")),
        "name": form.get("name", "").strip(),
        "scope": form.get("scope", "").strip(),
        "status": form.get("status", "Sales handoff").strip(),
        "scheduled_start": _optional_date(form.get("scheduled_start")),
        "crew_name": form.get("crew_name", "").strip(),
        "committed_revenue": _optional_float(form.get("committed_revenue")),
    }


def _validate_job_form(data):
    errors = []
    if data["customer_id"] is None:
        errors.append("Customer is required for a job.")
    if not data["name"]:
        errors.append("Job name is required.")
    if not data["scope"]:
        errors.append("Job scope is required.")
    if data["status"] not in JOB_STATUSES:
        errors.append("Job status is invalid.")
    if data["committed_revenue"] is None or data["committed_revenue"] < 0:
        errors.append("Committed revenue must be a positive number.")
    return errors


def _invoice_form_data(form):
    return {
        "quote_id": _optional_int(form.get("quote_id")),
        "change_order_id": _optional_int(form.get("change_order_id")),
        "customer_id": _optional_int(form.get("customer_id")),
        "job_id": _optional_int(form.get("job_id")),
        "invoice_number": form.get("invoice_number", "").strip(),
        "billing_type": form.get("billing_type", "Standard").strip(),
        "application_number": form.get("application_number", "").strip(),
        "status": form.get("status", "Draft").strip(),
        "amount": _optional_float(form.get("amount")),
        "issued_date": _optional_date(form.get("issued_date")),
        "due_date": _optional_date(form.get("due_date")),
        "billing_period_start": _optional_date(form.get("billing_period_start")),
        "billing_period_end": _optional_date(form.get("billing_period_end")),
        "retainage_pct": _optional_float(form.get("retainage_pct", "0")),
        "retainage_held": _optional_float(form.get("retainage_held", "0")),
        "remaining_balance": _optional_float(form.get("remaining_balance")),
    }


def _validate_invoice_form(data):
    errors = []
    if data["customer_id"] is None:
        errors.append("Customer is required for an invoice.")
    if not data["invoice_number"]:
        errors.append("Invoice number is required.")
    if data["billing_type"] not in INVOICE_BILLING_TYPES:
        errors.append("Billing type is invalid.")
    if data["status"] not in INVOICE_STATUSES:
        errors.append("Invoice status is invalid.")
    if data["amount"] is None or data["amount"] < 0:
        errors.append("Invoice amount must be a positive number.")
    if not data["due_date"]:
        errors.append("Invoice due date is required.")
    if data["billing_period_start"] and data["billing_period_end"] and data["billing_period_end"] < data["billing_period_start"]:
        errors.append("Billing period end cannot be before the billing period start.")
    if data["retainage_pct"] is None or data["retainage_pct"] < 0 or data["retainage_pct"] > 100:
        errors.append("Retainage percent must be between 0 and 100.")
    if data["retainage_held"] is None or data["retainage_held"] < 0:
        errors.append("Retainage held must be zero or a positive number.")
    if data["remaining_balance"] is None or data["remaining_balance"] < 0:
        errors.append("Remaining balance must be zero or a positive number.")
    if data["amount"] is not None and data["retainage_held"] is not None and data["retainage_held"] > data["amount"]:
        errors.append("Retainage held cannot exceed the invoice amount.")
    if data["amount"] is not None and data["remaining_balance"] is not None and data["remaining_balance"] > data["amount"]:
        errors.append("Remaining balance cannot exceed invoice amount.")
    return errors


def _change_order_form_data(form):
    return {
        "change_number": form.get("change_number", "").strip(),
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "status": form.get("status", "Draft").strip(),
        "requested_date": _optional_date(form.get("requested_date")),
        "approved_date": _optional_date(form.get("approved_date")),
        "amount": _optional_float(form.get("amount")),
        "cost_impact": _optional_float(form.get("cost_impact")),
        "schedule_days": _optional_int(form.get("schedule_days")),
        "owner_name": form.get("owner_name", "").strip(),
        "is_billable": _checkbox_value(form, "is_billable"),
        "notes": form.get("notes", "").strip(),
    }


def _validate_change_order_form(data):
    errors = []
    if not data["change_number"]:
        errors.append("Change order number is required.")
    if not data["title"]:
        errors.append("Change order title is required.")
    if not data["description"]:
        errors.append("Change order description is required.")
    if data["status"] not in CHANGE_ORDER_STATUSES:
        errors.append("Change order status is invalid.")
    if not data["requested_date"]:
        errors.append("Requested date is required.")
    if data["status"] in ("Approved", "Invoiced") and not data["approved_date"]:
        errors.append("Approved or invoiced change orders need an approved date.")
    if data["approved_date"] and data["requested_date"] and data["approved_date"] < data["requested_date"]:
        errors.append("Approved date cannot be before the requested date.")
    if data["amount"] is None:
        errors.append("Change order amount is required.")
    elif data["amount"] < 0:
        errors.append("Change order amount must be zero or a positive number.")
    if data["cost_impact"] is None:
        errors.append("Cost impact is required.")
    elif data["cost_impact"] < 0:
        errors.append("Cost impact must be zero or a positive number.")
    if data["schedule_days"] is None:
        errors.append("Schedule impact days are required.")
    elif data["schedule_days"] < 0:
        errors.append("Schedule impact days must be zero or a positive number.")
    if not data["owner_name"]:
        errors.append("Change order owner is required.")
    if data["status"] == "Invoiced" and not data["is_billable"]:
        errors.append("Only billable change orders can move to invoiced status.")
    if not data["notes"]:
        errors.append("Add field notes for this change order.")
    return errors


def _job_document_form_data(form):
    return {
        "record_type": form.get("record_type", "Photo").strip(),
        "title": form.get("title", "").strip(),
        "file_reference": form.get("file_reference", "").strip(),
        "captured_at": _optional_datetime(form.get("captured_at")),
        "owner_name": form.get("owner_name", "").strip(),
        "status": form.get("status", "Logged").strip(),
        "notes": form.get("notes", "").strip(),
    }


def _validate_job_document_form(data, upload=None):
    errors = []
    if data["record_type"] not in JOB_DOCUMENT_TYPES:
        errors.append("Field record type is invalid.")
    if not data["title"]:
        errors.append("Field record title is required.")
    if not data["captured_at"]:
        errors.append("Captured date and time are required.")
    if not data["owner_name"]:
        errors.append("Field record owner is required.")
    if data["status"] not in JOB_DOCUMENT_STATUSES:
        errors.append("Field record status is invalid.")
    if upload is not None and (upload.filename or "").strip() and not _is_allowed_job_document_upload(upload.filename):
        errors.append("Uploaded file type is not supported for job documents.")
    if not data["notes"]:
        errors.append("Add field notes for this record.")
    return errors


def _inventory_form_data(form):
    return {
        "vendor_id": _optional_int(form.get("vendor_id")),
        "sku": form.get("sku", "").strip(),
        "item_name": form.get("item_name", "").strip(),
        "category": form.get("category", "Roofing").strip(),
        "stock_on_hand": _optional_float(form.get("stock_on_hand")),
        "unit_cost": _optional_float(form.get("unit_cost")),
        "unit_price": _optional_float(form.get("unit_price")),
        "status": form.get("status", "Healthy").strip(),
    }


def _validate_inventory_form(data, current_reserved_qty=0):
    errors = []
    if not data["sku"]:
        errors.append("SKU is required.")
    if not data["item_name"]:
        errors.append("Item name is required.")
    if data["category"] not in INVENTORY_CATEGORIES:
        errors.append("Inventory category is invalid.")
    if data["stock_on_hand"] is None or data["stock_on_hand"] < 0:
        errors.append("Stock on hand must be zero or a positive number.")
    if data["stock_on_hand"] is not None and data["stock_on_hand"] < current_reserved_qty:
        errors.append("Stock on hand cannot be set below the quantity already reserved to jobs.")
    if data["unit_cost"] is None or data["unit_cost"] < 0:
        errors.append("Unit cost must be zero or a positive number.")
    if data["unit_price"] is None or data["unit_price"] < 0:
        errors.append("Unit price must be zero or a positive number.")
    if data["status"] not in INVENTORY_STATUSES:
        errors.append("Inventory status is invalid.")
    return errors


def _material_form_data(form):
    return {
        "inventory_item_id": _optional_int(form.get("inventory_item_id")),
        "requested_qty": _optional_float(form.get("requested_qty")),
        "notes": form.get("notes", "").strip(),
        "auto_purchase": _checkbox_value(form, "auto_purchase"),
        "purchase_priority": form.get("purchase_priority", "high").strip(),
    }


def _validate_material_form(data):
    errors = []
    if data["inventory_item_id"] is None:
        errors.append("Select an inventory item to reserve.")
    if data["requested_qty"] is None or data["requested_qty"] <= 0:
        errors.append("Requested quantity must be greater than zero.")
    if data["purchase_priority"] not in PURCHASE_PRIORITIES:
        errors.append("Purchase priority is invalid.")
    return errors


def _delivery_form_data(form):
    return {
        "job_id": _optional_int(form.get("job_id")),
        "route_name": form.get("route_name", "").strip(),
        "truck_name": form.get("truck_name", "").strip(),
        "eta": _optional_datetime(form.get("eta")),
        "status": form.get("status", "Scheduled").strip(),
        "load_percent": _optional_int(form.get("load_percent")),
        "notes": form.get("notes", "").strip(),
    }


def _validate_delivery_form(data):
    errors = []
    if data["job_id"] is None:
        errors.append("Job is required for dispatch scheduling.")
    if not data["route_name"]:
        errors.append("Route name is required.")
    if not data["truck_name"]:
        errors.append("Truck name is required.")
    if not data["eta"]:
        errors.append("ETA is required.")
    if data["status"] not in DELIVERY_STATUSES:
        errors.append("Delivery status is invalid.")
    if data["load_percent"] is None or not 0 <= data["load_percent"] <= 100:
        errors.append("Load percent must be between 0 and 100.")
    if not data["notes"]:
        errors.append("Dispatch notes are required.")
    return errors


def _purchase_request_form_data(form):
    ordered_qty = _optional_float(form.get("ordered_qty"))
    received_qty = _optional_float(form.get("received_qty"))
    return {
        "vendor_id": _optional_int(form.get("vendor_id")),
        "job_id": _optional_int(form.get("job_id")),
        "job_material_id": _optional_int(form.get("job_material_id")),
        "inventory_item_id": _optional_int(form.get("inventory_item_id")),
        "title": form.get("title", "").strip(),
        "details": form.get("details", "").strip(),
        "requested_qty": _optional_float(form.get("requested_qty")),
        "ordered_qty": ordered_qty if ordered_qty is not None else 0,
        "received_qty": received_qty if received_qty is not None else 0,
        "priority": form.get("priority", "medium").strip(),
        "status": form.get("status", "Open").strip(),
        "owner_name": form.get("owner_name", "").strip(),
        "needed_by": _optional_date(form.get("needed_by")),
        "eta_date": _optional_date(form.get("eta_date")),
        "vendor_notes": form.get("vendor_notes", "").strip(),
    }


def _validate_purchase_request_form(data):
    errors = []
    if not data["title"]:
        errors.append("Request title is required.")
    if not data["details"]:
        errors.append("Request details are required.")
    if data["requested_qty"] is not None and data["requested_qty"] < 0:
        errors.append("Requested quantity must be zero or a positive number.")
    if data["ordered_qty"] is None or data["ordered_qty"] < 0:
        errors.append("Ordered quantity must be zero or a positive number.")
    if data["received_qty"] is None or data["received_qty"] < 0:
        errors.append("Received quantity must be zero or a positive number.")
    if data["ordered_qty"] is not None and data["received_qty"] is not None and data["received_qty"] > data["ordered_qty"]:
        errors.append("Received quantity cannot exceed ordered quantity.")
    if data["priority"] not in PURCHASE_PRIORITIES:
        errors.append("Purchase request priority is invalid.")
    if data["status"] not in PURCHASE_REQUEST_STATUSES:
        errors.append("Purchase request status is invalid.")
    if not data["owner_name"]:
        errors.append("Purchase request owner is required.")
    if not data["vendor_notes"]:
        errors.append("Vendor follow-up notes are required.")
    return errors


def _job_cost_form_data(form):
    quantity = _optional_float(form.get("quantity"))
    unit_cost = _optional_float(form.get("unit_cost"))
    total_cost = round(quantity * unit_cost, 2) if quantity is not None and unit_cost is not None else None
    return {
        "vendor_id": _optional_int(form.get("vendor_id")),
        "cost_code": form.get("cost_code", "Material").strip(),
        "source_type": form.get("source_type", "Material").strip(),
        "description": form.get("description", "").strip(),
        "quantity": quantity,
        "unit_cost": unit_cost,
        "total_cost": total_cost,
        "cost_date": _optional_date(form.get("cost_date")),
        "status": form.get("status", "Committed").strip(),
        "notes": form.get("notes", "").strip(),
    }


def _validate_job_cost_form(data):
    errors = []
    if data["cost_code"] not in JOB_COST_SOURCE_TYPES:
        errors.append("Cost code is invalid.")
    if data["source_type"] not in JOB_COST_SOURCE_TYPES:
        errors.append("Cost source type is invalid.")
    if not data["description"]:
        errors.append("Cost description is required.")
    if data["quantity"] is None or data["quantity"] <= 0:
        errors.append("Quantity must be greater than zero.")
    if data["unit_cost"] is None or data["unit_cost"] < 0:
        errors.append("Unit cost must be zero or a positive number.")
    if data["total_cost"] is None or data["total_cost"] < 0:
        errors.append("Total cost must be zero or a positive number.")
    if not data["cost_date"]:
        errors.append("Cost date is required.")
    if data["status"] not in JOB_COST_STATUSES:
        errors.append("Cost status is invalid.")
    if not data["notes"]:
        errors.append("Cost notes are required.")
    return errors


def _note_form_data(form):
    return {
        "title": form.get("title", "").strip(),
        "details": form.get("details", "").strip(),
        "activity_type": form.get("activity_type", "Note").strip(),
    }


def _validate_note_form(data):
    errors = []
    if data["activity_type"] not in ACTIVITY_TYPES:
        errors.append("Activity type is invalid.")
    if not data["title"]:
        errors.append("Note title is required.")
    if not data["details"]:
        errors.append("Note details are required.")
    return errors


def _task_form_data(form):
    return {
        "title": form.get("title", "").strip(),
        "module_name": form.get("module_name", "Customer 360").strip(),
        "owner_name": form.get("owner_name", "").strip(),
        "due_date": _optional_date(form.get("due_date")),
        "reminder_at": _optional_datetime(form.get("reminder_at")),
        "status": form.get("status", "open").strip(),
        "priority": form.get("priority", "medium").strip(),
        "details": form.get("details", "").strip(),
    }


def _validate_task_form(data):
    errors = []
    if not data["title"]:
        errors.append("Task title is required.")
    if data["module_name"] not in TASK_MODULES:
        errors.append("Task module is invalid.")
    if not data["owner_name"]:
        errors.append("Task owner is required.")
    if not data["due_date"]:
        errors.append("Task due date is required.")
    if data["status"] not in TASK_STATUSES:
        errors.append("Task status is invalid.")
    if data["priority"] not in TASK_PRIORITIES:
        errors.append("Task priority is invalid.")
    if not data["details"]:
        errors.append("Task details are required.")
    return errors


def _email_form_data(form):
    return {
        "direction": form.get("direction", "Outbound").strip(),
        "contact_email": form.get("contact_email", "").strip(),
        "subject": form.get("subject", "").strip(),
        "body": form.get("body", "").strip(),
        "owner_name": form.get("owner_name", "").strip(),
        "status": form.get("status", "Sent").strip(),
        "sent_at": _optional_datetime(form.get("sent_at")),
        "integration_status": form.get("integration_status", "Manual log").strip(),
    }


def _validate_email_form(data):
    errors = []
    if data["direction"] not in EMAIL_DIRECTIONS:
        errors.append("Email direction is invalid.")
    if not data["contact_email"]:
        errors.append("Contact email is required.")
    if "@" not in data["contact_email"]:
        errors.append("Contact email must be a valid email address.")
    if not data["subject"]:
        errors.append("Email subject is required.")
    if not data["body"]:
        errors.append("Email body is required.")
    if not data["owner_name"]:
        errors.append("Email owner is required.")
    if data["status"] not in EMAIL_STATUSES:
        errors.append("Email status is invalid.")
    if not data["sent_at"]:
        errors.append("Email date and time are required.")
    if data["integration_status"] not in INTEGRATION_STATUSES:
        errors.append("Integration status is invalid.")
    return errors


def _calendar_form_data(form):
    return {
        "title": form.get("title", "").strip(),
        "event_type": form.get("event_type", "Call").strip(),
        "starts_at": _optional_datetime(form.get("starts_at")),
        "ends_at": _optional_datetime(form.get("ends_at")),
        "owner_name": form.get("owner_name", "").strip(),
        "location": form.get("location", "").strip(),
        "status": form.get("status", "Planned").strip(),
        "notes": form.get("notes", "").strip(),
        "integration_status": form.get("integration_status", "Manual log").strip(),
    }


def _validate_calendar_form(data):
    errors = []
    if not data["title"]:
        errors.append("Calendar title is required.")
    if data["event_type"] not in CALENDAR_EVENT_TYPES:
        errors.append("Calendar event type is invalid.")
    if not data["starts_at"]:
        errors.append("Calendar start date and time are required.")
    if data["ends_at"] and data["starts_at"] and data["ends_at"] < data["starts_at"]:
        errors.append("Calendar end time cannot be before the start time.")
    if not data["owner_name"]:
        errors.append("Calendar owner is required.")
    if not data["location"]:
        errors.append("Calendar location is required.")
    if data["status"] not in CALENDAR_EVENT_STATUSES:
        errors.append("Calendar status is invalid.")
    if not data["notes"]:
        errors.append("Calendar notes are required.")
    if data["integration_status"] not in INTEGRATION_STATUSES:
        errors.append("Integration status is invalid.")
    return errors


def _fetch_customer(customer_id):
    return get_db().execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()


def _fetch_customer_contact(contact_id):
    return get_db().execute("SELECT * FROM customer_contacts WHERE id = ?", (contact_id,)).fetchone()


def _fetch_lead(lead_id):
    return get_db().execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def _fetch_opportunity(opportunity_id):
    return get_db().execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()


def _fetch_quote(quote_id):
    return get_db().execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()


def _fetch_job(job_id):
    return get_db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def _fetch_change_order(change_order_id):
    return get_db().execute("SELECT * FROM change_orders WHERE id = ?", (change_order_id,)).fetchone()


def _fetch_invoice(invoice_id):
    return get_db().execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()


def _fetch_inventory_item(item_id):
    return get_db().execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()


def _fetch_job_material(material_id):
    return get_db().execute("SELECT * FROM job_materials WHERE id = ?", (material_id,)).fetchone()


def _fetch_job_document(document_id):
    return get_db().execute("SELECT * FROM job_documents WHERE id = ?", (document_id,)).fetchone()


def _fetch_delivery(delivery_id):
    return get_db().execute("SELECT * FROM deliveries WHERE id = ?", (delivery_id,)).fetchone()


def _fetch_purchase_request(request_id):
    return get_db().execute("SELECT * FROM purchase_requests WHERE id = ?", (request_id,)).fetchone()


def _fetch_job_cost_entry(cost_id):
    return get_db().execute("SELECT * FROM job_cost_entries WHERE id = ?", (cost_id,)).fetchone()


def _fetch_task(task_id):
    return get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def _fetch_email_message(message_id):
    return get_db().execute("SELECT * FROM email_messages WHERE id = ?", (message_id,)).fetchone()


def _fetch_calendar_event(event_id):
    return get_db().execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,)).fetchone()


def _opportunity_choices():
    return get_db().execute(
        """
        SELECT id, name, subtitle, customer_id
        FROM opportunities
        ORDER BY priority DESC, close_date ASC
        """
    ).fetchall()


def _quote_choices():
    return get_db().execute(
        """
        SELECT q.id, q.quote_number, q.option_name, q.amount, c.name AS customer_name
        FROM quotes q
        JOIN customers c ON c.id = q.customer_id
        ORDER BY q.id DESC
        """
    ).fetchall()


def _job_choices():
    return get_db().execute(
        """
        SELECT j.id, j.name, j.scope, c.name AS customer_name
        FROM jobs j
        JOIN customers c ON c.id = j.customer_id
        ORDER BY j.id DESC
        """
    ).fetchall()


def _change_order_choices(job_id=None, customer_id=None, approved_only=False, billable_only=False):
    params = []
    conditions = []
    sql = """
        SELECT co.id, co.change_number, co.title, co.amount, co.status, co.is_billable,
               j.name AS job_name, c.name AS customer_name
        FROM change_orders co
        JOIN jobs j ON j.id = co.job_id
        JOIN customers c ON c.id = co.customer_id
    """
    if job_id is not None:
        conditions.append("co.job_id = ?")
        params.append(job_id)
    if customer_id is not None:
        conditions.append("co.customer_id = ?")
        params.append(customer_id)
    if approved_only:
        conditions.append("co.status IN ('Approved', 'Invoiced')")
    if billable_only:
        conditions.append("co.is_billable = 1")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY co.id DESC"
    return get_db().execute(sql, params).fetchall()


def _vendor_choices():
    return get_db().execute(
        """
        SELECT id, name, category
        FROM vendors
        ORDER BY name
        """
    ).fetchall()


def _bank_account_choices():
    return get_db().execute(
        """
        SELECT id, account_name, account_type
        FROM bank_accounts
        ORDER BY account_name
        """
    ).fetchall()


def _inventory_item_choices():
    return get_db().execute(
        """
        SELECT i.id, i.sku, i.item_name, i.category, i.stock_on_hand, i.reserved_qty,
               v.name AS vendor_name
        FROM inventory_items i
        LEFT JOIN vendors v ON v.id = i.vendor_id
        ORDER BY i.category, i.item_name
        """
    ).fetchall()


def _next_document_number(prefix, table_name, column_name):
    row = get_db().execute(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {table_name}").fetchone()
    return f"{prefix}-{1000 + row['max_id'] + 1}"


def _compute_invoice_aging_bucket(due_date, remaining_balance):
    if remaining_balance <= 0:
        return "Paid"
    if not due_date:
        return "Current"

    days_past_due = (datetime.now().date() - datetime.fromisoformat(due_date).date()).days
    if days_past_due <= 0:
        return "Current"
    if days_past_due <= 30:
        return "1-30 days"
    if days_past_due <= 60:
        return "31-60 days"
    return "60+ days"


def _job_execution_snapshot(job_id):
    db = get_db()
    change_order_snapshot = db.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN status = 'Approved' AND is_billable = 1 THEN amount ELSE 0 END), 0) AS approved_revenue,
               COALESCE(SUM(CASE WHEN status = 'Approved' THEN cost_impact ELSE 0 END), 0) AS approved_cost_impact,
               COALESCE(SUM(CASE WHEN status IN ('Draft', 'Pending Approval') THEN 1 ELSE 0 END), 0) AS open_count,
               COUNT(*) AS total_count
        FROM change_orders
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()
    document_snapshot = db.execute(
        """
        SELECT COUNT(*) AS total_count,
               COALESCE(SUM(CASE WHEN status IN ('Logged', 'Pending Review') THEN 1 ELSE 0 END), 0) AS open_count
        FROM job_documents
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()
    return {
        "approved_change_revenue": change_order_snapshot["approved_revenue"],
        "approved_change_cost": change_order_snapshot["approved_cost_impact"],
        "open_change_orders": change_order_snapshot["open_count"],
        "change_order_count": change_order_snapshot["total_count"],
        "field_record_count": document_snapshot["total_count"],
        "open_field_records": document_snapshot["open_count"],
    }


def _serialize_snapshot(record):
    snapshot = {}
    for key in record.keys():
        value = record[key]
        if isinstance(value, datetime):
            snapshot[key] = value.isoformat(sep=" ")
        else:
            snapshot[key] = value
    return json.dumps(snapshot, sort_keys=True)


def _record_change_order_version(change_order_id, changed_by, change_summary):
    db = get_db()
    change_order = _fetch_change_order(change_order_id)
    if change_order is None:
        return

    next_version = db.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM change_order_versions WHERE change_order_id = ?",
        (change_order_id,),
    ).fetchone()["next_version"]
    db.execute(
        """
        INSERT INTO change_order_versions (
            branch_id, change_order_id, version_number, changed_at, changed_by, change_summary, snapshot_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            change_order_id,
            next_version,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            changed_by,
            change_summary,
            _serialize_snapshot(change_order),
        ),
    )


def _change_order_version_history(change_order_id):
    rows = get_db().execute(
        """
        SELECT *
        FROM change_order_versions
        WHERE change_order_id = ?
        ORDER BY version_number DESC, id DESC
        """,
        (change_order_id,),
    ).fetchall()
    history = []
    for row in rows:
        item = dict(row)
        item["snapshot"] = json.loads(item["snapshot_json"])
        history.append(item)
    return history


def _job_document_upload_dir():
    upload_dir = Path(current_app.config["JOB_DOCUMENT_UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _is_allowed_job_document_upload(filename):
    suffix = Path(filename or "").suffix.lower()
    return suffix in JOB_DOCUMENT_UPLOAD_EXTENSIONS


def _save_job_document_upload(upload, job_id):
    filename = (upload.filename or "").strip()
    if not filename:
        return None, None

    safe_name = secure_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    stored_file_name = f"job-{job_id}-{uuid4().hex}{suffix}"
    upload.save(_job_document_upload_dir() / stored_file_name)
    return stored_file_name, filename


def _remove_job_document_upload(document):
    stored_file_name = document["stored_file_name"] if document is not None else None
    if not stored_file_name:
        return

    file_path = _job_document_upload_dir() / stored_file_name
    if file_path.exists():
        file_path.unlink()


def _create_activity(customer_id, activity_type, owner_name, title, details, activity_date=None):
    get_db().execute(
        """
        INSERT INTO activity_feed (
            branch_id, customer_id, activity_date, activity_type, owner_name, title, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            customer_id,
            activity_date or datetime.now().strftime("%Y-%m-%d %H:%M"),
            activity_type,
            owner_name,
            title,
            details,
        ),
    )


def _upsert_primary_customer_contact(customer_id, customer_name, data):
    contact_name = data["primary_contact"].strip()
    if not any((contact_name, data["phone"], data["email"])):
        return
    contact_name = contact_name or customer_name

    db = get_db()
    existing = db.execute(
        """
        SELECT id
        FROM customer_contacts
        WHERE customer_id = ? AND is_primary = 1
        ORDER BY id
        LIMIT 1
        """,
        (customer_id,),
    ).fetchone()

    if existing is None:
        db.execute(
            """
            INSERT INTO customer_contacts (
                branch_id, customer_id, full_name, role_label, phone, email, is_primary, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                customer_id,
                contact_name,
                "Primary contact",
                data["phone"],
                data["email"],
                1,
                "Synced from the customer profile.",
            ),
        )
        return

    db.execute(
        """
        UPDATE customer_contacts
        SET full_name = ?, role_label = ?, phone = ?, email = ?, is_primary = 1
        WHERE id = ?
        """,
        (contact_name, "Primary contact", data["phone"], data["email"], existing["id"]),
    )


def _sync_job_operations_status(job_id):
    job = _fetch_job(job_id)
    if job is None or job["status"] in {"In progress", "Completed", "Cancelled"}:
        return

    db = get_db()
    reserved_total = db.execute(
        "SELECT COALESCE(SUM(reserved_qty), 0) AS total FROM job_materials WHERE job_id = ?",
        (job_id,),
    ).fetchone()["total"]
    active_deliveries = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM deliveries
        WHERE job_id = ? AND status IN ('Scheduled', 'Loading', 'En route', 'Delayed')
        """,
        (job_id,),
    ).fetchone()["count"]
    delivered_deliveries = db.execute(
        "SELECT COUNT(*) AS count FROM deliveries WHERE job_id = ? AND status = 'Delivered'",
        (job_id,),
    ).fetchone()["count"]

    new_status = "Scheduled" if job["scheduled_start"] else "Sales handoff"
    if reserved_total > 0:
        new_status = "Materials reserved"
    if delivered_deliveries > 0:
        new_status = "Ready for production"
    if active_deliveries > 0:
        new_status = "Delivery pending"

    if new_status != job["status"]:
        db.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))


def _create_shortage_purchase_request(job, item, job_material_id, shortage_qty, priority):
    db = get_db()
    title = f"{job['name']} shortage / {item['sku']}"
    details = (
        f"{item['item_name']} short by {shortage_qty:,.2f} for job '{job['name']}'. "
        f"Reserve or source additional stock before delivery scheduling."
    )
    owner_name = g.user["full_name"] if g.get("user") else "Inventory Desk"
    db.execute(
        """
        INSERT INTO purchase_requests (
            branch_id, vendor_id, job_id, job_material_id, inventory_item_id, title, details,
            requested_qty, ordered_qty, received_qty, priority, status, owner_name, needed_by,
            eta_date, vendor_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            item["vendor_id"],
            job["id"],
            job_material_id,
            item["id"],
            title,
            details,
            shortage_qty,
            0,
            0,
            priority,
            "Open",
            owner_name,
            job["scheduled_start"],
            job["scheduled_start"],
            "Auto-created from job shortage. Confirm vendor availability and ETA.",
        ),
    )


@bp.get("/")
def home():
    return redirect(url_for("crm.dashboard"))


@bp.get("/dashboard")
@roles_required(*ALL_APP_ROLES)
def dashboard():
    payload = build_bootstrap_payload()
    db = get_db()
    role_snapshot = {
        "customers": db.execute("SELECT COUNT(*) AS count FROM customers").fetchone()["count"],
        "leads": db.execute("SELECT COUNT(*) AS count FROM leads").fetchone()["count"],
        "opportunities": db.execute("SELECT COUNT(*) AS count FROM opportunities").fetchone()["count"],
        "quotes": db.execute("SELECT COUNT(*) AS count FROM quotes").fetchone()["count"],
        "jobs": db.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"],
        "invoices": db.execute("SELECT COUNT(*) AS count FROM invoices").fetchone()["count"],
        "deliveries": db.execute("SELECT COUNT(*) AS count FROM deliveries").fetchone()["count"],
        "inventory_items": db.execute("SELECT COUNT(*) AS count FROM inventory_items").fetchone()["count"],
        "materials": db.execute("SELECT COUNT(*) AS count FROM job_materials").fetchone()["count"],
        "users": db.execute("SELECT COUNT(*) AS count FROM users WHERE is_active = 1").fetchone()["count"],
    }
    return render_template(
        "dashboard.html",
        overview_metrics=payload["overviewMetrics"],
        dashboard=payload["dashboard"],
        role_snapshot=role_snapshot,
    )


@bp.get("/workboard")
@roles_required(*ALL_APP_ROLES)
def workboard():
    today = datetime.now().date().isoformat()
    next_week = (datetime.now().date() + timedelta(days=7)).isoformat()
    db = get_db()
    tasks = db.execute(
        """
        SELECT t.*, c.name AS customer_name
        FROM tasks t
        LEFT JOIN customers c ON c.id = t.customer_id
        WHERE t.status IN ('open', 'scheduled')
        ORDER BY CASE
            WHEN t.due_date < ? THEN 0
            WHEN t.due_date = ? THEN 1
            ELSE 2
        END,
        CASE t.priority
            WHEN 'high' THEN 0
            WHEN 'medium' THEN 1
            ELSE 2
        END,
        t.due_date,
        t.id DESC
        LIMIT 12
        """,
        (today, today),
    ).fetchall()
    installs = db.execute(
        """
        SELECT j.id, j.name, j.status, j.scheduled_start, j.crew_name, c.id AS customer_id, c.name AS customer_name,
               (SELECT COALESCE(SUM(jm.reserved_qty), 0) FROM job_materials jm WHERE jm.job_id = j.id) AS reserved_qty,
               (SELECT COUNT(*) FROM deliveries d WHERE d.job_id = j.id AND d.status IN ('Scheduled', 'Loading', 'En route', 'Delayed')) AS active_deliveries,
               (SELECT COUNT(*) FROM purchase_requests pr WHERE pr.job_id = j.id AND pr.status IN ('Open', 'Quoted', 'Ordered')) AS open_purchase_requests
        FROM jobs j
        JOIN customers c ON c.id = j.customer_id
        WHERE j.status NOT IN ('Completed', 'Cancelled')
        ORDER BY j.scheduled_start IS NULL, j.scheduled_start, j.id DESC
        LIMIT 10
        """
    ).fetchall()
    collections = db.execute(
        """
        SELECT i.id, i.invoice_number, i.status, i.amount, i.remaining_balance, i.due_date, i.aging_bucket,
               c.id AS customer_id, c.name AS customer_name, j.name AS job_name
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN jobs j ON j.id = i.job_id
        WHERE i.remaining_balance > 0
        ORDER BY CASE i.aging_bucket
            WHEN '60+ days' THEN 0
            WHEN '31-60 days' THEN 1
            WHEN '1-30 days' THEN 2
            ELSE 3
        END, i.due_date, i.id DESC
        LIMIT 10
        """
    ).fetchall()
    purchasing = db.execute(
        """
        SELECT pr.*, v.name AS vendor_name, j.name AS job_name, c.id AS customer_id,
               c.name AS customer_name, i.item_name, i.sku
        FROM purchase_requests pr
        LEFT JOIN vendors v ON v.id = pr.vendor_id
        LEFT JOIN jobs j ON j.id = pr.job_id
        LEFT JOIN customers c ON c.id = j.customer_id
        LEFT JOIN inventory_items i ON i.id = pr.inventory_item_id
        WHERE pr.status IN ('Open', 'Quoted', 'Ordered')
        ORDER BY CASE pr.priority
            WHEN 'high' THEN 0
            WHEN 'medium' THEN 1
            ELSE 2
        END, pr.needed_by IS NULL, pr.needed_by, pr.id DESC
        LIMIT 10
        """
    ).fetchall()
    summary = {
        "overdue_tasks": db.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE status IN ('open', 'scheduled') AND due_date < ?",
            (today,),
        ).fetchone()["count"],
        "installs_this_week": db.execute(
            """
            SELECT COUNT(*) AS count
            FROM jobs
            WHERE scheduled_start IS NOT NULL
              AND scheduled_start >= ?
              AND scheduled_start <= ?
              AND status NOT IN ('Completed', 'Cancelled')
            """,
            (today, next_week),
        ).fetchone()["count"],
        "past_due_ar": db.execute(
            "SELECT COUNT(*) AS count FROM invoices WHERE remaining_balance > 0 AND due_date < ?",
            (today,),
        ).fetchone()["count"],
        "open_shortages": db.execute(
            "SELECT COUNT(*) AS count FROM purchase_requests WHERE status IN ('Open', 'Quoted', 'Ordered')",
        ).fetchone()["count"],
    }
    return render_template(
        "workboard.html",
        summary=summary,
        tasks=tasks,
        installs=installs,
        collections=collections,
        purchasing=purchasing,
        today=today,
    )


@bp.get("/customers")
@roles_required(*CRM_ROLES)
def customers_index():
    query = request.args.get("q", "").strip()
    params = []
    sql = """
        SELECT c.*,
               (SELECT COUNT(*) FROM leads l WHERE l.customer_id = c.id) AS lead_count,
               (SELECT COUNT(*) FROM opportunities o WHERE o.customer_id = c.id) AS opportunity_count,
               (SELECT COUNT(*) FROM tasks t WHERE t.customer_id = c.id AND t.status IN ('open', 'scheduled')) AS open_task_count
        FROM customers c
    """

    if query:
        sql += """
            WHERE c.name LIKE ?
               OR c.primary_contact LIKE ?
               OR c.service_address LIKE ?
               OR EXISTS (
                    SELECT 1
                    FROM customer_contacts cc
                    WHERE cc.customer_id = c.id
                      AND (cc.full_name LIKE ? OR cc.email LIKE ? OR cc.phone LIKE ?)
               )
        """
        like_value = f"%{query}%"
        params.extend([like_value, like_value, like_value, like_value, like_value, like_value])

    sql += " ORDER BY c.name"
    customers = get_db().execute(sql, params).fetchall()

    return render_template(
        "customers/index.html",
        customers=customers,
        query=query,
    )


@bp.get("/customers/<int:customer_id>")
@roles_required(*ALL_APP_ROLES)
def customers_detail(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    db = get_db()
    summary = {
        "contacts": db.execute("SELECT COUNT(*) AS count FROM customer_contacts WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "leads": db.execute("SELECT COUNT(*) AS count FROM leads WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "opportunities": db.execute("SELECT COUNT(*) AS count FROM opportunities WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "quotes": db.execute("SELECT COUNT(*) AS count FROM quotes WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "jobs": db.execute("SELECT COUNT(*) AS count FROM jobs WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "change_orders": db.execute("SELECT COUNT(*) AS count FROM change_orders WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "field_records": db.execute("SELECT COUNT(*) AS count FROM job_documents WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "invoices": db.execute("SELECT COUNT(*) AS count FROM invoices WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "open_tasks": db.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE customer_id = ? AND status IN ('open', 'scheduled')",
            (customer_id,),
        ).fetchone()["count"],
        "reminders_due": db.execute(
            """
            SELECT COUNT(*) AS count
            FROM tasks
            WHERE customer_id = ? AND reminder_at IS NOT NULL AND status IN ('open', 'scheduled')
            """,
            (customer_id,),
        ).fetchone()["count"],
        "open_balance": db.execute(
            "SELECT COALESCE(SUM(remaining_balance), 0) AS total FROM invoices WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()["total"],
    }
    contacts = db.execute(
        """
        SELECT id, full_name, role_label, phone, email, is_primary, notes
        FROM customer_contacts
        WHERE customer_id = ?
        ORDER BY is_primary DESC, full_name
        """,
        (customer_id,),
    ).fetchall()

    leads = db.execute(
        """
        SELECT id, source, trade_interest, stage, assigned_rep, inspection_date, estimated_value
        FROM leads
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    opportunities = db.execute(
        """
        SELECT id, name, subtitle, stage, close_date, value, priority, rep
        FROM opportunities
        WHERE customer_id = ?
        ORDER BY priority DESC, close_date ASC
        """,
        (customer_id,),
    ).fetchall()
    quotes = db.execute(
        """
        SELECT id, quote_number, option_name, description, status, amount, issue_date, expiration_date
        FROM quotes
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    jobs = db.execute(
        """
        SELECT j.id, j.name, j.status, j.scheduled_start, j.crew_name, j.committed_revenue,
               (SELECT COUNT(*) FROM deliveries d WHERE d.job_id = j.id) AS delivery_count
        FROM jobs j
        WHERE j.customer_id = ?
        ORDER BY j.id DESC
        """,
        (customer_id,),
    ).fetchall()
    invoices = db.execute(
        """
        SELECT id, invoice_number, billing_type, application_number, status, amount, due_date, remaining_balance, retainage_held
        FROM invoices
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    deliveries = db.execute(
        """
        SELECT d.id, d.route_name, d.truck_name, d.eta, d.status, j.name AS job_name
        FROM deliveries d
        LEFT JOIN jobs j ON j.id = d.job_id
        WHERE j.customer_id = ?
        ORDER BY d.eta DESC
        """,
        (customer_id,),
    ).fetchall()
    change_orders = db.execute(
        """
        SELECT co.id, co.job_id, co.change_number, co.title, co.status, co.amount, co.approved_date,
               co.owner_name, co.is_billable, j.name AS job_name,
               (SELECT COUNT(*) FROM invoices i WHERE i.change_order_id = co.id) AS invoice_count
        FROM change_orders co
        JOIN jobs j ON j.id = co.job_id
        WHERE co.customer_id = ?
        ORDER BY CASE co.status
            WHEN 'Pending Approval' THEN 1
            WHEN 'Draft' THEN 2
            WHEN 'Approved' THEN 3
            WHEN 'Invoiced' THEN 4
            ELSE 5
        END, co.requested_date DESC, co.id DESC
        """,
        (customer_id,),
    ).fetchall()
    job_documents = db.execute(
        """
        SELECT jd.id, jd.job_id, jd.record_type, jd.title, jd.file_reference, jd.stored_file_name,
               jd.original_filename, jd.captured_at, jd.owner_name, jd.status, j.name AS job_name
        FROM job_documents jd
        JOIN jobs j ON j.id = jd.job_id
        WHERE jd.customer_id = ?
        ORDER BY jd.captured_at DESC, jd.id DESC
        LIMIT 10
        """,
        (customer_id,),
    ).fetchall()
    tasks = db.execute(
        """
        SELECT id, title, module_name, owner_name, due_date, reminder_at, status, priority, details
        FROM tasks
        WHERE customer_id = ?
        ORDER BY CASE status
            WHEN 'open' THEN 1
            WHEN 'scheduled' THEN 2
            WHEN 'completed' THEN 3
            ELSE 4
        END, due_date, id DESC
        """,
        (customer_id,),
    ).fetchall()
    activities = db.execute(
        """
        SELECT id, activity_date, activity_type, owner_name, title, details
        FROM activity_feed
        WHERE customer_id = ?
        ORDER BY activity_date DESC, id DESC
        LIMIT 10
        """,
        (customer_id,),
    ).fetchall()
    emails = db.execute(
        """
        SELECT id, direction, contact_email, subject, owner_name, status, sent_at, integration_status
        FROM email_messages
        WHERE customer_id = ?
        ORDER BY sent_at DESC, id DESC
        LIMIT 8
        """,
        (customer_id,),
    ).fetchall()
    calendar_events = db.execute(
        """
        SELECT id, title, event_type, starts_at, ends_at, owner_name, location, status, integration_status
        FROM calendar_events
        WHERE customer_id = ?
        ORDER BY starts_at DESC, id DESC
        LIMIT 8
        """,
        (customer_id,),
    ).fetchall()

    return render_template(
        "customers/detail.html",
        customer=customer,
        summary=summary,
        contacts=contacts,
        leads=leads,
        opportunities=opportunities,
        quotes=quotes,
        jobs=jobs,
        change_orders=change_orders,
        job_documents=job_documents,
        invoices=invoices,
        deliveries=deliveries,
        tasks=tasks,
        activities=activities,
        emails=emails,
        calendar_events=calendar_events,
        owners=_owner_choices(),
        contact_roles=CONTACT_ROLE_OPTIONS,
        task_modules=TASK_MODULES,
        task_statuses=TASK_STATUSES,
        task_priorities=TASK_PRIORITIES,
        activity_types=ACTIVITY_TYPES,
        email_directions=EMAIL_DIRECTIONS,
        email_statuses=EMAIL_STATUSES,
        integration_statuses=INTEGRATION_STATUSES,
        calendar_event_types=CALENDAR_EVENT_TYPES,
        calendar_statuses=CALENDAR_EVENT_STATUSES,
    )


@bp.post("/customers/<int:customer_id>/notes")
@roles_required(*ALL_APP_ROLES)
def customer_notes_create(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    data = _note_form_data(request.form)
    errors = _validate_note_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.customers_detail", customer_id=customer_id))

    actor = g.user["full_name"] if g.get("user") else "System"
    db = get_db()
    _create_activity(customer_id, data["activity_type"], actor, data["title"], data["details"])
    db.commit()
    flash("Customer note added to the 360 timeline.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=customer_id))


@bp.post("/customers/<int:customer_id>/tasks")
@roles_required(*ALL_APP_ROLES)
def customer_tasks_create(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    data = _task_form_data(request.form)
    errors = _validate_task_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.customers_detail", customer_id=customer_id))

    db = get_db()
    db.execute(
        """
        INSERT INTO tasks (
            branch_id, customer_id, title, module_name, owner_name, due_date, reminder_at,
            status, priority, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            customer_id,
            data["title"],
            data["module_name"],
            data["owner_name"],
            data["due_date"],
            data["reminder_at"],
            data["status"],
            data["priority"],
            data["details"],
        ),
    )
    actor = g.user["full_name"] if g.get("user") else data["owner_name"]
    reminder_copy = f" Reminder set for {data['reminder_at']}." if data["reminder_at"] else ""
    _create_activity(
        customer_id,
        "Reminder",
        actor,
        f"Task created: {data['title']}",
        f"{data['module_name']} / owner {data['owner_name']} / due {data['due_date']}.{reminder_copy} {data['details']}".strip(),
    )
    db.commit()
    flash("Task and reminder added to Customer 360.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=customer_id))


@bp.post("/tasks/<int:task_id>/toggle")
@roles_required(*ALL_APP_ROLES)
def tasks_toggle(task_id):
    task = _fetch_task(task_id)
    if task is None:
        abort(404)

    new_status = "completed" if task["status"] in {"open", "scheduled"} else "open"
    db = get_db()
    db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    actor = g.user["full_name"] if g.get("user") else task["owner_name"]
    _create_activity(
        task["customer_id"],
        "System",
        actor,
        f"Task {new_status}: {task['title']}",
        f"Customer 360 task status changed to {new_status}.",
    )
    db.commit()
    flash("Task status updated.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=task["customer_id"]))


@bp.post("/tasks/<int:task_id>/delete")
@roles_required(*ALL_APP_ROLES)
def tasks_delete(task_id):
    task = _fetch_task(task_id)
    if task is None:
        abort(404)

    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    actor = g.user["full_name"] if g.get("user") else task["owner_name"]
    _create_activity(
        task["customer_id"],
        "System",
        actor,
        f"Task removed: {task['title']}",
        "Customer 360 task was removed from the queue.",
    )
    db.commit()
    flash("Task removed.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=task["customer_id"]))


@bp.post("/customers/<int:customer_id>/emails")
@roles_required(*ALL_APP_ROLES)
def customer_emails_create(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    data = _email_form_data(request.form)
    errors = _validate_email_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.customers_detail", customer_id=customer_id))

    db = get_db()
    db.execute(
        """
        INSERT INTO email_messages (
            branch_id, customer_id, direction, contact_email, subject, body, owner_name,
            status, sent_at, integration_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            customer_id,
            data["direction"],
            data["contact_email"],
            data["subject"],
            data["body"],
            data["owner_name"],
            data["status"],
            data["sent_at"],
            data["integration_status"],
        ),
    )
    actor = g.user["full_name"] if g.get("user") else data["owner_name"]
    _create_activity(
        customer_id,
        "Email",
        actor,
        f"Email logged: {data['subject']}",
        f"{data['direction']} email for {data['contact_email']} logged with status {data['status']}.",
        data["sent_at"],
    )
    db.commit()
    flash("Email activity added to the customer hub.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=customer_id))


@bp.post("/emails/<int:message_id>/delete")
@roles_required(*ALL_APP_ROLES)
def emails_delete(message_id):
    message = _fetch_email_message(message_id)
    if message is None:
        abort(404)

    db = get_db()
    db.execute("DELETE FROM email_messages WHERE id = ?", (message_id,))
    actor = g.user["full_name"] if g.get("user") else message["owner_name"]
    _create_activity(
        message["customer_id"],
        "System",
        actor,
        f"Email removed: {message['subject']}",
        "Customer 360 email log entry was deleted.",
    )
    db.commit()
    flash("Email log removed.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=message["customer_id"]))


@bp.post("/customers/<int:customer_id>/calendar")
@roles_required(*ALL_APP_ROLES)
def customer_calendar_create(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    data = _calendar_form_data(request.form)
    errors = _validate_calendar_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.customers_detail", customer_id=customer_id))

    db = get_db()
    db.execute(
        """
        INSERT INTO calendar_events (
            branch_id, customer_id, title, event_type, starts_at, ends_at, owner_name,
            location, status, notes, integration_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            customer_id,
            data["title"],
            data["event_type"],
            data["starts_at"],
            data["ends_at"],
            data["owner_name"],
            data["location"],
            data["status"],
            data["notes"],
            data["integration_status"],
        ),
    )
    actor = g.user["full_name"] if g.get("user") else data["owner_name"]
    _create_activity(
        customer_id,
        "Meeting" if data["event_type"] in {"Call", "Meeting"} else "Reminder",
        actor,
        f"Calendar event scheduled: {data['title']}",
        f"{data['event_type']} scheduled for {data['starts_at']} at {data['location']}.",
        data["starts_at"],
    )
    db.commit()
    flash("Calendar event added to the customer hub.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=customer_id))


@bp.post("/calendar-events/<int:event_id>/delete")
@roles_required(*ALL_APP_ROLES)
def calendar_delete(event_id):
    event = _fetch_calendar_event(event_id)
    if event is None:
        abort(404)

    db = get_db()
    db.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    actor = g.user["full_name"] if g.get("user") else event["owner_name"]
    _create_activity(
        event["customer_id"],
        "System",
        actor,
        f"Calendar event removed: {event['title']}",
        "Customer 360 calendar entry was deleted.",
    )
    db.commit()
    flash("Calendar event removed.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=event["customer_id"]))


@bp.post("/customers/<int:customer_id>/contacts")
@roles_required(*ALL_APP_ROLES)
def customer_contacts_create(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    data = _customer_contact_form_data(request.form)
    errors = _validate_customer_contact_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.customers_detail", customer_id=customer_id))

    db = get_db()
    if data["is_primary"]:
        db.execute("UPDATE customer_contacts SET is_primary = 0 WHERE customer_id = ?", (customer_id,))
        db.execute(
            "UPDATE customers SET primary_contact = ?, phone = ?, email = ? WHERE id = ?",
            (data["full_name"], data["phone"], data["email"], customer_id),
        )
    db.execute(
        """
        INSERT INTO customer_contacts (
            branch_id, customer_id, full_name, role_label, phone, email, is_primary, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            customer_id,
            data["full_name"],
            data["role_label"],
            data["phone"],
            data["email"],
            data["is_primary"],
            data["notes"],
        ),
    )
    actor = g.user["full_name"] if g.get("user") else data["full_name"]
    _create_activity(
        customer_id,
        "System",
        actor,
        f"Contact added: {data['full_name']}",
        f"{data['role_label']} contact added to Customer 360.",
    )
    db.commit()
    flash("Customer contact added.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=customer_id))


@bp.post("/customer-contacts/<int:contact_id>/delete")
@roles_required(*ALL_APP_ROLES)
def customer_contacts_delete(contact_id):
    contact = _fetch_customer_contact(contact_id)
    if contact is None:
        abort(404)

    db = get_db()
    db.execute("DELETE FROM customer_contacts WHERE id = ?", (contact_id,))
    if contact["is_primary"]:
        replacement = db.execute(
            """
            SELECT id, full_name, phone, email
            FROM customer_contacts
            WHERE customer_id = ?
            ORDER BY is_primary DESC, id
            LIMIT 1
            """,
            (contact["customer_id"],),
        ).fetchone()
        if replacement:
            db.execute("UPDATE customer_contacts SET is_primary = 1 WHERE id = ?", (replacement["id"],))
        db.execute(
            "UPDATE customers SET primary_contact = ?, phone = ?, email = ? WHERE id = ?",
            (
                replacement["full_name"] if replacement else "",
                replacement["phone"] if replacement else "",
                replacement["email"] if replacement else "",
                contact["customer_id"],
            ),
        )
    actor = g.user["full_name"] if g.get("user") else contact["full_name"]
    _create_activity(
        contact["customer_id"],
        "System",
        actor,
        f"Contact removed: {contact['full_name']}",
        "Customer 360 contact was removed from the account.",
    )
    db.commit()
    flash("Customer contact removed.", "success")
    return redirect(url_for("crm.customers_detail", customer_id=contact["customer_id"]))


@bp.route("/customers/new", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def customers_create():
    data = _customer_form_data(request.form) if request.method == "POST" else {
        "name": "",
        "segment": "Residential",
        "is_repeat": 0,
        "primary_contact": "",
        "phone": "",
        "email": "",
        "service_address": "",
        "status": "active",
        "trade_mix": "",
        "notes": "",
    }

    if request.method == "POST":
        errors = _validate_customer_form(data)
        if not errors:
            db = get_db()
            customer_id = db.insert(
                """
                INSERT INTO customers (
                    branch_id, name, segment, is_repeat, primary_contact, phone, email,
                    service_address, status, trade_mix, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["name"],
                    data["segment"],
                    data["is_repeat"],
                    data["primary_contact"],
                    data["phone"],
                    data["email"],
                    data["service_address"],
                    data["status"],
                    data["trade_mix"],
                    data["notes"],
                ),
            )
            _upsert_primary_customer_contact(customer_id, data["name"], data)
            db.commit()
            flash(f"Customer '{data['name']}' created.", "success")
            return redirect(url_for("crm.customers_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "customers/form.html",
        mode="create",
        customer=data,
        segments=CUSTOMER_SEGMENTS,
        statuses=CUSTOMER_STATUSES,
    )


@bp.route("/customers/<int:customer_id>/edit", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def customers_edit(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    data = dict(customer)
    if request.method == "POST":
        data = _customer_form_data(request.form)
        errors = _validate_customer_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE customers
                SET name = ?, segment = ?, is_repeat = ?, primary_contact = ?, phone = ?,
                    email = ?, service_address = ?, status = ?, trade_mix = ?, notes = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data["segment"],
                    data["is_repeat"],
                    data["primary_contact"],
                    data["phone"],
                    data["email"],
                    data["service_address"],
                    data["status"],
                    data["trade_mix"],
                    data["notes"],
                    customer_id,
                ),
            )
            _upsert_primary_customer_contact(customer_id, data["name"], data)
            db.commit()
            flash(f"Customer '{data['name']}' updated.", "success")
            return redirect(url_for("crm.customers_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "customers/form.html",
        mode="edit",
        customer=data,
        segments=CUSTOMER_SEGMENTS,
        statuses=CUSTOMER_STATUSES,
    )


@bp.post("/customers/<int:customer_id>/delete")
@roles_required(*CRM_ROLES)
def customers_delete(customer_id):
    customer = _fetch_customer(customer_id)
    if customer is None:
        abort(404)

    db = get_db()
    dependencies = {
        "leads": db.execute("SELECT COUNT(*) AS count FROM leads WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "opportunities": db.execute("SELECT COUNT(*) AS count FROM opportunities WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "quotes": db.execute("SELECT COUNT(*) AS count FROM quotes WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "jobs": db.execute("SELECT COUNT(*) AS count FROM jobs WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "change_orders": db.execute("SELECT COUNT(*) AS count FROM change_orders WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "job_documents": db.execute("SELECT COUNT(*) AS count FROM job_documents WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "invoices": db.execute("SELECT COUNT(*) AS count FROM invoices WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "tasks": db.execute("SELECT COUNT(*) AS count FROM tasks WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "activity": db.execute("SELECT COUNT(*) AS count FROM activity_feed WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "emails": db.execute("SELECT COUNT(*) AS count FROM email_messages WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "calendar": db.execute("SELECT COUNT(*) AS count FROM calendar_events WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
        "contacts": db.execute("SELECT COUNT(*) AS count FROM customer_contacts WHERE customer_id = ?", (customer_id,)).fetchone()["count"],
    }

    if any(dependencies.values()):
        flash(
            "Customer cannot be deleted while linked CRM, field, operations, contact, note, task, email, or calendar records still exist.",
            "error",
        )
        return redirect(url_for("crm.customers_index"))

    db.execute("DELETE FROM customer_contacts WHERE customer_id = ?", (customer_id,))
    db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    db.commit()
    flash(f"Customer '{customer['name']}' deleted.", "success")
    return redirect(url_for("crm.customers_index"))


@bp.get("/leads")
@roles_required(*CRM_ROLES)
def leads_index():
    stage = request.args.get("stage", "").strip()
    params = []
    sql = """
        SELECT l.*, c.name AS customer_name, o.id AS opportunity_id
        FROM leads l
        LEFT JOIN customers c ON c.id = l.customer_id
        LEFT JOIN opportunities o ON o.lead_id = l.id
    """

    if stage:
        sql += " WHERE l.stage = ?"
        params.append(stage)

    sql += " ORDER BY l.id DESC"
    leads = get_db().execute(sql, params).fetchall()

    return render_template(
        "leads/index.html",
        leads=leads,
        selected_stage=stage,
        stage_options=LEAD_STAGES,
    )


@bp.route("/leads/new", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def leads_create():
    data = _lead_form_data(request.form) if request.method == "POST" else {
        "customer_id": _optional_int(request.args.get("customer_id")),
        "source": "Referrals",
        "trade_interest": "",
        "stage": "New Leads",
        "assigned_rep": "",
        "inspection_date": None,
        "estimated_value": None,
        "is_commercial": 0,
    }

    if request.method == "POST":
        errors = _validate_lead_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                INSERT INTO leads (
                    branch_id, customer_id, source, trade_interest, stage, assigned_rep,
                    inspection_date, estimated_value, is_commercial
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["customer_id"],
                    data["source"],
                    data["trade_interest"],
                    data["stage"],
                    data["assigned_rep"],
                    data["inspection_date"],
                    data["estimated_value"],
                    data["is_commercial"],
                ),
            )
            db.commit()
            flash("Lead created.", "success")
            return redirect(url_for("crm.leads_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "leads/form.html",
        mode="create",
        lead=data,
        customers=_customer_choices(),
        sales_reps=_sales_rep_choices(),
        stage_options=LEAD_STAGES,
        source_options=LEAD_SOURCES,
    )


@bp.route("/leads/<int:lead_id>/edit", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def leads_edit(lead_id):
    lead = _fetch_lead(lead_id)
    if lead is None:
        abort(404)

    data = dict(lead)
    if request.method == "POST":
        data = _lead_form_data(request.form)
        errors = _validate_lead_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE leads
                SET customer_id = ?, source = ?, trade_interest = ?, stage = ?, assigned_rep = ?,
                    inspection_date = ?, estimated_value = ?, is_commercial = ?
                WHERE id = ?
                """,
                (
                    data["customer_id"],
                    data["source"],
                    data["trade_interest"],
                    data["stage"],
                    data["assigned_rep"],
                    data["inspection_date"],
                    data["estimated_value"],
                    data["is_commercial"],
                    lead_id,
                ),
            )
            db.commit()
            flash("Lead updated.", "success")
            return redirect(url_for("crm.leads_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "leads/form.html",
        mode="edit",
        lead=data,
        customers=_customer_choices(),
        sales_reps=_sales_rep_choices(),
        stage_options=LEAD_STAGES,
        source_options=LEAD_SOURCES,
    )


@bp.post("/leads/<int:lead_id>/delete")
@roles_required(*CRM_ROLES)
def leads_delete(lead_id):
    lead = _fetch_lead(lead_id)
    if lead is None:
        abort(404)

    linked_opp = get_db().execute(
        "SELECT COUNT(*) AS count FROM opportunities WHERE lead_id = ?",
        (lead_id,),
    ).fetchone()["count"]
    if linked_opp:
        flash("Lead cannot be deleted while an opportunity still references it.", "error")
        return redirect(url_for("crm.leads_index"))

    db = get_db()
    db.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    db.commit()
    flash("Lead deleted.", "success")
    return redirect(url_for("crm.leads_index"))


@bp.get("/opportunities")
@roles_required(*CRM_ROLES)
def opportunities_index():
    stage = request.args.get("stage", "").strip()
    params = []
    sql = """
        SELECT o.*, c.name AS customer_name
        FROM opportunities o
        LEFT JOIN customers c ON c.id = o.customer_id
    """

    if stage:
        sql += " WHERE o.stage = ?"
        params.append(stage)

    sql += " ORDER BY o.priority DESC, o.close_date ASC"
    opportunities = get_db().execute(sql, params).fetchall()

    return render_template(
        "opportunities/index.html",
        opportunities=opportunities,
        selected_stage=stage,
        stage_options=OPPORTUNITY_STAGES,
    )


@bp.route("/opportunities/new", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def opportunities_create():
    lead_id = _optional_int(request.args.get("lead_id"))
    lead = _fetch_lead(lead_id) if lead_id else None

    data = _opportunity_form_data(request.form) if request.method == "POST" else {
        "lead_id": lead["id"] if lead else None,
        "customer_id": lead["customer_id"] if lead else None,
        "name": "",
        "subtitle": lead["trade_interest"] if lead else "",
        "stage": lead["stage"] if lead and lead["stage"] in OPPORTUNITY_STAGES else "New Leads",
        "close_date": None,
        "value": lead["estimated_value"] if lead else None,
        "priority": 60,
        "trade_mix": lead["trade_interest"] if lead else "",
        "rep": lead["assigned_rep"] if lead else "",
    }

    if lead and data["name"] == "":
        linked_customer = _fetch_customer(lead["customer_id"]) if lead["customer_id"] else None
        data["name"] = linked_customer["name"] if linked_customer else lead["trade_interest"]

    if request.method == "POST":
        errors = _validate_opportunity_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                INSERT INTO opportunities (
                    branch_id, lead_id, customer_id, name, subtitle, stage, close_date,
                    value, priority, trade_mix, rep
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["lead_id"],
                    data["customer_id"],
                    data["name"],
                    data["subtitle"],
                    data["stage"],
                    data["close_date"],
                    data["value"],
                    data["priority"],
                    data["trade_mix"],
                    data["rep"],
                ),
            )
            db.commit()
            flash("Opportunity created.", "success")
            return redirect(url_for("crm.opportunities_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "opportunities/form.html",
        mode="create",
        opportunity=data,
        customers=_customer_choices(),
        leads=_lead_choices(),
        sales_reps=_sales_rep_choices(),
        stage_options=OPPORTUNITY_STAGES,
    )


@bp.route("/opportunities/<int:opportunity_id>/edit", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def opportunities_edit(opportunity_id):
    opportunity = _fetch_opportunity(opportunity_id)
    if opportunity is None:
        abort(404)

    data = dict(opportunity)
    if request.method == "POST":
        data = _opportunity_form_data(request.form)
        errors = _validate_opportunity_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE opportunities
                SET lead_id = ?, customer_id = ?, name = ?, subtitle = ?, stage = ?,
                    close_date = ?, value = ?, priority = ?, trade_mix = ?, rep = ?
                WHERE id = ?
                """,
                (
                    data["lead_id"],
                    data["customer_id"],
                    data["name"],
                    data["subtitle"],
                    data["stage"],
                    data["close_date"],
                    data["value"],
                    data["priority"],
                    data["trade_mix"],
                    data["rep"],
                    opportunity_id,
                ),
            )
            db.commit()
            flash("Opportunity updated.", "success")
            return redirect(url_for("crm.opportunities_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "opportunities/form.html",
        mode="edit",
        opportunity=data,
        customers=_customer_choices(),
        leads=_lead_choices(),
        sales_reps=_sales_rep_choices(),
        stage_options=OPPORTUNITY_STAGES,
    )


@bp.post("/opportunities/<int:opportunity_id>/delete")
@roles_required(*CRM_ROLES)
def opportunities_delete(opportunity_id):
    opportunity = _fetch_opportunity(opportunity_id)
    if opportunity is None:
        abort(404)

    dependencies = {
        "quotes": get_db().execute("SELECT COUNT(*) AS count FROM quotes WHERE opportunity_id = ?", (opportunity_id,)).fetchone()["count"],
        "jobs": get_db().execute("SELECT COUNT(*) AS count FROM jobs WHERE opportunity_id = ?", (opportunity_id,)).fetchone()["count"],
    }
    if any(dependencies.values()):
        flash("Opportunity cannot be deleted while linked quotes or jobs still exist.", "error")
        return redirect(url_for("crm.opportunities_index"))

    db = get_db()
    db.execute("DELETE FROM opportunities WHERE id = ?", (opportunity_id,))
    db.commit()
    flash("Opportunity deleted.", "success")
    return redirect(url_for("crm.opportunities_index"))


@bp.get("/quotes")
@roles_required(*CRM_ROLES)
def quotes_index():
    status = request.args.get("status", "").strip()
    params = []
    sql = """
        SELECT q.*, c.name AS customer_name, o.name AS opportunity_name
        FROM quotes q
        JOIN customers c ON c.id = q.customer_id
        LEFT JOIN opportunities o ON o.id = q.opportunity_id
    """

    if status:
        sql += " WHERE q.status = ?"
        params.append(status)

    sql += " ORDER BY q.id DESC"
    quotes = get_db().execute(sql, params).fetchall()
    return render_template(
        "quotes/index.html",
        quotes=quotes,
        selected_status=status,
        status_options=QUOTE_STATUSES,
    )


@bp.route("/quotes/new", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def quotes_create():
    opportunity_id = _optional_int(request.args.get("opportunity_id"))
    opportunity = _fetch_opportunity(opportunity_id) if opportunity_id else None
    suggested_amount = opportunity["value"] if opportunity else None
    data = _quote_form_data(request.form) if request.method == "POST" else {
        "opportunity_id": opportunity["id"] if opportunity else None,
        "customer_id": opportunity["customer_id"] if opportunity else None,
        "quote_number": _next_document_number("Q", "quotes", "quote_number"),
        "option_name": "Standard",
        "description": opportunity["subtitle"] if opportunity else "",
        "amount": suggested_amount,
        "estimated_cost": round(suggested_amount * 0.67, 2) if suggested_amount else None,
        "deposit_required": round(suggested_amount * 0.25, 2) if suggested_amount else 0,
        "deposit_received": 0,
        "status": "Draft",
        "signed_date": None,
        "issue_date": datetime.now().date().isoformat(),
        "expiration_date": None,
    }

    if request.method == "POST":
        errors = _validate_quote_form(data)
        if not errors:
            db = get_db()
            target_margin_pct = _calculate_margin_pct(data["amount"], data["estimated_cost"])
            db.execute(
                """
                INSERT INTO quotes (
                    branch_id, opportunity_id, customer_id, quote_number, option_name,
                    description, amount, estimated_cost, target_margin_pct, deposit_required,
                    deposit_received, status, signed_date, issue_date, expiration_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["opportunity_id"],
                    data["customer_id"],
                    data["quote_number"],
                    data["option_name"],
                    data["description"],
                    data["amount"],
                    data["estimated_cost"],
                    target_margin_pct,
                    data["deposit_required"],
                    data["deposit_received"],
                    data["status"],
                    data["signed_date"],
                    data["issue_date"],
                    data["expiration_date"],
                ),
            )
            if data["opportunity_id"]:
                db.execute(
                    "UPDATE opportunities SET stage = ? WHERE id = ?",
                    ("Quoted", data["opportunity_id"]),
                )
            if data["customer_id"]:
                _create_activity(
                    data["customer_id"],
                    "System",
                    g.user["full_name"] if g.get("user") else "System",
                    f"Contract created: {data['quote_number']}",
                    f"{data['option_name']} for {data['amount']:,.2f} with target margin {target_margin_pct:.1f}%.",
                )
            db.commit()
            flash("Quote created.", "success")
            return redirect(url_for("crm.quotes_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "quotes/form.html",
        mode="create",
        quote=data,
        customers=_customer_choices(),
        opportunities=_opportunity_choices(),
        status_options=QUOTE_STATUSES,
    )


@bp.route("/quotes/<int:quote_id>/edit", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def quotes_edit(quote_id):
    quote = _fetch_quote(quote_id)
    if quote is None:
        abort(404)

    data = dict(quote)
    if request.method == "POST":
        data = _quote_form_data(request.form)
        errors = _validate_quote_form(data)
        if not errors:
            db = get_db()
            target_margin_pct = _calculate_margin_pct(data["amount"], data["estimated_cost"])
            db.execute(
                """
                UPDATE quotes
                SET opportunity_id = ?, customer_id = ?, quote_number = ?, option_name = ?, description = ?,
                    amount = ?, estimated_cost = ?, target_margin_pct = ?, deposit_required = ?,
                    deposit_received = ?, status = ?, signed_date = ?, issue_date = ?, expiration_date = ?
                WHERE id = ?
                """,
                (
                    data["opportunity_id"],
                    data["customer_id"],
                    data["quote_number"],
                    data["option_name"],
                    data["description"],
                    data["amount"],
                    data["estimated_cost"],
                    target_margin_pct,
                    data["deposit_required"],
                    data["deposit_received"],
                    data["status"],
                    data["signed_date"],
                    data["issue_date"],
                    data["expiration_date"],
                    quote_id,
                ),
            )
            db.commit()
            flash("Quote updated.", "success")
            return redirect(url_for("crm.quotes_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "quotes/form.html",
        mode="edit",
        quote=data,
        customers=_customer_choices(),
        opportunities=_opportunity_choices(),
        status_options=QUOTE_STATUSES,
    )


@bp.route("/quotes/<int:quote_id>/contract", methods=("GET", "POST"))
@roles_required(*CRM_ROLES)
def quotes_contract(quote_id):
    quote = _fetch_quote(quote_id)
    if quote is None:
        abort(404)

    contract = {
        "signed_date": quote["signed_date"],
        "deposit_required": quote["deposit_required"],
        "deposit_received": quote["deposit_received"],
    }
    if request.method == "POST":
        contract = {
            "signed_date": _optional_date(request.form.get("signed_date")),
            "deposit_required": _optional_float(request.form.get("deposit_required")),
            "deposit_received": _optional_float(request.form.get("deposit_received")),
        }
        errors = []
        if not contract["signed_date"]:
            errors.append("Signed date is required before the job can move forward.")
        if contract["deposit_required"] is None or contract["deposit_required"] < 0:
            errors.append("Required deposit must be zero or a positive number.")
        if contract["deposit_received"] is None or contract["deposit_received"] < 0:
            errors.append("Received deposit must be zero or a positive number.")
        if (
            contract["deposit_required"] is not None
            and quote["amount"] is not None
            and contract["deposit_required"] > quote["amount"]
        ):
            errors.append("Required deposit cannot exceed contract amount.")
        if (
            contract["deposit_received"] is not None
            and quote["amount"] is not None
            and contract["deposit_received"] > quote["amount"]
        ):
            errors.append("Received deposit cannot exceed contract amount.")
        if not errors:
            status = "Approved" if contract["deposit_received"] >= contract["deposit_required"] else "Pending Deposit"
            db = get_db()
            db.execute(
                """
                UPDATE quotes
                SET signed_date = ?, deposit_required = ?, deposit_received = ?, status = ?
                WHERE id = ?
                """,
                (
                    contract["signed_date"],
                    contract["deposit_required"],
                    contract["deposit_received"],
                    status,
                    quote_id,
                ),
            )
            if quote["customer_id"]:
                _create_activity(
                    quote["customer_id"],
                    "System",
                    g.user["full_name"] if g.get("user") else "System",
                    f"Contract updated: {quote['quote_number']}",
                    (
                        f"Signed {contract['signed_date']}. "
                        f"Deposit {contract['deposit_received']:,.2f} of {contract['deposit_required']:,.2f}. "
                        f"Status moved to {status}."
                    ),
                )
            db.commit()
            flash("Contract execution details updated.", "success")
            return redirect(url_for("crm.quotes_index"))

        for error in errors:
            flash(error, "error")

    return render_template("quotes/contract.html", quote=quote, contract=contract)


@bp.post("/quotes/<int:quote_id>/delete")
@roles_required(*CRM_ROLES)
def quotes_delete(quote_id):
    quote = _fetch_quote(quote_id)
    if quote is None:
        abort(404)

    linked_jobs = get_db().execute(
        "SELECT COUNT(*) AS count FROM jobs WHERE quote_id = ?",
        (quote_id,),
    ).fetchone()["count"]
    linked_invoices = get_db().execute(
        "SELECT COUNT(*) AS count FROM invoices WHERE quote_id = ?",
        (quote_id,),
    ).fetchone()["count"]
    linked_change_orders = get_db().execute(
        "SELECT COUNT(*) AS count FROM change_orders WHERE quote_id = ?",
        (quote_id,),
    ).fetchone()["count"]
    if linked_jobs or linked_invoices or linked_change_orders:
        flash("Quote cannot be deleted while a job, change order, or invoice still references it.", "error")
        return redirect(url_for("crm.quotes_index"))

    db = get_db()
    db.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))
    db.commit()
    flash("Quote deleted.", "success")
    return redirect(url_for("crm.quotes_index"))


@bp.get("/jobs")
@roles_required(*ALL_APP_ROLES)
def jobs_index():
    status = request.args.get("status", "").strip()
    params = []
    sql = """
        SELECT j.*, c.name AS customer_name, q.quote_number, q.option_name,
               (SELECT COUNT(*) FROM invoices i WHERE i.job_id = j.id) AS invoice_count,
               (SELECT COUNT(*) FROM deliveries d WHERE d.job_id = j.id) AS delivery_count,
               (SELECT COUNT(*) FROM job_materials jm WHERE jm.job_id = j.id) AS material_count,
               (SELECT COUNT(*) FROM change_orders co WHERE co.job_id = j.id) AS change_order_count,
               (SELECT COUNT(*) FROM job_documents jd WHERE jd.job_id = j.id) AS field_record_count,
               (SELECT COALESCE(SUM(CASE WHEN co.status = 'Approved' AND co.is_billable = 1 THEN co.amount ELSE 0 END), 0)
                FROM change_orders co WHERE co.job_id = j.id) AS approved_change_revenue,
               (SELECT COALESCE(SUM(jc.total_cost), 0) FROM job_cost_entries jc WHERE jc.job_id = j.id) AS actual_cost
        FROM jobs j
        JOIN customers c ON c.id = j.customer_id
        LEFT JOIN quotes q ON q.id = j.quote_id
    """
    if status:
        sql += " WHERE j.status = ?"
        params.append(status)
    sql += " ORDER BY j.id DESC"
    jobs = get_db().execute(sql, params).fetchall()
    return render_template(
        "jobs/index.html",
        jobs=jobs,
        selected_status=status,
        status_options=JOB_STATUSES,
    )


@bp.route("/jobs/new", methods=("GET", "POST"))
@roles_required(*JOB_ROLES)
def jobs_create():
    quote_id = _optional_int(request.args.get("quote_id"))
    quote = _fetch_quote(quote_id) if quote_id else None
    if quote and (not quote["signed_date"] or quote["status"] != "Approved"):
        flash("Record the signed contract and deposit before creating a job from this quote.", "error")
        return redirect(url_for("crm.quotes_contract", quote_id=quote_id))
    opportunity = _fetch_opportunity(quote["opportunity_id"]) if quote and quote["opportunity_id"] else None
    customer = _fetch_customer(quote["customer_id"]) if quote else None
    data = _job_form_data(request.form) if request.method == "POST" else {
        "opportunity_id": opportunity["id"] if opportunity else None,
        "quote_id": quote["id"] if quote else None,
        "customer_id": customer["id"] if customer else None,
        "name": customer["name"] if customer else "",
        "scope": quote["description"] if quote else (opportunity["subtitle"] if opportunity else ""),
        "status": "Sales handoff",
        "scheduled_start": None,
        "crew_name": "",
        "committed_revenue": quote["amount"] if quote else (opportunity["value"] if opportunity else None),
    }

    if request.method == "POST":
        errors = _validate_job_form(data)
        linked_quote = _fetch_quote(data["quote_id"]) if data["quote_id"] else None
        if linked_quote and (not linked_quote["signed_date"] or linked_quote["status"] != "Approved"):
            errors.append("A signed and approved contract is required before creating the job.")
        if not errors:
            db = get_db()
            db.execute(
                """
                INSERT INTO jobs (
                    branch_id, opportunity_id, quote_id, customer_id, name, scope, status,
                    scheduled_start, crew_name, committed_revenue
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["opportunity_id"],
                    data["quote_id"],
                    data["customer_id"],
                    data["name"],
                    data["scope"],
                    data["status"],
                    data["scheduled_start"],
                    data["crew_name"],
                    data["committed_revenue"],
                ),
            )
            if data["quote_id"]:
                db.execute("UPDATE quotes SET status = ? WHERE id = ?", ("Approved", data["quote_id"]))
            if data["opportunity_id"]:
                db.execute("UPDATE opportunities SET stage = ? WHERE id = ?", ("Won / Ready", data["opportunity_id"]))
            db.commit()
            flash("Job created from sales workflow.", "success")
            return redirect(url_for("crm.jobs_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "jobs/form.html",
        mode="create",
        job=data,
        customers=_customer_choices(),
        opportunities=_opportunity_choices(),
        quotes=_quote_choices(),
        status_options=JOB_STATUSES,
    )


@bp.route("/jobs/<int:job_id>/edit", methods=("GET", "POST"))
@roles_required(*JOB_ROLES)
def jobs_edit(job_id):
    job = _fetch_job(job_id)
    if job is None:
        abort(404)

    data = dict(job)
    if request.method == "POST":
        data = _job_form_data(request.form)
        errors = _validate_job_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE jobs
                SET opportunity_id = ?, quote_id = ?, customer_id = ?, name = ?, scope = ?,
                    status = ?, scheduled_start = ?, crew_name = ?, committed_revenue = ?
                WHERE id = ?
                """,
                (
                    data["opportunity_id"],
                    data["quote_id"],
                    data["customer_id"],
                    data["name"],
                    data["scope"],
                    data["status"],
                    data["scheduled_start"],
                    data["crew_name"],
                    data["committed_revenue"],
                    job_id,
                ),
            )
            db.commit()
            flash("Job updated.", "success")
            return redirect(url_for("crm.jobs_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "jobs/form.html",
        mode="edit",
        job=data,
        customers=_customer_choices(),
        opportunities=_opportunity_choices(),
        quotes=_quote_choices(),
        status_options=JOB_STATUSES,
    )


@bp.post("/jobs/<int:job_id>/delete")
@roles_required(*JOB_ROLES)
def jobs_delete(job_id):
    job = _fetch_job(job_id)
    if job is None:
        abort(404)

    db = get_db()
    dependencies = {
        "deliveries": db.execute("SELECT COUNT(*) AS count FROM deliveries WHERE job_id = ?", (job_id,)).fetchone()["count"],
        "invoices": db.execute("SELECT COUNT(*) AS count FROM invoices WHERE job_id = ?", (job_id,)).fetchone()["count"],
        "materials": db.execute("SELECT COUNT(*) AS count FROM job_materials WHERE job_id = ?", (job_id,)).fetchone()["count"],
        "costs": db.execute("SELECT COUNT(*) AS count FROM job_cost_entries WHERE job_id = ?", (job_id,)).fetchone()["count"],
        "purchasing": db.execute("SELECT COUNT(*) AS count FROM purchase_requests WHERE job_id = ?", (job_id,)).fetchone()["count"],
        "change_orders": db.execute("SELECT COUNT(*) AS count FROM change_orders WHERE job_id = ?", (job_id,)).fetchone()["count"],
        "job_documents": db.execute("SELECT COUNT(*) AS count FROM job_documents WHERE job_id = ?", (job_id,)).fetchone()["count"],
    }
    if any(dependencies.values()):
        flash(
            "Job cannot be deleted while linked materials, field records, change orders, costs, purchasing, deliveries, or invoices still exist.",
            "error",
        )
        return redirect(url_for("crm.jobs_index"))

    db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.commit()
    flash("Job deleted.", "success")
    return redirect(url_for("crm.jobs_index"))


@bp.get("/jobs/<int:job_id>/costing")
@roles_required(*ALL_APP_ROLES)
def jobs_costing(job_id):
    db = get_db()
    job = db.execute(
        """
        SELECT j.*, c.name AS customer_name, q.quote_number, q.option_name, q.estimated_cost,
               q.target_margin_pct, q.deposit_required, q.deposit_received, q.signed_date
        FROM jobs j
        JOIN customers c ON c.id = j.customer_id
        LEFT JOIN quotes q ON q.id = j.quote_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    if job is None:
        abort(404)

    costs = db.execute(
        """
        SELECT jc.*, v.name AS vendor_name
        FROM job_cost_entries jc
        LEFT JOIN vendors v ON v.id = jc.vendor_id
        WHERE jc.job_id = ?
        ORDER BY jc.cost_date DESC, jc.id DESC
        """,
        (job_id,),
    ).fetchall()
    tracked_cost = db.execute(
        "SELECT COALESCE(SUM(total_cost), 0) AS total FROM job_cost_entries WHERE job_id = ?",
        (job_id,),
    ).fetchone()["total"]
    reserved_material_cost = db.execute(
        """
        SELECT COALESCE(SUM(jm.reserved_qty * i.unit_cost), 0) AS total
        FROM job_materials jm
        JOIN inventory_items i ON i.id = jm.inventory_item_id
        WHERE jm.job_id = ?
        """,
        (job_id,),
    ).fetchone()["total"]
    invoice_snapshot = db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS invoiced,
               COALESCE(SUM(amount - remaining_balance), 0) AS collected
        FROM invoices
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()
    execution_snapshot = _job_execution_snapshot(job_id)
    revised_contract_value = job["committed_revenue"] + execution_snapshot["approved_change_revenue"]
    projected_cost_at_completion = tracked_cost + execution_snapshot["approved_change_cost"]
    projected_profit = job["committed_revenue"] - tracked_cost
    revised_projected_profit = revised_contract_value - projected_cost_at_completion
    actual_margin_pct = _calculate_margin_pct(job["committed_revenue"], tracked_cost)
    revised_margin_pct = _calculate_margin_pct(revised_contract_value, projected_cost_at_completion)
    reserved_material_pct = _calculate_margin_pct(job["committed_revenue"], reserved_material_cost)

    summary = {
        "contract_value": job["committed_revenue"],
        "estimated_cost": job["estimated_cost"] or 0,
        "target_margin_pct": job["target_margin_pct"] or 0,
        "deposit_required": job["deposit_required"] or 0,
        "deposit_received": job["deposit_received"] or 0,
        "tracked_cost": tracked_cost,
        "reserved_material_cost": reserved_material_cost,
        "projected_profit": projected_profit,
        "actual_margin_pct": actual_margin_pct,
        "reserved_material_pct": reserved_material_pct,
        "invoiced": invoice_snapshot["invoiced"],
        "collected": invoice_snapshot["collected"],
        "approved_change_revenue": execution_snapshot["approved_change_revenue"],
        "approved_change_cost": execution_snapshot["approved_change_cost"],
        "open_change_orders": execution_snapshot["open_change_orders"],
        "field_record_count": execution_snapshot["field_record_count"],
        "revised_contract_value": revised_contract_value,
        "revised_projected_profit": revised_projected_profit,
        "revised_margin_pct": revised_margin_pct,
    }

    return render_template(
        "jobs/costing.html",
        job=job,
        costs=costs,
        summary=summary,
        vendors=_vendor_choices(),
        source_types=JOB_COST_SOURCE_TYPES,
        cost_statuses=JOB_COST_STATUSES,
    )


@bp.post("/jobs/<int:job_id>/costs")
@roles_required(*COSTING_MANAGE_ROLES)
def jobs_costs_create(job_id):
    job = _fetch_job(job_id)
    if job is None:
        abort(404)

    data = _job_cost_form_data(request.form)
    errors = _validate_job_cost_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.jobs_costing", job_id=job_id))

    db = get_db()
    db.execute(
        """
        INSERT INTO job_cost_entries (
            branch_id, job_id, vendor_id, cost_code, source_type, description, quantity,
            unit_cost, total_cost, cost_date, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            job_id,
            data["vendor_id"],
            data["cost_code"],
            data["source_type"],
            data["description"],
            data["quantity"],
            data["unit_cost"],
            data["total_cost"],
            data["cost_date"],
            data["status"],
            data["notes"],
        ),
    )
    _create_activity(
        job["customer_id"],
        "System",
        g.user["full_name"] if g.get("user") else "System",
        f"Job cost added: {job['name']}",
        f"{data['source_type']} cost '{data['description']}' logged at {data['total_cost']:,.2f}.",
        data["cost_date"],
    )
    db.commit()
    flash("Job cost entry added.", "success")
    return redirect(url_for("crm.jobs_costing", job_id=job_id))


@bp.post("/job-costs/<int:cost_id>/delete")
@roles_required(*COSTING_MANAGE_ROLES)
def jobs_costs_delete(cost_id):
    cost = _fetch_job_cost_entry(cost_id)
    if cost is None:
        abort(404)

    job = _fetch_job(cost["job_id"])
    db = get_db()
    db.execute("DELETE FROM job_cost_entries WHERE id = ?", (cost_id,))
    if job is not None:
        _create_activity(
            job["customer_id"],
            "System",
            g.user["full_name"] if g.get("user") else "System",
            f"Job cost removed: {job['name']}",
            f"Removed costing line '{cost['description']}'.",
        )
    db.commit()
    flash("Job cost entry removed.", "success")
    return redirect(url_for("crm.jobs_costing", job_id=cost["job_id"]))


@bp.get("/jobs/<int:job_id>/execution")
@roles_required(*ALL_APP_ROLES)
def jobs_execution(job_id):
    db = get_db()
    job = db.execute(
        """
        SELECT j.*, c.name AS customer_name, q.quote_number, q.option_name, q.deposit_received,
               q.deposit_required, q.signed_date
        FROM jobs j
        JOIN customers c ON c.id = j.customer_id
        LEFT JOIN quotes q ON q.id = j.quote_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    if job is None:
        abort(404)

    change_orders = db.execute(
        """
        SELECT co.*,
               (SELECT COUNT(*) FROM invoices i WHERE i.change_order_id = co.id) AS invoice_count,
               (SELECT COUNT(*) FROM change_order_versions cov WHERE cov.change_order_id = co.id) AS version_count
        FROM change_orders co
        WHERE co.job_id = ?
        ORDER BY CASE co.status
            WHEN 'Pending Approval' THEN 1
            WHEN 'Draft' THEN 2
            WHEN 'Approved' THEN 3
            WHEN 'Invoiced' THEN 4
            ELSE 5
        END, co.requested_date DESC, co.id DESC
        """,
        (job_id,),
    ).fetchall()
    documents = db.execute(
        """
        SELECT *
        FROM job_documents
        WHERE job_id = ?
        ORDER BY captured_at DESC, id DESC
        """,
        (job_id,),
    ).fetchall()
    deliveries = db.execute(
        """
        SELECT id, route_name, truck_name, eta, status, load_percent
        FROM deliveries
        WHERE job_id = ?
        ORDER BY eta DESC, id DESC
        LIMIT 5
        """,
        (job_id,),
    ).fetchall()
    invoice_snapshot = db.execute(
        """
        SELECT COUNT(*) AS count,
               COALESCE(SUM(amount), 0) AS total,
               COALESCE(SUM(remaining_balance), 0) AS balance
        FROM invoices
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()
    execution_snapshot = _job_execution_snapshot(job_id)
    summary = {
        "revised_contract_value": job["committed_revenue"] + execution_snapshot["approved_change_revenue"],
        "approved_change_revenue": execution_snapshot["approved_change_revenue"],
        "approved_change_cost": execution_snapshot["approved_change_cost"],
        "open_change_orders": execution_snapshot["open_change_orders"],
        "field_record_count": execution_snapshot["field_record_count"],
        "open_field_records": execution_snapshot["open_field_records"],
        "invoice_count": invoice_snapshot["count"],
        "invoiced_total": invoice_snapshot["total"],
        "open_balance": invoice_snapshot["balance"],
    }
    change_order_defaults = {
        "change_number": _next_document_number("CO", "change_orders", "change_number"),
        "title": "",
        "description": "",
        "status": "Draft",
        "requested_date": datetime.now().date().isoformat(),
        "approved_date": None,
        "amount": None,
        "cost_impact": None,
        "schedule_days": 0,
        "owner_name": g.user["full_name"] if g.get("user") else "",
        "is_billable": 1,
        "notes": "",
    }
    document_defaults = {
        "record_type": "Photo",
        "title": "",
        "file_reference": "",
        "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "owner_name": g.user["full_name"] if g.get("user") else "",
        "status": "Logged",
        "notes": "",
    }
    return render_template(
        "jobs/execution.html",
        job=job,
        change_orders=change_orders,
        documents=documents,
        deliveries=deliveries,
        summary=summary,
        change_order_defaults=change_order_defaults,
        document_defaults=document_defaults,
        change_order_statuses=CHANGE_ORDER_STATUSES,
        owners=_owner_choices(),
        document_types=JOB_DOCUMENT_TYPES,
        document_statuses=JOB_DOCUMENT_STATUSES,
    )


@bp.post("/jobs/<int:job_id>/change-orders")
@roles_required(*FIELD_EXECUTION_MANAGE_ROLES)
def change_orders_create(job_id):
    job = _fetch_job(job_id)
    if job is None:
        abort(404)

    data = _change_order_form_data(request.form)
    errors = _validate_change_order_form(data)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.jobs_execution", job_id=job_id))

    db = get_db()
    change_order_id = db.insert(
        """
        INSERT INTO change_orders (
            branch_id, job_id, customer_id, quote_id, change_number, title, description,
            status, requested_date, approved_date, amount, cost_impact, schedule_days,
            owner_name, is_billable, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            job_id,
            job["customer_id"],
            job["quote_id"],
            data["change_number"],
            data["title"],
            data["description"],
            data["status"],
            data["requested_date"],
            data["approved_date"],
            data["amount"],
            data["cost_impact"],
            data["schedule_days"],
            data["owner_name"],
            data["is_billable"],
            data["notes"],
        ),
    )
    _record_change_order_version(
        change_order_id,
        g.user["full_name"] if g.get("user") else "System",
        "Initial change order entry",
    )
    _create_activity(
        job["customer_id"],
        "System",
        g.user["full_name"] if g.get("user") else "System",
        f"Change order logged: {data['change_number']}",
        f"{data['title']} for ${data['amount']:,.2f} on job {job['name']}.",
        data["approved_date"] or data["requested_date"],
    )
    db.commit()
    flash("Change order logged on the job execution record.", "success")
    return redirect(url_for("crm.jobs_execution", job_id=job_id))


@bp.route("/change-orders/<int:change_order_id>/edit", methods=("GET", "POST"))
@roles_required(*FIELD_EXECUTION_MANAGE_ROLES)
def change_orders_edit(change_order_id):
    change_order = _fetch_change_order(change_order_id)
    if change_order is None:
        abort(404)

    job = _fetch_job(change_order["job_id"])
    if job is None:
        abort(404)

    data = dict(change_order)
    if request.method == "POST":
        data = _change_order_form_data(request.form)
        change_summary = request.form.get("change_summary", "").strip() or "Updated change order"
        errors = _validate_change_order_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE change_orders
                SET change_number = ?, title = ?, description = ?, status = ?, requested_date = ?,
                    approved_date = ?, amount = ?, cost_impact = ?, schedule_days = ?, owner_name = ?,
                    is_billable = ?, notes = ?
                WHERE id = ?
                """,
                (
                    data["change_number"],
                    data["title"],
                    data["description"],
                    data["status"],
                    data["requested_date"],
                    data["approved_date"],
                    data["amount"],
                    data["cost_impact"],
                    data["schedule_days"],
                    data["owner_name"],
                    data["is_billable"],
                    data["notes"],
                    change_order_id,
                ),
            )
            _record_change_order_version(
                change_order_id,
                g.user["full_name"] if g.get("user") else "System",
                change_summary,
            )
            _create_activity(
                change_order["customer_id"],
                "System",
                g.user["full_name"] if g.get("user") else "System",
                f"Change order updated: {data['change_number']}",
                f"{change_summary}. Current status {data['status']} at ${data['amount']:,.2f}.",
                data["approved_date"] or data["requested_date"],
            )
            db.commit()
            flash("Change order updated.", "success")
            return redirect(url_for("crm.jobs_execution", job_id=change_order["job_id"]))

        for error in errors:
            flash(error, "error")

    return render_template(
        "change_orders/form.html",
        mode="edit",
        change_order=data,
        change_summary="",
        job=job,
        owners=_owner_choices(),
        change_order_statuses=CHANGE_ORDER_STATUSES,
        version_history=_change_order_version_history(change_order_id),
    )


@bp.post("/change-orders/<int:change_order_id>/delete")
@roles_required(*FIELD_EXECUTION_MANAGE_ROLES)
def change_orders_delete(change_order_id):
    change_order = _fetch_change_order(change_order_id)
    if change_order is None:
        abort(404)

    db = get_db()
    linked_invoices = db.execute(
        "SELECT COUNT(*) AS count FROM invoices WHERE change_order_id = ?",
        (change_order_id,),
    ).fetchone()["count"]
    if linked_invoices:
        flash("Delete or unlink the related invoice before removing this change order.", "error")
        return redirect(url_for("crm.jobs_execution", job_id=change_order["job_id"]))

    db.execute("DELETE FROM change_order_versions WHERE change_order_id = ?", (change_order_id,))
    db.execute("DELETE FROM change_orders WHERE id = ?", (change_order_id,))
    _create_activity(
        change_order["customer_id"],
        "System",
        g.user["full_name"] if g.get("user") else "System",
        f"Change order removed: {change_order['change_number']}",
        f"Removed change order '{change_order['title']}' from field execution.",
    )
    db.commit()
    flash("Change order removed.", "success")
    return redirect(url_for("crm.jobs_execution", job_id=change_order["job_id"]))


@bp.post("/jobs/<int:job_id>/documents")
@roles_required(*FIELD_EXECUTION_MANAGE_ROLES)
def job_documents_create(job_id):
    job = _fetch_job(job_id)
    if job is None:
        abort(404)

    data = _job_document_form_data(request.form)
    upload = request.files.get("upload_file")
    errors = _validate_job_document_form(data, upload)
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.jobs_execution", job_id=job_id))

    stored_file_name, original_filename = _save_job_document_upload(upload, job_id) if upload else (None, None)
    db = get_db()
    db.execute(
        """
        INSERT INTO job_documents (
            branch_id, job_id, customer_id, record_type, title, file_reference, stored_file_name,
            original_filename, captured_at, owner_name, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            job_id,
            job["customer_id"],
            data["record_type"],
            data["title"],
            data["file_reference"],
            stored_file_name,
            original_filename,
            data["captured_at"],
            data["owner_name"],
            data["status"],
            data["notes"],
        ),
    )
    _create_activity(
        job["customer_id"],
        "System",
        g.user["full_name"] if g.get("user") else "System",
        f"Field record added: {data['title']}",
        f"{data['record_type']} logged on job {job['name']}.",
        data["captured_at"],
    )
    db.commit()
    flash("Field record added to the job packet.", "success")
    return redirect(url_for("crm.jobs_execution", job_id=job_id))


@bp.route("/job-documents/<int:document_id>/edit", methods=("GET", "POST"))
@roles_required(*FIELD_EXECUTION_MANAGE_ROLES)
def job_documents_edit(document_id):
    document = _fetch_job_document(document_id)
    if document is None:
        abort(404)

    job = _fetch_job(document["job_id"])
    if job is None:
        abort(404)

    data = dict(document)
    if request.method == "POST":
        data = _job_document_form_data(request.form)
        upload = request.files.get("upload_file")
        replace_existing_file = request.form.get("replace_existing_file") == "on"
        errors = _validate_job_document_form(data, upload)
        if not errors:
            stored_file_name = document["stored_file_name"]
            original_filename = document["original_filename"]
            if upload and (upload.filename or "").strip():
                _remove_job_document_upload(document)
                stored_file_name, original_filename = _save_job_document_upload(upload, job["id"])
            elif replace_existing_file:
                _remove_job_document_upload(document)
                stored_file_name = None
                original_filename = None

            db = get_db()
            db.execute(
                """
                UPDATE job_documents
                SET record_type = ?, title = ?, file_reference = ?, stored_file_name = ?, original_filename = ?,
                    captured_at = ?, owner_name = ?, status = ?, notes = ?
                WHERE id = ?
                """,
                (
                    data["record_type"],
                    data["title"],
                    data["file_reference"],
                    stored_file_name,
                    original_filename,
                    data["captured_at"],
                    data["owner_name"],
                    data["status"],
                    data["notes"],
                    document_id,
                ),
            )
            _create_activity(
                document["customer_id"],
                "System",
                g.user["full_name"] if g.get("user") else "System",
                f"Field record updated: {data['title']}",
                f"{data['record_type']} metadata refreshed on job {job['name']}.",
                data["captured_at"],
            )
            db.commit()
            flash("Field record updated.", "success")
            return redirect(url_for("crm.jobs_execution", job_id=document["job_id"]))

        for error in errors:
            flash(error, "error")

    return render_template(
        "job_documents/form.html",
        mode="edit",
        document=data,
        job=job,
        owners=_owner_choices(),
        document_types=JOB_DOCUMENT_TYPES,
        document_statuses=JOB_DOCUMENT_STATUSES,
    )


@bp.get("/job-documents/<int:document_id>/file")
@roles_required(*ALL_APP_ROLES)
def job_documents_file(document_id):
    document = _fetch_job_document(document_id)
    if document is None:
        abort(404)
    if not document["stored_file_name"]:
        abort(404)

    upload_dir = _job_document_upload_dir()
    file_path = upload_dir / document["stored_file_name"]
    if not file_path.exists():
        abort(404)

    response = send_from_directory(
        upload_dir,
        document["stored_file_name"],
        as_attachment=True,
        download_name=document["original_filename"] or document["stored_file_name"],
    )
    response.direct_passthrough = False
    return response


@bp.post("/job-documents/<int:document_id>/delete")
@roles_required(*FIELD_EXECUTION_MANAGE_ROLES)
def job_documents_delete(document_id):
    document = _fetch_job_document(document_id)
    if document is None:
        abort(404)

    db = get_db()
    _remove_job_document_upload(document)
    db.execute("DELETE FROM job_documents WHERE id = ?", (document_id,))
    _create_activity(
        document["customer_id"],
        "System",
        g.user["full_name"] if g.get("user") else "System",
        f"Field record removed: {document['title']}",
        "A job packet record was removed from field execution.",
    )
    db.commit()
    flash("Field record removed.", "success")
    return redirect(url_for("crm.jobs_execution", job_id=document["job_id"]))


@bp.get("/jobs/<int:job_id>/materials")
@roles_required(*ALL_APP_ROLES)
def job_materials_index(job_id):
    db = get_db()
    job = db.execute(
        """
        SELECT j.*, c.name AS customer_name, q.quote_number
        FROM jobs j
        JOIN customers c ON c.id = j.customer_id
        LEFT JOIN quotes q ON q.id = j.quote_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    if job is None:
        abort(404)

    materials = db.execute(
        """
        SELECT jm.*, i.sku, i.item_name, i.category, v.name AS vendor_name
        FROM job_materials jm
        JOIN inventory_items i ON i.id = jm.inventory_item_id
        LEFT JOIN vendors v ON v.id = i.vendor_id
        WHERE jm.job_id = ?
        ORDER BY jm.id DESC
        """,
        (job_id,),
    ).fetchall()
    summary = db.execute(
        """
        SELECT COUNT(*) AS line_count,
               COALESCE(SUM(requested_qty), 0) AS requested_qty,
               COALESCE(SUM(reserved_qty), 0) AS reserved_qty,
               COALESCE(SUM(shortage_qty), 0) AS shortage_qty
        FROM job_materials
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()
    shortage_requests = db.execute(
        """
        SELECT pr.*, v.name AS vendor_name
        FROM purchase_requests pr
        LEFT JOIN vendors v ON v.id = pr.vendor_id
        WHERE pr.job_id = ?
        ORDER BY CASE pr.status
            WHEN 'Open' THEN 1
            WHEN 'Quoted' THEN 2
            WHEN 'Ordered' THEN 3
            WHEN 'Received' THEN 4
            ELSE 5
        END, pr.id DESC
        LIMIT 5
        """,
        (job_id,),
    ).fetchall()

    return render_template(
        "jobs/materials.html",
        job=job,
        materials=materials,
        inventory_items=_inventory_item_choices(),
        purchase_requests=shortage_requests,
        summary=summary,
        purchase_priorities=PURCHASE_PRIORITIES,
    )


@bp.post("/jobs/<int:job_id>/materials")
@roles_required(*MATERIAL_ROLES)
def job_materials_create(job_id):
    job = _fetch_job(job_id)
    if job is None:
        abort(404)

    data = _material_form_data(request.form)
    errors = _validate_material_form(data)
    item = _fetch_inventory_item(data["inventory_item_id"]) if data["inventory_item_id"] else None
    if item is None:
        errors.append("Inventory item was not found.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("crm.job_materials_index", job_id=job_id))

    available_qty = max(item["stock_on_hand"] - item["reserved_qty"], 0)
    reserved_qty = min(data["requested_qty"], available_qty)
    shortage_qty = round(max(data["requested_qty"] - reserved_qty, 0), 2)
    status = "Reserved" if shortage_qty == 0 else "Partial"
    notes = data["notes"] or (
        "Auto reservation created from the job workflow."
        if shortage_qty == 0
        else "Partial reservation created while the remaining stock is sourced."
    )

    db = get_db()
    job_material_id = db.insert(
        """
        INSERT INTO job_materials (
            branch_id, job_id, inventory_item_id, requested_qty, reserved_qty,
            shortage_qty, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, job_id, item["id"], data["requested_qty"], reserved_qty, shortage_qty, status, notes),
    )
    if reserved_qty > 0:
        db.execute(
            "UPDATE inventory_items SET reserved_qty = reserved_qty + ? WHERE id = ?",
            (reserved_qty, item["id"]),
        )
    if shortage_qty > 0 and data["auto_purchase"]:
        _create_shortage_purchase_request(job, item, job_material_id, shortage_qty, data["purchase_priority"])
    _sync_job_operations_status(job_id)
    db.commit()

    if shortage_qty > 0:
        flash(
            f"Material reserved partially. {shortage_qty:,.2f} still needs to be sourced for this job.",
            "warning",
        )
    else:
        flash("Material reserved against the job.", "success")
    return redirect(url_for("crm.job_materials_index", job_id=job_id))


@bp.post("/job-materials/<int:material_id>/delete")
@roles_required(*MATERIAL_ROLES)
def job_materials_delete(material_id):
    material = _fetch_job_material(material_id)
    if material is None:
        abort(404)

    item = _fetch_inventory_item(material["inventory_item_id"])
    if item is None:
        abort(404)

    db = get_db()
    linked_requests = db.execute(
        "SELECT COUNT(*) AS count FROM purchase_requests WHERE job_material_id = ?",
        (material_id,),
    ).fetchone()["count"]
    if linked_requests:
        flash("Close or remove linked purchasing records before deleting this material line.", "error")
        return redirect(url_for("crm.job_materials_index", job_id=material["job_id"]))

    new_reserved_total = max(item["reserved_qty"] - material["reserved_qty"], 0)
    db.execute(
        "UPDATE inventory_items SET reserved_qty = ? WHERE id = ?",
        (new_reserved_total, item["id"]),
    )
    db.execute("DELETE FROM job_materials WHERE id = ?", (material_id,))
    _sync_job_operations_status(material["job_id"])
    db.commit()
    flash("Reserved material line removed from the job.", "success")
    return redirect(url_for("crm.job_materials_index", job_id=material["job_id"]))


@bp.get("/purchasing")
@roles_required(*ALL_APP_ROLES)
def purchasing_index():
    status = request.args.get("status", "").strip()
    params = []
    sql = """
        SELECT pr.*, v.name AS vendor_name, j.name AS job_name, c.id AS customer_id,
               c.name AS customer_name, i.item_name, i.sku
        FROM purchase_requests pr
        LEFT JOIN vendors v ON v.id = pr.vendor_id
        LEFT JOIN jobs j ON j.id = pr.job_id
        LEFT JOIN customers c ON c.id = j.customer_id
        LEFT JOIN inventory_items i ON i.id = pr.inventory_item_id
    """
    if status:
        sql += " WHERE pr.status = ?"
        params.append(status)
    sql += """
        ORDER BY CASE pr.status
            WHEN 'Open' THEN 1
            WHEN 'Quoted' THEN 2
            WHEN 'Ordered' THEN 3
            WHEN 'Received' THEN 4
            ELSE 5
        END, pr.needed_by IS NULL, pr.needed_by, pr.id DESC
    """

    db = get_db()
    requests = db.execute(sql, params).fetchall()
    summary = {
        "open": db.execute("SELECT COUNT(*) AS count FROM purchase_requests WHERE status IN ('Open', 'Quoted', 'Ordered')").fetchone()["count"],
        "high_priority": db.execute("SELECT COUNT(*) AS count FROM purchase_requests WHERE priority = 'high'").fetchone()["count"],
        "due_soon": db.execute(
            "SELECT COUNT(*) AS count FROM purchase_requests WHERE needed_by IS NOT NULL AND status IN ('Open', 'Quoted', 'Ordered')"
        ).fetchone()["count"],
        "vendors": db.execute("SELECT COUNT(*) AS count FROM vendors").fetchone()["count"],
    }
    return render_template(
        "purchasing/index.html",
        purchase_requests=requests,
        selected_status=status,
        status_options=PURCHASE_REQUEST_STATUSES,
        summary=summary,
    )


@bp.route("/purchasing/new", methods=("GET", "POST"))
@roles_required(*PURCHASING_ROLES)
def purchasing_create():
    job_id = _optional_int(request.args.get("job_id"))
    inventory_item_id = _optional_int(request.args.get("inventory_item_id"))
    job_material_id = _optional_int(request.args.get("job_material_id"))
    job = _fetch_job(job_id) if job_id else None
    item = _fetch_inventory_item(inventory_item_id) if inventory_item_id else None
    data = _purchase_request_form_data(request.form) if request.method == "POST" else {
        "vendor_id": item["vendor_id"] if item else None,
        "job_id": job_id,
        "job_material_id": job_material_id,
        "inventory_item_id": inventory_item_id,
        "title": f"{job['name']} purchase follow-up" if job else "",
        "details": "",
        "requested_qty": None,
        "ordered_qty": 0,
        "received_qty": 0,
        "priority": "medium",
        "status": "Open",
        "owner_name": g.user["full_name"] if g.get("user") else "",
        "needed_by": job["scheduled_start"] if job else None,
        "eta_date": job["scheduled_start"] if job else None,
        "vendor_notes": "Initial supplier outreach pending.",
    }

    if request.method == "POST":
        errors = _validate_purchase_request_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                INSERT INTO purchase_requests (
                    branch_id, vendor_id, job_id, job_material_id, inventory_item_id, title, details,
                    requested_qty, ordered_qty, received_qty, priority, status, owner_name, needed_by,
                    eta_date, vendor_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["vendor_id"],
                    data["job_id"],
                    data["job_material_id"],
                    data["inventory_item_id"],
                    data["title"],
                    data["details"],
                    data["requested_qty"],
                    data["ordered_qty"],
                    data["received_qty"],
                    data["priority"],
                    data["status"],
                    data["owner_name"],
                    data["needed_by"],
                    data["eta_date"],
                    data["vendor_notes"],
                ),
            )
            db.commit()
            flash("Purchase request created.", "success")
            return redirect(url_for("crm.purchasing_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "purchasing/form.html",
        mode="create",
        purchase_request=data,
        vendors=_vendor_choices(),
        jobs=_job_choices(),
        inventory_items=_inventory_item_choices(),
        priorities=PURCHASE_PRIORITIES,
        statuses=PURCHASE_REQUEST_STATUSES,
        owners=_owner_choices(),
    )


@bp.route("/purchasing/<int:request_id>/edit", methods=("GET", "POST"))
@roles_required(*PURCHASING_ROLES)
def purchasing_edit(request_id):
    purchase_request = _fetch_purchase_request(request_id)
    if purchase_request is None:
        abort(404)

    data = dict(purchase_request)
    if request.method == "POST":
        data = _purchase_request_form_data(request.form)
        errors = _validate_purchase_request_form(data)
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE purchase_requests
                SET vendor_id = ?, job_id = ?, job_material_id = ?, inventory_item_id = ?, title = ?,
                    details = ?, requested_qty = ?, ordered_qty = ?, received_qty = ?, priority = ?,
                    status = ?, owner_name = ?, needed_by = ?, eta_date = ?, vendor_notes = ?
                WHERE id = ?
                """,
                (
                    data["vendor_id"],
                    data["job_id"],
                    data["job_material_id"],
                    data["inventory_item_id"],
                    data["title"],
                    data["details"],
                    data["requested_qty"],
                    data["ordered_qty"],
                    data["received_qty"],
                    data["priority"],
                    data["status"],
                    data["owner_name"],
                    data["needed_by"],
                    data["eta_date"],
                    data["vendor_notes"],
                    request_id,
                ),
            )
            db.commit()
            flash("Purchase request updated.", "success")
            return redirect(url_for("crm.purchasing_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "purchasing/form.html",
        mode="edit",
        purchase_request=data,
        vendors=_vendor_choices(),
        jobs=_job_choices(),
        inventory_items=_inventory_item_choices(),
        priorities=PURCHASE_PRIORITIES,
        statuses=PURCHASE_REQUEST_STATUSES,
        owners=_owner_choices(),
    )


@bp.post("/purchasing/<int:request_id>/delete")
@roles_required(*PURCHASING_ROLES)
def purchasing_delete(request_id):
    purchase_request = _fetch_purchase_request(request_id)
    if purchase_request is None:
        abort(404)

    db = get_db()
    db.execute("DELETE FROM purchase_requests WHERE id = ?", (request_id,))
    db.commit()
    flash("Purchase request removed.", "success")
    return redirect(url_for("crm.purchasing_index"))


@bp.get("/inventory")
@roles_required(*ALL_APP_ROLES)
def inventory_index():
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    params = []
    conditions = []
    sql = """
        SELECT i.*, v.name AS vendor_name,
               (i.stock_on_hand - i.reserved_qty) AS available_qty,
               (SELECT COUNT(*) FROM job_materials jm WHERE jm.inventory_item_id = i.id) AS reservation_count
        FROM inventory_items i
        LEFT JOIN vendors v ON v.id = i.vendor_id
    """

    if category:
        conditions.append("i.category = ?")
        params.append(category)
    if status:
        conditions.append("i.status = ?")
        params.append(status)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY i.category, i.item_name"

    db = get_db()
    inventory_items = db.execute(sql, params).fetchall()
    purchase_requests = db.execute(
        """
        SELECT pr.*, v.name AS vendor_name, j.name AS job_name, c.id AS customer_id,
               c.name AS customer_name, ii.item_name, ii.sku
        FROM purchase_requests pr
        LEFT JOIN vendors v ON v.id = pr.vendor_id
        LEFT JOIN jobs j ON j.id = pr.job_id
        LEFT JOIN customers c ON c.id = j.customer_id
        LEFT JOIN inventory_items ii ON ii.id = pr.inventory_item_id
        ORDER BY CASE pr.priority
            WHEN 'high' THEN 1
            WHEN 'medium' THEN 2
            ELSE 3
        END, pr.needed_by IS NULL, pr.needed_by, pr.id DESC
        LIMIT 6
        """
    ).fetchall()
    inventory_summary = {
        "items": db.execute("SELECT COUNT(*) AS count FROM inventory_items").fetchone()["count"],
        "reserved": db.execute("SELECT COALESCE(SUM(reserved_qty), 0) AS total FROM inventory_items").fetchone()["total"],
        "available": db.execute(
            "SELECT COALESCE(SUM(stock_on_hand - reserved_qty), 0) AS total FROM inventory_items"
        ).fetchone()["total"],
        "purchase_requests": db.execute("SELECT COUNT(*) AS count FROM purchase_requests").fetchone()["count"],
    }

    return render_template(
        "inventory/index.html",
        inventory_items=inventory_items,
        purchase_requests=purchase_requests,
        inventory_summary=inventory_summary,
        selected_category=category,
        selected_status=status,
        categories=INVENTORY_CATEGORIES,
        statuses=INVENTORY_STATUSES,
    )


@bp.route("/inventory/new", methods=("GET", "POST"))
@roles_required(*INVENTORY_MANAGE_ROLES)
def inventory_create():
    data = _inventory_form_data(request.form) if request.method == "POST" else {
        "vendor_id": None,
        "sku": "",
        "item_name": "",
        "category": "Roofing",
        "stock_on_hand": None,
        "unit_cost": None,
        "unit_price": None,
        "status": "Healthy",
    }

    if request.method == "POST":
        errors = _validate_inventory_form(data)
        existing_sku = (
            get_db().execute("SELECT id FROM inventory_items WHERE sku = ?", (data["sku"],)).fetchone()
            if data["sku"]
            else None
        )
        if existing_sku is not None:
            errors.append("SKU must be unique inside the branch inventory list.")
        if not errors:
            db = get_db()
            db.execute(
                """
                INSERT INTO inventory_items (
                    branch_id, vendor_id, sku, item_name, category, stock_on_hand,
                    reserved_qty, unit_cost, unit_price, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["vendor_id"],
                    data["sku"],
                    data["item_name"],
                    data["category"],
                    data["stock_on_hand"],
                    0,
                    data["unit_cost"],
                    data["unit_price"],
                    data["status"],
                ),
            )
            db.commit()
            flash(f"Inventory item '{data['item_name']}' created.", "success")
            return redirect(url_for("crm.inventory_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "inventory/form.html",
        mode="create",
        item=data,
        vendors=_vendor_choices(),
        categories=INVENTORY_CATEGORIES,
        statuses=INVENTORY_STATUSES,
        current_reserved_qty=0,
    )


@bp.route("/inventory/<int:item_id>/edit", methods=("GET", "POST"))
@roles_required(*INVENTORY_MANAGE_ROLES)
def inventory_edit(item_id):
    item = _fetch_inventory_item(item_id)
    if item is None:
        abort(404)

    data = dict(item)
    if request.method == "POST":
        data = _inventory_form_data(request.form)
        errors = _validate_inventory_form(data, item["reserved_qty"])
        existing_sku = (
            get_db().execute("SELECT id FROM inventory_items WHERE sku = ?", (data["sku"],)).fetchone()
            if data["sku"]
            else None
        )
        if existing_sku is not None and existing_sku["id"] != item_id:
            errors.append("SKU must be unique inside the branch inventory list.")
        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE inventory_items
                SET vendor_id = ?, sku = ?, item_name = ?, category = ?, stock_on_hand = ?,
                    unit_cost = ?, unit_price = ?, status = ?
                WHERE id = ?
                """,
                (
                    data["vendor_id"],
                    data["sku"],
                    data["item_name"],
                    data["category"],
                    data["stock_on_hand"],
                    data["unit_cost"],
                    data["unit_price"],
                    data["status"],
                    item_id,
                ),
            )
            db.commit()
            flash(f"Inventory item '{data['item_name']}' updated.", "success")
            return redirect(url_for("crm.inventory_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "inventory/form.html",
        mode="edit",
        item=data,
        vendors=_vendor_choices(),
        categories=INVENTORY_CATEGORIES,
        statuses=INVENTORY_STATUSES,
        current_reserved_qty=item["reserved_qty"],
    )


@bp.post("/inventory/<int:item_id>/delete")
@roles_required(*INVENTORY_MANAGE_ROLES)
def inventory_delete(item_id):
    item = _fetch_inventory_item(item_id)
    if item is None:
        abort(404)

    db = get_db()
    linked_materials = db.execute(
        "SELECT COUNT(*) AS count FROM job_materials WHERE inventory_item_id = ?",
        (item_id,),
    ).fetchone()["count"]
    if linked_materials or item["reserved_qty"] > 0:
        flash("Inventory item cannot be deleted while job reservations still reference it.", "error")
        return redirect(url_for("crm.inventory_index"))

    db.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
    db.commit()
    flash(f"Inventory item '{item['item_name']}' deleted.", "success")
    return redirect(url_for("crm.inventory_index"))


@bp.get("/dispatch")
@roles_required(*ALL_APP_ROLES)
def dispatch_index():
    status = request.args.get("status", "").strip()
    params = []
    sql = """
        SELECT d.*, j.name AS job_name, c.id AS customer_id, c.name AS customer_name,
               (SELECT COUNT(*) FROM job_materials jm WHERE jm.job_id = d.job_id) AS material_count
        FROM deliveries d
        LEFT JOIN jobs j ON j.id = d.job_id
        LEFT JOIN customers c ON c.id = j.customer_id
    """
    if status:
        sql += " WHERE d.status = ?"
        params.append(status)
    sql += " ORDER BY d.eta"

    db = get_db()
    deliveries = db.execute(sql, params).fetchall()
    ready_jobs = db.execute(
        """
        SELECT *
        FROM (
            SELECT j.id, j.name, c.name AS customer_name, j.scheduled_start,
                   COALESCE(SUM(jm.reserved_qty), 0) AS reserved_qty
            FROM jobs j
            JOIN customers c ON c.id = j.customer_id
            LEFT JOIN job_materials jm ON jm.job_id = j.id
            GROUP BY j.id, j.name, c.name, j.scheduled_start
        ) ready
        WHERE ready.reserved_qty > 0
        ORDER BY ready.scheduled_start IS NULL, ready.scheduled_start, ready.id DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "dispatch/index.html",
        deliveries=deliveries,
        ready_jobs=ready_jobs,
        selected_status=status,
        status_options=DELIVERY_STATUSES,
    )


@bp.route("/dispatch/new", methods=("GET", "POST"))
@roles_required(*DISPATCH_MANAGE_ROLES)
def dispatch_create():
    job_id = _optional_int(request.args.get("job_id"))
    job = _fetch_job(job_id) if job_id else None
    data = _delivery_form_data(request.form) if request.method == "POST" else {
        "job_id": job["id"] if job else None,
        "route_name": f"{job['name']} route" if job else "",
        "truck_name": "",
        "eta": f"{job['scheduled_start']} 07:30" if job and job["scheduled_start"] else None,
        "status": "Scheduled",
        "load_percent": 100 if job else 0,
        "notes": f"Initial delivery for {job['name']}" if job else "",
    }

    if request.method == "POST":
        errors = _validate_delivery_form(data)
        job = _fetch_job(data["job_id"]) if data["job_id"] else None
        reserved_total = 0
        if job is None:
            errors.append("Selected job was not found.")
        else:
            reserved_total = get_db().execute(
                "SELECT COALESCE(SUM(reserved_qty), 0) AS total FROM job_materials WHERE job_id = ?",
                (job["id"],),
            ).fetchone()["total"]
            if reserved_total <= 0:
                errors.append("Reserve at least one material line before scheduling a delivery.")

        if not errors:
            db = get_db()
            db.execute(
                """
                INSERT INTO deliveries (
                    branch_id, job_id, route_name, truck_name, eta, status, load_percent, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["job_id"],
                    data["route_name"],
                    data["truck_name"],
                    data["eta"],
                    data["status"],
                    data["load_percent"],
                    data["notes"],
                ),
            )
            _sync_job_operations_status(data["job_id"])
            db.commit()
            flash("Delivery scheduled from the dispatch board.", "success")
            return redirect(url_for("crm.dispatch_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "dispatch/form.html",
        mode="create",
        delivery=data,
        jobs=_job_choices(),
        status_options=DELIVERY_STATUSES,
    )


@bp.route("/dispatch/<int:delivery_id>/edit", methods=("GET", "POST"))
@roles_required(*DISPATCH_MANAGE_ROLES)
def dispatch_edit(delivery_id):
    delivery = _fetch_delivery(delivery_id)
    if delivery is None:
        abort(404)

    data = dict(delivery)
    if request.method == "POST":
        data = _delivery_form_data(request.form)
        errors = _validate_delivery_form(data)
        job = _fetch_job(data["job_id"]) if data["job_id"] else None
        if job is None:
            errors.append("Selected job was not found.")
        else:
            reserved_total = get_db().execute(
                "SELECT COALESCE(SUM(reserved_qty), 0) AS total FROM job_materials WHERE job_id = ?",
                (job["id"],),
            ).fetchone()["total"]
            if reserved_total <= 0:
                errors.append("Reserve at least one material line before dispatching this job.")

        if not errors:
            db = get_db()
            db.execute(
                """
                UPDATE deliveries
                SET job_id = ?, route_name = ?, truck_name = ?, eta = ?, status = ?,
                    load_percent = ?, notes = ?
                WHERE id = ?
                """,
                (
                    data["job_id"],
                    data["route_name"],
                    data["truck_name"],
                    data["eta"],
                    data["status"],
                    data["load_percent"],
                    data["notes"],
                    delivery_id,
                ),
            )
            if delivery["job_id"] != data["job_id"] and delivery["job_id"]:
                _sync_job_operations_status(delivery["job_id"])
            _sync_job_operations_status(data["job_id"])
            db.commit()
            flash("Delivery updated.", "success")
            return redirect(url_for("crm.dispatch_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "dispatch/form.html",
        mode="edit",
        delivery=data,
        jobs=_job_choices(),
        status_options=DELIVERY_STATUSES,
    )


@bp.post("/dispatch/<int:delivery_id>/delete")
@roles_required(*DISPATCH_MANAGE_ROLES)
def dispatch_delete(delivery_id):
    delivery = _fetch_delivery(delivery_id)
    if delivery is None:
        abort(404)

    db = get_db()
    db.execute("DELETE FROM deliveries WHERE id = ?", (delivery_id,))
    if delivery["job_id"]:
        _sync_job_operations_status(delivery["job_id"])
    db.commit()
    flash("Delivery removed from the dispatch board.", "success")
    return redirect(url_for("crm.dispatch_index"))


@bp.get("/invoices")
@roles_required(*ALL_APP_ROLES)
def invoices_index():
    status = request.args.get("status", "").strip()
    params = []
    sql = """
        SELECT i.*, c.name AS customer_name, j.name AS job_name, q.quote_number,
               co.change_number, co.title AS change_order_title,
               (SELECT COUNT(*) FROM invoice_payments ip WHERE ip.invoice_id = i.id) AS payment_count,
               (SELECT MAX(payment_date) FROM invoice_payments ip WHERE ip.invoice_id = i.id) AS last_payment_date
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN jobs j ON j.id = i.job_id
        LEFT JOIN quotes q ON q.id = i.quote_id
        LEFT JOIN change_orders co ON co.id = i.change_order_id
    """
    if status:
        sql += " WHERE i.status = ?"
        params.append(status)
    sql += " ORDER BY i.id DESC"
    invoices = get_db().execute(sql, params).fetchall()
    return render_template(
        "invoices/index.html",
        invoices=invoices,
        selected_status=status,
        status_options=INVOICE_STATUSES,
    )


@bp.route("/invoices/new", methods=("GET", "POST"))
@roles_required(*INVOICE_ROLES)
def invoices_create():
    job_id = _optional_int(request.args.get("job_id"))
    change_order_id = _optional_int(request.args.get("change_order_id"))
    job = _fetch_job(job_id) if job_id else None
    change_order = _fetch_change_order(change_order_id) if change_order_id else None
    if job is None and change_order is not None:
        job = _fetch_job(change_order["job_id"])
    quote = _fetch_quote(job["quote_id"]) if job and job["quote_id"] else None
    if quote is None and change_order and change_order["quote_id"]:
        quote = _fetch_quote(change_order["quote_id"])
    default_amount = (
        change_order["amount"]
        if change_order is not None
        else (job["committed_revenue"] if job else (quote["amount"] if quote else None))
    )
    data = _invoice_form_data(request.form) if request.method == "POST" else {
        "quote_id": quote["id"] if quote else None,
        "change_order_id": change_order["id"] if change_order else None,
        "customer_id": job["customer_id"] if job else None,
        "job_id": job["id"] if job else None,
        "invoice_number": _next_document_number("INV", "invoices", "invoice_number"),
        "billing_type": "Change Order" if change_order else "Standard",
        "application_number": "",
        "status": "Issued",
        "amount": default_amount,
        "issued_date": datetime.now().date().isoformat(),
        "due_date": None,
        "billing_period_start": change_order["requested_date"] if change_order else None,
        "billing_period_end": change_order["approved_date"] if change_order else None,
        "retainage_pct": 0,
        "retainage_held": 0,
        "remaining_balance": default_amount,
    }

    if request.method == "POST":
        errors = _validate_invoice_form(data)
        linked_change_order = _fetch_change_order(data["change_order_id"]) if data["change_order_id"] else None
        linked_job = _fetch_job(data["job_id"]) if data["job_id"] else None
        linked_quote = _fetch_quote(data["quote_id"]) if data["quote_id"] else None
        if data["billing_type"] == "Change Order" and linked_change_order is None:
            errors.append("Select an approved, billable change order for this invoice.")
        if linked_job and data["customer_id"] != linked_job["customer_id"]:
            errors.append("Invoice customer must match the linked job.")
        if linked_quote and data["customer_id"] != linked_quote["customer_id"]:
            errors.append("Invoice customer must match the linked quote.")
        if linked_change_order:
            if linked_change_order["status"] not in ("Approved", "Invoiced"):
                errors.append("Only approved change orders can be billed.")
            if not linked_change_order["is_billable"]:
                errors.append("This change order is marked non-billable.")
            if linked_job and linked_change_order["job_id"] != linked_job["id"]:
                errors.append("Change order must belong to the same job as the invoice.")
            if data["customer_id"] != linked_change_order["customer_id"]:
                errors.append("Invoice customer must match the linked change order.")
            if data["quote_id"] and linked_change_order["quote_id"] and data["quote_id"] != linked_change_order["quote_id"]:
                errors.append("Invoice quote must match the linked change order.")
        if not errors:
            aging_bucket = _compute_invoice_aging_bucket(data["due_date"], data["remaining_balance"])
            db = get_db()
            db.execute(
                """
                INSERT INTO invoices (
                    branch_id, quote_id, change_order_id, customer_id, job_id, invoice_number, billing_type,
                    application_number, status, amount, issued_date, due_date, billing_period_start,
                    billing_period_end, retainage_pct, retainage_held, aging_bucket, remaining_balance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    data["quote_id"],
                    data["change_order_id"],
                    data["customer_id"],
                    data["job_id"],
                    data["invoice_number"],
                    data["billing_type"],
                    data["application_number"],
                    data["status"],
                    data["amount"],
                    data["issued_date"],
                    data["due_date"],
                    data["billing_period_start"],
                    data["billing_period_end"],
                    data["retainage_pct"],
                    data["retainage_held"],
                    aging_bucket,
                    data["remaining_balance"],
                ),
            )
            if linked_change_order and data["billing_type"] == "Change Order":
                db.execute("UPDATE change_orders SET status = ? WHERE id = ?", ("Invoiced", linked_change_order["id"]))
            db.commit()
            flash("Invoice created.", "success")
            return redirect(url_for("crm.invoices_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "invoices/form.html",
        mode="create",
        invoice=data,
        customers=_customer_choices(),
        jobs=_job_choices(),
        quotes=_quote_choices(),
        change_orders=(
            _change_order_choices(job["id"], job["customer_id"], approved_only=True, billable_only=True)
            if job
            else _change_order_choices(approved_only=True, billable_only=True)
        ),
        billing_type_options=INVOICE_BILLING_TYPES,
        status_options=INVOICE_STATUSES,
    )


@bp.route("/invoices/<int:invoice_id>/edit", methods=("GET", "POST"))
@roles_required(*INVOICE_ROLES)
def invoices_edit(invoice_id):
    invoice = _fetch_invoice(invoice_id)
    if invoice is None:
        abort(404)

    data = dict(invoice)
    if request.method == "POST":
        data = _invoice_form_data(request.form)
        errors = _validate_invoice_form(data)
        linked_change_order = _fetch_change_order(data["change_order_id"]) if data["change_order_id"] else None
        linked_job = _fetch_job(data["job_id"]) if data["job_id"] else None
        linked_quote = _fetch_quote(data["quote_id"]) if data["quote_id"] else None
        if data["billing_type"] == "Change Order" and linked_change_order is None:
            errors.append("Select an approved, billable change order for this invoice.")
        if linked_job and data["customer_id"] != linked_job["customer_id"]:
            errors.append("Invoice customer must match the linked job.")
        if linked_quote and data["customer_id"] != linked_quote["customer_id"]:
            errors.append("Invoice customer must match the linked quote.")
        if linked_change_order:
            if linked_change_order["status"] not in ("Approved", "Invoiced"):
                errors.append("Only approved change orders can be billed.")
            if not linked_change_order["is_billable"]:
                errors.append("This change order is marked non-billable.")
            if linked_job and linked_change_order["job_id"] != linked_job["id"]:
                errors.append("Change order must belong to the same job as the invoice.")
            if data["customer_id"] != linked_change_order["customer_id"]:
                errors.append("Invoice customer must match the linked change order.")
            if data["quote_id"] and linked_change_order["quote_id"] and data["quote_id"] != linked_change_order["quote_id"]:
                errors.append("Invoice quote must match the linked change order.")
        if not errors:
            aging_bucket = _compute_invoice_aging_bucket(data["due_date"], data["remaining_balance"])
            db = get_db()
            db.execute(
                """
                UPDATE invoices
                SET quote_id = ?, change_order_id = ?, customer_id = ?, job_id = ?, invoice_number = ?,
                    billing_type = ?, application_number = ?, status = ?, amount = ?, issued_date = ?,
                    due_date = ?, billing_period_start = ?, billing_period_end = ?, retainage_pct = ?,
                    retainage_held = ?, aging_bucket = ?, remaining_balance = ?
                WHERE id = ?
                """,
                (
                    data["quote_id"],
                    data["change_order_id"],
                    data["customer_id"],
                    data["job_id"],
                    data["invoice_number"],
                    data["billing_type"],
                    data["application_number"],
                    data["status"],
                    data["amount"],
                    data["issued_date"],
                    data["due_date"],
                    data["billing_period_start"],
                    data["billing_period_end"],
                    data["retainage_pct"],
                    data["retainage_held"],
                    aging_bucket,
                    data["remaining_balance"],
                    invoice_id,
                ),
            )
            if invoice["change_order_id"] and (
                data["change_order_id"] != invoice["change_order_id"] or data["billing_type"] != "Change Order"
            ):
                other_links = db.execute(
                    "SELECT COUNT(*) AS count FROM invoices WHERE change_order_id = ? AND id != ?",
                    (invoice["change_order_id"], invoice_id),
                ).fetchone()["count"]
                if other_links == 0:
                    db.execute(
                        "UPDATE change_orders SET status = CASE WHEN status = 'Invoiced' THEN 'Approved' ELSE status END WHERE id = ?",
                        (invoice["change_order_id"],),
                    )
            if linked_change_order and data["billing_type"] == "Change Order":
                db.execute("UPDATE change_orders SET status = ? WHERE id = ?", ("Invoiced", linked_change_order["id"]))
            db.commit()
            flash("Invoice updated.", "success")
            return redirect(url_for("crm.invoices_index"))

        for error in errors:
            flash(error, "error")

    return render_template(
        "invoices/form.html",
        mode="edit",
        invoice=data,
        customers=_customer_choices(),
        jobs=_job_choices(),
        quotes=_quote_choices(),
        change_orders=_change_order_choices(approved_only=True, billable_only=True),
        billing_type_options=INVOICE_BILLING_TYPES,
        status_options=INVOICE_STATUSES,
    )


@bp.route("/invoices/<int:invoice_id>/payment", methods=("GET", "POST"))
@roles_required(*INVOICE_ROLES)
def invoices_payment(invoice_id):
    invoice = _fetch_invoice(invoice_id)
    if invoice is None:
        abort(404)

    accounts = _bank_account_choices()
    payment_data = {
        "payment_amount": "",
        "payment_date": datetime.now().date().isoformat(),
        "payment_method": "ACH",
        "deposit_account_id": accounts[0]["id"] if accounts else None,
        "reference_number": "",
        "notes": "",
    }
    payment_history = get_db().execute(
        """
        SELECT ip.*, b.account_name
        FROM invoice_payments ip
        LEFT JOIN bank_accounts b ON b.id = ip.deposit_account_id
        WHERE ip.invoice_id = ?
        ORDER BY ip.payment_date DESC, ip.id DESC
        """,
        (invoice_id,),
    ).fetchall()

    if request.method == "POST":
        payment_data = {
            "payment_amount": request.form.get("payment_amount", "").strip(),
            "payment_date": _optional_date(request.form.get("payment_date")),
            "payment_method": request.form.get("payment_method", "ACH").strip(),
            "deposit_account_id": _optional_int(request.form.get("deposit_account_id")),
            "reference_number": request.form.get("reference_number", "").strip(),
            "notes": request.form.get("notes", "").strip(),
        }
        payment_amount = _optional_float(payment_data["payment_amount"])
        if payment_amount is None or payment_amount <= 0:
            flash("Payment amount must be greater than zero.", "error")
        elif payment_amount > invoice["remaining_balance"]:
            flash("Payment amount cannot exceed the remaining balance.", "error")
        elif not payment_data["payment_date"]:
            flash("Payment date is required.", "error")
        elif payment_data["payment_method"] not in PAYMENT_METHODS:
            flash("Payment method is invalid.", "error")
        elif payment_data["deposit_account_id"] is None:
            flash("Select the deposit account that received the payment.", "error")
        else:
            new_remaining = round(invoice["remaining_balance"] - payment_amount, 2)
            new_status = "Paid" if new_remaining == 0 else "Partial Paid"
            aging_bucket = _compute_invoice_aging_bucket(invoice["due_date"], new_remaining)
            db = get_db()
            db.execute(
                """
                INSERT INTO invoice_payments (
                    branch_id, invoice_id, customer_id, deposit_account_id, payment_date, payment_amount,
                    payment_method, reference_number, posted_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    invoice_id,
                    invoice["customer_id"],
                    payment_data["deposit_account_id"],
                    payment_data["payment_date"],
                    payment_amount,
                    payment_data["payment_method"],
                    payment_data["reference_number"],
                    g.user["full_name"] if g.get("user") else "System",
                    payment_data["notes"],
                ),
            )
            db.execute(
                """
                UPDATE invoices
                SET status = ?, remaining_balance = ?, aging_bucket = ?
                WHERE id = ?
                """,
                (new_status, new_remaining, aging_bucket, invoice_id),
            )
            if invoice["customer_id"]:
                _create_activity(
                    invoice["customer_id"],
                    "System",
                    g.user["full_name"] if g.get("user") else "System",
                    f"Payment posted: {invoice['invoice_number']}",
                    f"{payment_data['payment_method']} payment of ${payment_amount:,.2f} posted on {payment_data['payment_date']}.",
                    payment_data["payment_date"],
                )
            db.commit()
            flash("Payment recorded.", "success")
            return redirect(url_for("crm.invoices_index"))

    return render_template(
        "invoices/payment.html",
        invoice=invoice,
        payment=payment_data,
        payment_history=payment_history,
        payment_methods=PAYMENT_METHODS,
        deposit_accounts=accounts,
    )


@bp.post("/invoices/<int:invoice_id>/delete")
@roles_required(*INVOICE_ROLES)
def invoices_delete(invoice_id):
    invoice = _fetch_invoice(invoice_id)
    if invoice is None:
        abort(404)

    db = get_db()
    if invoice["change_order_id"]:
        other_links = db.execute(
            "SELECT COUNT(*) AS count FROM invoices WHERE change_order_id = ? AND id != ?",
            (invoice["change_order_id"], invoice_id),
        ).fetchone()["count"]
        if other_links == 0:
            db.execute(
                "UPDATE change_orders SET status = CASE WHEN status = 'Invoiced' THEN 'Approved' ELSE status END WHERE id = ?",
                (invoice["change_order_id"],),
            )
    db.execute("DELETE FROM invoice_payments WHERE invoice_id = ?", (invoice_id,))
    db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    db.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("crm.invoices_index"))
