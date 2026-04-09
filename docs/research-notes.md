# ConTech Research Notes

Date: April 2, 2026

## Goal

Review current CRM, field-service, and roofing software patterns before defining ConTech's base experience.

## Products reviewed

### AccuLynx

Why it matters:
- Built specifically for roofing operations, not just generic CRM workflows.
- Strong emphasis on lead qualification, supplier-linked estimating, material ordering, payments, and customer visibility.

What stood out:
- AccuLynx positions itself as an all-in-one roofing platform that runs from lead through final payment.
- Recent product content emphasizes live supplier pricing, creating material orders from estimates, and tighter ordering workflows.
- Customer portal content focuses on project visibility, invoice access, payments, and communications in one place.

ConTech implications:
- A roofing-first CRM should keep sales, material planning, production, invoicing, and payment events attached to the same job record.
- Supplier pricing, margin pressure, and material availability should appear early in the sales workflow, not only in back-office tools.
- Customer self-service is a standard expectation once a job is sold.

Sources:
- [AccuLynx homepage](https://acculynx.com/)
- [SRS ordering tools in AccuLynx](https://acculynx.com/srs-ordering-tools-in-acculynx/)
- [Lead Intelligence](https://acculynx.com/roofing-sales-lead-intelligence/)
- [Customer Portal](https://acculynx.com/acculynx-customer-portal-for-roofing-contractors/)
- [Material ordering efficiency](https://acculynx.com/acculynx-material-ordering/)

### JobNimbus

Why it matters:
- One of the most recognizable roofing CRM products and especially strong around estimate speed.
- Good reference for the estimate -> signature -> material order -> invoice flow.

What stood out:
- The estimates product page is centered on building estimates quickly in the field, using supplier pricing and digital signatures.
- Support content shows material orders, invoices, and payments living directly inside the job workflow.
- Estimate documentation explicitly supports multi-trade options like roofing, siding, and gutters.

ConTech implications:
- Sales stages should be grounded in real contracting milestones, not just generic "opportunity" statuses.
- Good / better / best proposals and multi-trade quote tabs should be a first-class concept for roofing and siding.
- Financial documents should be visible on the same record as the customer, property, and job.

Sources:
- [JobNimbus estimates](https://www.jobnimbus.com/estimates)
- [JobNimbus invoicing](https://www.jobnimbus.com/product/invoicing/)
- [Create an estimate](https://support.jobnimbus.com/how-do-i-create-a-proposal)
- [Create a material order](https://support.jobnimbus.com/how-do-i-create-a-material-order-in-the-new-sales-experience)
- [QXO integration](https://www.jobnimbus.com/integrations/qxo)

### Buildertrend

Why it matters:
- Shows how construction businesses expect the handoff from sales to project execution to feel.
- Strong reference for schedule visibility, customer communication, and job-level financial control.

What stood out:
- Buildertrend's sales management positioning connects CRM, proposals, and contract flow into the active build.
- Scheduling content highlights one shared calendar for trades, inspections, and delays, with mobile access and live updates.
- The platform messaging consistently stresses profitability tracking and reducing handoff friction between departments.

ConTech implications:
- ConTech should not separate sales data from fulfillment data once a deal is won.
- A central schedule and customer communication layer should sit above dispatch, not beside it.
- Dashboard reporting needs both operational and financial views.

Sources:
- [Buildertrend homepage](https://buildertrend.com/)
- [Construction sales management software](https://buildertrend.com/sales-process/)
- [Construction CRM](https://buildertrend.com/sales-process/construction-crm/)
- [Construction scheduling software](https://buildertrend.com/project-management/schedule/)
- [Mobile app overview](https://buildertrend.com/how-it-works/platform/app/)

### ServiceTitan

Why it matters:
- Strong benchmark for dispatch boards, inventory control, reporting, payments, and payroll visibility.
- Useful reference for the operations-heavy side of ConTech.

What stood out:
- Dispatch pages emphasize drag-and-drop scheduling, route optimization, property data, and real-time customer updates.
- Inventory content focuses on multi-location stock control, replenishment templates, barcode workflows, and reserved materials.
- Accounting, payments, reporting, and payroll pages show the expectation that cash, labor, and job-cost visibility live close to field activity.

ConTech implications:
- Dispatch should include both a scheduling board and a logistics status layer for deliveries and crews.
- Inventory must support warehouses, trucks, and reserved job stock, not just a flat SKU list.
- Accounting cannot be treated as a disconnected admin screen; users expect operational context tied back to jobs, invoices, and labor.

Sources:
- [Dispatch software](https://www.servicetitan.com/features/dispatch-software)
- [Contractor inventory software](https://www.servicetitan.com/features/contractor-inventory-software)
- [Field reporting software](https://www.servicetitan.com/features/field-reporting-software)
- [Payments](https://www.servicetitan.com/features/payments)
- [Accounting](https://www.servicetitan.com/features/accounting)
- [Contractor payroll software](https://www.servicetitan.com/features/contractor-payroll-software)

## Research summary

Patterns repeated across current platforms:

1. Successful contractor CRMs anchor the workflow around the job, not only the contact.
2. Estimates, material planning, dispatch, invoicing, and payment collection are expected to connect without duplicate entry.
3. Construction users need both office and field views: pipeline, schedule, property details, supplier status, and cash status.
4. Reporting is expected to answer margin, throughput, team performance, and customer retention questions from the same system.
5. Mobile-friendly execution and customer visibility are already standard in the market.

## Product direction for ConTech

ConTech should differentiate by combining:

- Roofing and siding sales workflows that move naturally from inspection to quote to signed work.
- Material-aware operations that expose supplier, stock, and delivery risk before crews are blocked.
- A clean block-style interface that feels simpler than enterprise CRMs without removing operational depth.
- A role-based control center where sales, dispatch, inventory, and accounting still point back to the same customer and property story.
