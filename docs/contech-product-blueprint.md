# ConTech Product Blueprint

Date: April 2, 2026

## Product aim

ConTech is a construction CRM and lead-tracking platform designed for roofing and siding companies. The base product should feel familiar enough for teams moving from existing contractor CRMs, while giving owners a more connected picture of sales, fulfillment, inventory, and cash flow.

## Confirmed phase-one decisions

1. Phase one is single-branch.
2. Phase one supports both residential and commercial workflows.
3. Accounting in phase one is full bookkeeping and payroll, not just operational visibility.
4. Customer portal and supplier integrations are planned for a later release.

## Design principles

1. Keep the workflow job-centered.
2. Reduce duplicate entry between sales, operations, and accounting.
3. Make key risks obvious: stalled leads, late deliveries, low stock, overdue invoices, and shrinking margin.
4. Keep the interface visually clean, block-based, and easy to scan.
5. Build for office and field handoff from day one.

## Primary users

### Owner / admin

Needs:
- Total pipeline visibility
- Profitability and cash tracking
- Team activity and accountability
- Cross-module reporting

### Sales rep

Needs:
- Fast lead capture
- Inspection notes
- Quote generation
- Customer communication
- Clear follow-up tasks

### Dispatcher / operations coordinator

Needs:
- Delivery scheduling
- Crew and truck assignment
- Material readiness
- Status updates and bottleneck alerts

### Inventory / purchasing manager

Needs:
- Stock control by location
- Reorder triggers
- Vendor management
- Job reservations

### Accounting / bookkeeper

Needs:
- Invoice and payment visibility
- Inflow vs outflow
- Vendor bills
- Card activity
- Payroll review

## Core domain model

### Lead

Fields:
- lead source
- assigned rep
- property address
- trade interest
- inspection date
- lead score
- estimated deal value

### Customer

Fields:
- customer type
- billing contact
- project contacts
- service address
- documents
- notes
- lifetime value

### Property / site

Fields:
- building type
- roof type
- siding type
- measurement data
- photos
- permits
- delivery constraints

### Opportunity

Fields:
- stage
- probability
- quote package
- trade mix
- projected close date
- projected margin

### Quote

Fields:
- version
- line items
- option set
- labor
- materials
- discount
- tax
- approval status

### Sales order / job

Fields:
- scope
- committed revenue
- scheduled start
- crew assignment
- delivery windows
- production status

### Dispatch record

Fields:
- delivery type
- truck
- driver
- ETA
- status
- customer notification state

### Inventory item

Fields:
- SKU
- category
- supplier
- warehouse
- truck stock
- reserved qty
- reorder point
- unit cost
- sell price

### Invoice / payment

Fields:
- job
- invoice status
- due date
- payment method
- deposit status
- remaining balance

### Vendor / payable

Fields:
- vendor type
- open bills
- card used
- expected payment date
- linked jobs

### Employee / payroll record

Fields:
- role
- timesheet summary
- hourly vs commission mix
- payroll period
- labor cost by job

## Base navigation

Main modules:

1. Dashboard
2. Sales
3. Customers
4. Reports
5. Dispatch
6. Inventory
7. Accounting

Support navigation:

- search
- notifications
- quick actions
- saved views
- user role switcher

## Module definitions

### Dashboard

Purpose:
- Daily command center for leadership and team leads.

Must show:
- pipeline value
- quotes awaiting signature
- deliveries today
- low-stock alerts
- receivables due soon
- team follow-ups

### Sales

Purpose:
- Move leads from intake to signed work.

Base features:
- lead board by stage
- inspection scheduling
- quote builder
- good / better / best options
- order conversion
- invoice handoff

### Customers

Purpose:
- Hold the full relationship history for the customer and their property.

Base features:
- customer profile
- project list
- contacts
- notes
- communication history
- document access

### Reports

Purpose:
- Show financial, sales, and retention trends.

Base features:
- revenue trend
- gross profit trend
- quote conversion
- customer churn
- sales cycle duration
- on-time delivery rate
- report library

### Dispatch

Purpose:
- Coordinate deliveries, trucks, crews, and customer updates.

Base features:
- dispatch board
- route / ETA status
- schedule calendar
- crew load view
- customer notification state
- delay alerts

### Inventory

Purpose:
- Manage material control and purchasing decisions.

Base features:
- SKU list
- stock by location
- reserved job stock
- reorder queue
- vendor list
- price and margin visibility

### Accounting

Purpose:
- Provide full bookkeeping and payroll capabilities while still keeping day-to-day operational finance visible.

Base features:
- bank balance summary
- inflow vs outflow
- card usage
- vendor bills
- payroll snapshot
- invoice aging
- deposit tracking
- general ledger
- reconciliations
- journal controls
- payroll processing
- vendor payables workflow

## Core workflows

### Sales to fulfillment

1. Lead created
2. Inspection scheduled
3. Quote assembled from labor, materials, and trade options
4. Customer signs proposal
5. Quote converts to active order / job
6. Materials reserved or ordered
7. Dispatch schedules delivery and crew
8. Invoice and deposit tracking continue through completion

### Inventory to purchasing

1. Quote or job reserves expected materials
2. Availability is checked across warehouse and truck stock
3. Shortages move to reorder queue
4. Buyer selects vendor and confirms timing
5. Delivery status updates the dispatch and job records

### Cash control

1. Deposits requested when quote is approved
2. Progress or final invoices issued from the job
3. Payments update customer, job, and accounting views
4. Vendor bills and payroll update outflow visibility
5. Owners monitor margin drift and outstanding balances

## Initial reporting set

- Pipeline by stage
- Quote conversion by rep
- Average days from lead to signed order
- Revenue by trade
- Gross profit by job
- Material spend by supplier
- Delivery on-time rate
- Inventory shrinkage / stock adjustments
- Accounts receivable aging
- Customer churn / repeat-customer rate

## UI direction

### Visual language

- Soft red and white palette with warm neutrals
- Thick bordered cards and block-style grouping
- Large section headings and compact operational detail
- Minimal clutter, no dense enterprise chrome

### Layout

- Left navigation rail for module switching
- Large command surface with summary strip at top
- Mixed cards, boards, tables, and timelines based on the task
- Responsive collapse for tablets and laptops

### Interaction model

- Quick actions always visible
- Most important statuses color coded
- Related job context shown inline instead of forcing deep page changes
- Multi-step workflows shown as a sequence users can follow at a glance

## Open questions before deeper product buildout

These are the areas that should be confirmed instead of guessed:

1. Should payroll include commission rules for sales reps in phase one, or stay focused on hourly / salary payroll first?
2. Do you want commercial workflows to include phased billing, multi-site jobs, and approval chains immediately, or as a second pass within phase one?
3. Should accounting own tax handling inside ConTech in phase one, or should tax reporting stay limited at first?
4. How detailed should permissions be between sales, dispatch, inventory, and accounting roles in the first release?

## Recommended first build scope after this foundation

Phase 1:
- Dashboard
- Sales pipeline
- Customer records
- Quote to order flow
- Dispatch board
- Inventory catalog with reorder alerts
- Full accounting and payroll foundation for a single branch
- Residential and commercial job handling

Phase 2:
- Customer portal
- Supplier integrations
- Customer portal
- Vendor purchase orders
- Payroll automation
- Deeper reporting and scheduled exports
- Mobile-first field workflows
