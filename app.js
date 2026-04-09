const appState = {
  activeView: "dashboard",
};

const views = [
  {
    id: "dashboard",
    icon: "DB",
    label: "Dashboard",
    kicker: "Daily control center",
    description:
      "Leadership overview for quotes, deliveries, stock risk, and cash pressure across the business.",
  },
  {
    id: "sales",
    icon: "SL",
    label: "Sales",
    kicker: "Lead to signed work",
    description:
      "A roofing and siding sales workspace shaped around inspections, proposals, approvals, and invoice handoff.",
  },
  {
    id: "customers",
    icon: "CU",
    label: "Customers",
    kicker: "Relationship and property record",
    description:
      "Customer history, property context, communication, documents, and repeat-business signals in one profile.",
  },
  {
    id: "reports",
    icon: "RP",
    label: "Reports",
    kicker: "Profit and performance visibility",
    description:
      "Financial, operational, and retention reporting designed for owners and department leads.",
  },
  {
    id: "dispatch",
    icon: "DP",
    label: "Dispatch",
    kicker: "Delivery and crew orchestration",
    description:
      "Manage trucks, routes, crews, ETAs, and customer notifications without losing job-level context.",
  },
  {
    id: "inventory",
    icon: "IV",
    label: "Inventory",
    kicker: "Material control",
    description:
      "Stock, purchasing, reservations, price changes, and vendor-linked replenishment for roofing and siding materials.",
  },
  {
    id: "accounting",
    icon: "AC",
    label: "Accounting",
    kicker: "Cash, payables, and payroll pulse",
    description:
      "Operational finance visibility across receivables, vendor outflow, cards, and payroll readiness.",
  },
];

let overviewMetrics = [
  {
    label: "Active Pipeline",
    value: "$846,400",
    trend: "+12% vs last month",
  },
  {
    label: "Quotes Awaiting Signature",
    value: "18",
    trend: "6 due in 48 hrs",
  },
  {
    label: "Deliveries This Week",
    value: "24",
    trend: "3 routes at risk",
  },
  {
    label: "AR Due in 7 Days",
    value: "$92,180",
    trend: "11 invoices open",
  },
];

let dashboardData = {
  focusAreas: [
    "Lead intake -> inspection",
    "Quote -> signed contract",
    "Material order -> delivery",
    "Invoice -> payment",
  ],
  teamPulse: [
    { label: "Sales follow-ups due", value: "27", copy: "4 are overdue by more than 2 days" },
    { label: "Jobs ready for production", value: "9", copy: "6 have all materials reserved" },
    { label: "Vendor bills due this week", value: "$31.8k", copy: "Top vendor: Beacon West" },
    { label: "Gross margin forecast", value: "33.4%", copy: "Down 1.1 pts on two siding jobs" },
  ],
  hotPipeline: [
    {
      name: "Morris Residence",
      subtitle: "Full roof replacement + fascia",
      stage: "Quoted",
      close: "Apr 4",
      value: "$22,400",
      priority: 88,
    },
    {
      name: "Summit Dental Plaza",
      subtitle: "Commercial siding patch + membrane repair",
      stage: "Inspection",
      close: "Apr 8",
      value: "$46,900",
      priority: 72,
    },
    {
      name: "Alder Creek HOA",
      subtitle: "Building C storm restoration",
      stage: "Negotiation",
      close: "Apr 6",
      value: "$118,000",
      priority: 94,
    },
    {
      name: "Meyer Barn Conversion",
      subtitle: "Board and batten siding",
      stage: "New lead",
      close: "Apr 10",
      value: "$31,700",
      priority: 54,
    },
  ],
  dispatch: [
    { time: "7:30", title: "Route 02 / South Yard", copy: "Shingles + ridge cap to Morris Residence", status: "On time" },
    { time: "8:15", title: "Route 04 / Downtown", copy: "Commercial siding packs for Summit Dental Plaza", status: "Driver loading" },
    { time: "10:00", title: "Route 07 / North Loop", copy: "Dumpster swap + underlayment refill", status: "Weather watch" },
  ],
  inventoryRisk: [
    { title: "Charcoal laminate shingles", copy: "18 squares available, 32 reserved by Friday", tone: "danger" },
    { title: "White 6in fascia coil", copy: "Vendor cost increased 7% this week", tone: "warning" },
    { title: "Synthetic underlayment", copy: "Healthy on-hand stock across both yards", tone: "success" },
  ],
  cashSignals: [
    { label: "Deposits collected", value: "$58,400", tag: "8 new approvals" },
    { label: "Invoices overdue", value: "$21,600", tag: "Need customer follow-up" },
    { label: "Open vendor bills", value: "$47,280", tag: "6 due by Monday" },
    { label: "Payroll due Friday", value: "$18,900", tag: "Crew overtime elevated" },
  ],
};

let salesData = {
  lanes: [
    {
      title: "New Leads",
      count: "13 leads / $186k",
      cards: [
        { name: "Bayside Auto Spa", type: "Metal roof retrofit", rep: "Andrea", value: "$54,200" },
        { name: "Jordan Residence", type: "Siding hail claim", rep: "Micah", value: "$18,900" },
      ],
    },
    {
      title: "Inspection",
      count: "8 jobs / $139k",
      cards: [
        { name: "Summit Dental Plaza", type: "Commercial membrane + siding", rep: "Ramon", value: "$46,900" },
        { name: "Lopez Residence", type: "Roof leak + soffit", rep: "Andrea", value: "$14,300" },
      ],
    },
    {
      title: "Quoted",
      count: "18 jobs / $311k",
      cards: [
        { name: "Morris Residence", type: "Architectural shingles", rep: "Micah", value: "$22,400" },
        { name: "Alder Creek HOA", type: "Storm restoration", rep: "Ramon", value: "$118,000" },
        { name: "Edison Church", type: "Fiber cement siding", rep: "Andrea", value: "$39,800" },
      ],
    },
    {
      title: "Won / Ready",
      count: "9 jobs / $210k",
      cards: [
        { name: "Bennett Duplex", type: "Roof + gutters", rep: "Micah", value: "$27,600" },
        { name: "Crescent Bistro", type: "Storefront facade repairs", rep: "Ramon", value: "$41,500" },
      ],
    },
  ],
  quoteOptions: [
    { name: "Good", copy: "IKO Cambridge / 25 yr", amount: "$17,950", tone: "warning" },
    { name: "Better", copy: "Owens Corning Duration / upgraded venting", amount: "$22,400", tone: "success" },
    { name: "Best", copy: "Malarkey Vista + gutter refresh", amount: "$26,780", tone: "default" },
  ],
  orders: [
    { customer: "Bennett Duplex", doc: "Invoice #1042", status: "Deposit paid", amount: "$8,280" },
    { customer: "Crescent Bistro", doc: "Sales Order #225", status: "Materials reserved", amount: "$41,500" },
    { customer: "Morris Residence", doc: "Quote #8891", status: "Signature pending", amount: "$22,400" },
    { customer: "Alder Creek HOA", doc: "Progress Invoice #990", status: "Ready after delivery", amount: "$29,600" },
  ],
  channels: [
    { label: "Referrals", value: 68 },
    { label: "Website leads", value: 54 },
    { label: "Retail partner", value: 31 },
    { label: "Insurance agents", value: 47 },
  ],
  actions: [
    "Send revised HOA proposal with alternate siding panel",
    "Call Morris Residence before quote expires tomorrow",
    "Confirm insurance paperwork for Jordan Residence",
    "Move Bennett Duplex from deposit paid to production ready",
  ],
};

let customerData = {
  cards: [
    {
      name: "Morris Residence",
      line1: "Residential / repeat customer",
      line2: "2 projects in 4 years / strong referral source",
      tags: ["Roofing", "Gutters", "Preferred contact: text"],
    },
    {
      name: "Alder Creek HOA",
      line1: "Multi-building association",
      line2: "Requires board approval and milestone billing",
      tags: ["Commercial", "Storm claims", "Multi-phase"],
    },
    {
      name: "Summit Dental Plaza",
      line1: "Owner-managed commercial property",
      line2: "Tight delivery windows and tenant notice needs",
      tags: ["Commercial", "Delivery access", "After-hours work"],
    },
    {
      name: "Lopez Residence",
      line1: "Single-family homeowner",
      line2: "High engagement, financing questions open",
      tags: ["Residential", "Siding repair", "Needs follow-up"],
    },
  ],
  profile: [
    { label: "Primary contact", value: "Denise Morris / (555) 102-9941" },
    { label: "Property", value: "428 Juniper Ridge Dr, Sacramento, CA" },
    { label: "Trade mix", value: "Roofing, fascia, gutters" },
    { label: "Open items", value: "Quote signed pending deposit request" },
  ],
  timeline: [
    { time: "Mar 31", title: "Inspection completed", copy: "Photos and ventilation notes uploaded from mobile." },
    { time: "Apr 1", title: "Quote sent", copy: "Three-option proposal delivered by email and SMS link." },
    { time: "Apr 2", title: "Follow-up scheduled", copy: "Rep reminder set for 2:00 PM to close before weekend." },
  ],
  loyalty: [
    { label: "Repeat-customer rate", value: "28%" },
    { label: "Churn watch accounts", value: "7" },
    { label: "Avg response SLA", value: "43 min" },
    { label: "Reviews requested", value: "12" },
  ],
};

let reportData = {
  kpis: [
    { label: "Quote win rate", value: "41.8%" },
    { label: "Avg days to close", value: "11.4" },
    { label: "Customer churn", value: "3.2%" },
    { label: "On-time delivery", value: "92%" },
  ],
  revenueBars: [
    { label: "Jan", value: 62, amount: "$342k" },
    { label: "Feb", value: 74, amount: "$401k" },
    { label: "Mar", value: 88, amount: "$468k" },
    { label: "Apr", value: 59, amount: "$311k" },
  ],
  marginByTrade: [
    { label: "Roof replacement", value: "35.4%" },
    { label: "Storm restoration", value: "31.9%" },
    { label: "Siding install", value: "29.6%" },
    { label: "Repair work", value: "42.1%" },
  ],
  library: [
    "Profit by job and trade",
    "Sales by rep and lead source",
    "Material spend by supplier",
    "Inventory adjustments and shrinkage",
    "Accounts receivable aging",
    "Customer churn and repeat rate",
  ],
  notes: [
    { title: "Margin drift warning", copy: "Commercial siding jobs are under target margin because material costs spiked this month." },
    { title: "Healthy pipeline mix", copy: "Referral leads continue to close faster and at higher average contract value." },
    { title: "Retention focus", copy: "Seven prior customers have gone 12+ months without a follow-up touch." },
  ],
};

let dispatchData = {
  routes: [
    { title: "Route 02 / South Yard", copy: "3 stops / 91% loaded / 15 min buffer", value: 91 },
    { title: "Route 04 / Downtown", copy: "2 stops / tight site access / call ahead required", value: 73 },
    { title: "Route 07 / North Loop", copy: "4 stops / weather exposure risk / tarps added", value: 58 },
  ],
  board: [
    { time: "7:30", title: "Morris Residence", copy: "Shingles, ridge vent, drip edge", tag: "Truck 2" },
    { time: "8:15", title: "Summit Dental Plaza", copy: "Siding panels, trim packs, lift coordination", tag: "Truck 4" },
    { time: "10:00", title: "Bennett Duplex", copy: "Dumpster swap and underlayment replenish", tag: "Truck 7" },
    { time: "1:30", title: "Alder Creek HOA", copy: "Stage materials for Building C start Monday", tag: "Truck 5" },
  ],
  crews: [
    { label: "Crew Red", value: "2 roof installs / 1 repair" },
    { label: "Crew White", value: "Siding prep / 6.5 labor hrs booked" },
    { label: "Crew Slate", value: "Storm punch list / open afternoon slot" },
    { label: "Crew North", value: "Commercial sealant work / after-hours" },
  ],
  notices: [
    { title: "Customer text updates", copy: "11 customers will receive ETA windows automatically today.", tone: "success" },
    { title: "Weather alert", copy: "Possible wind delay after 2 PM for north loop deliveries.", tone: "warning" },
    { title: "Dock access note", copy: "Summit Dental loading zone closes at 11:30 AM sharp.", tone: "danger" },
  ],
};

let inventoryData = {
  stockRows: [
    { item: "Charcoal laminate shingles", sku: "SH-CHAR-30", stock: "18 sq", reserved: "32 sq", cost: "$94.00", price: "$134.00", status: "Low" },
    { item: "White 6in fascia coil", sku: "FA-WHT-6", stock: "44 rolls", reserved: "19 rolls", cost: "$71.00", price: "$109.00", status: "Cost spike" },
    { item: "Synthetic underlayment", sku: "UL-SYN-500", stock: "122 rolls", reserved: "41 rolls", cost: "$27.00", price: "$49.00", status: "Healthy" },
    { item: "Fiber cement lap siding", sku: "SD-FCL-8", stock: "64 bundles", reserved: "58 bundles", cost: "$213.00", price: "$296.00", status: "Watch" },
  ],
  purchasing: [
    { title: "Beacon West reorder", copy: "Charcoal shingles / 40 sq needed by Friday" },
    { title: "ABC branch transfer", copy: "Move 12 rolls of underlayment to South Yard" },
    { title: "QXO quote request", copy: "Compare fascia coil pricing before next PO" },
  ],
  controls: [
    { label: "Warehouse stock lists", value: "5 templates" },
    { label: "Truck restock cycles", value: "Nightly" },
    { label: "Reserved job stock", value: "$83,200" },
    { label: "Potential shrinkage", value: "$2,140" },
  ],
  marginSignals: [
    "Surface vendor price changes directly in the estimate workflow.",
    "Reserve stock against approved jobs before crews are scheduled.",
    "Flag jobs where real material cost erodes the quoted margin.",
  ],
};

let accountingData = {
  balances: [
    { label: "Operating cash", value: "$184,200", copy: "After pending deposits clear" },
    { label: "Receivables open", value: "$126,880", copy: "11 invoices, 3 overdue" },
    { label: "Payables open", value: "$47,280", copy: "6 vendor bills due this week" },
    { label: "Payroll next run", value: "$18,900", copy: "Friday, Apr 3" },
  ],
  cards: [
    { title: "Fuel Card", copy: "4 active drivers / $1,280 this month" },
    { title: "Materials Card", copy: "Used for emergency supplier pickups only" },
    { title: "Office Card", copy: "Low activity / policy compliant" },
  ],
  aging: [
    { customer: "Bennett Duplex", bucket: "Current", amount: "$5,620", status: "Deposit applied" },
    { customer: "Alder Creek HOA", bucket: "1-30 days", amount: "$29,600", status: "Board review pending" },
    { customer: "Lopez Residence", bucket: "31-60 days", amount: "$3,480", status: "Needs reminder call" },
    { customer: "Crescent Bistro", bucket: "Current", amount: "$12,200", status: "Final invoice not sent" },
  ],
  payroll: [
    { title: "Production labor", copy: "Overtime elevated on storm work this week." },
    { title: "Sales commissions", copy: "Three reps eligible after Morris and Bennett close." },
    { title: "Vendor payments", copy: "Beacon West and South Supply due before Monday." },
  ],
};

const navRoot = document.getElementById("nav-list");
const overviewRoot = document.getElementById("overview-strip");
const viewRoot = document.getElementById("view-root");
const viewTitle = document.getElementById("view-title");
const viewKicker = document.getElementById("view-kicker");
const viewDescription = document.getElementById("view-description");

function toneClass(value) {
  if (value === "success") return "success";
  if (value === "warning") return "warning";
  if (value === "danger") return "danger";
  return "";
}

function renderNav() {
  navRoot.innerHTML = views
    .map((view) => {
      const active = view.id === appState.activeView ? "active" : "";

      return `
        <button class="nav-button ${active}" data-view="${view.id}">
          <span class="nav-icon">${view.icon}</span>
          <span>
            <span class="nav-title">${view.label}</span>
            <span class="nav-copy">${view.kicker}</span>
          </span>
        </button>
      `;
    })
    .join("");
}

function renderOverview() {
  overviewRoot.innerHTML = overviewMetrics
    .map(
      (metric) => `
        <article class="metric-card">
          <div>
            <div class="metric-label">${metric.label}</div>
            <div class="metric-value">${metric.value}</div>
          </div>
          <span class="metric-trend">${metric.trend}</span>
        </article>
      `,
    )
    .join("");
}

function renderPriorityTable(rows) {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Opportunity</th>
            <th>Stage</th>
            <th>Close</th>
            <th>Value</th>
            <th>Priority</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  <td>
                    <div class="row-title">${row.name}</div>
                    <div class="row-subtitle">${row.subtitle}</div>
                  </td>
                  <td>${row.stage}</td>
                  <td>${row.close}</td>
                  <td>${row.value}</td>
                  <td>
                    <div class="priority-bar"><span style="width:${row.priority}%"></span></div>
                  </td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDashboard() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-8">
        <p class="module-tag">Base Design Direction</p>
        <h3 class="hero-title">Built around estimate, material, crew, and cash.</h3>
        <p class="hero-subtitle">
          ConTech is modeled on how roofing and siding businesses actually move work:
          capture a lead, inspect the property, send a quote, secure materials, dispatch crews,
          and collect cash without re-entering the same job five times.
        </p>
        <div class="hero-sequence">
          ${dashboardData.focusAreas
            .map((item) => `<span class="sequence-pill">${item}</span>`)
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Command pulse</h3>
            <p class="panel-copy">What leadership needs to notice before the day gets away.</p>
          </div>
        </div>
        <div class="mini-stat-grid">
          ${dashboardData.teamPulse
            .map(
              (item) => `
                <div class="mini-stat">
                  <span class="metric-label">${item.label}</span>
                  <strong>${item.value}</strong>
                  <div class="row-subtitle">${item.copy}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-7">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Hot pipeline</h3>
            <p class="panel-copy">Lead tracking with job value and urgency baked into the sales view.</p>
          </div>
          <span class="status-pill">Owner view</span>
        </div>
        ${renderPriorityTable(dashboardData.hotPipeline)}
      </section>

      <section class="card span-5">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Dispatch preview</h3>
            <p class="panel-copy">Deliveries and route status surfaced in the same command deck.</p>
          </div>
          <span class="status-pill warning">3 watch items</span>
        </div>
        <div class="timeline">
          ${dashboardData.dispatch
            .map(
              (item) => `
                <div class="timeline-item">
                  <div class="time-chip">${item.time}</div>
                  <div>
                    <div class="row-title">${item.title}</div>
                    <div class="row-subtitle">${item.copy}</div>
                    <div class="chips">
                      <span class="mini-pill">${item.status}</span>
                    </div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-5">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Material risk</h3>
            <p class="panel-copy">Inventory alerts belong next to the jobs they can delay.</p>
          </div>
        </div>
        <div class="signal-list">
          ${dashboardData.inventoryRisk
            .map(
              (item) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${item.title}</div>
                    <div class="row-subtitle">${item.copy}</div>
                  </div>
                  <span class="status-pill ${toneClass(item.tone)}">${item.tone}</span>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-7">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Cash view</h3>
            <p class="panel-copy">A base accounting layer that shows inflow and outflow in operational terms.</p>
          </div>
          <span class="status-pill success">Accounting aware</span>
        </div>
        <div class="mini-stat-grid">
          ${dashboardData.cashSignals
            .map(
              (item) => `
                <div class="mini-stat">
                  <span class="metric-label">${item.label}</span>
                  <strong>${item.value}</strong>
                  <div class="row-subtitle">${item.tag}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderSales() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-12">
        <div class="module-banner">
          <div>
            <p class="module-tag">Sales workflow</p>
            <h3 class="hero-title">Lead tracking that feels like contracting, not generic CRM theater.</h3>
            <p class="hero-subtitle">
              The ConTech sales module centers around inspection-driven work, good-better-best quoting,
              material-aware pricing, and a clean handoff into production once a customer signs.
            </p>
          </div>
          <div class="module-rail">
            <div class="stat-row">
              <span>Quote win rate</span>
              <strong>41.8%</strong>
            </div>
            <div class="stat-row">
              <span>Average quote turnaround</span>
              <strong>2.4 hrs</strong>
            </div>
            <div class="stat-row">
              <span>Signed this week</span>
              <strong>5 jobs</strong>
            </div>
          </div>
        </div>
      </section>

      <section class="card span-12">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Deal board</h3>
            <p class="panel-copy">Each stage represents a real construction milestone.</p>
          </div>
          <span class="status-pill">Sales board</span>
        </div>
        <div class="lane-board">
          ${salesData.lanes
            .map(
              (lane) => `
                <div class="lane">
                  <div class="lane-head">
                    <div class="lane-title">${lane.title}</div>
                    <div class="lane-count">${lane.count}</div>
                  </div>
                  <div class="deal-stack">
                    ${lane.cards
                      .map(
                        (card) => `
                          <div class="deal-card">
                            <div class="deal-top">
                              <div class="deal-name">${card.name}</div>
                              <div class="deal-value">${card.value}</div>
                            </div>
                            <div class="deal-meta">${card.type}</div>
                            <div class="deal-meta">Rep: ${card.rep}</div>
                          </div>
                        `,
                      )
                      .join("")}
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-7">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Quote builder pattern</h3>
            <p class="panel-copy">Built to support roofing, siding, and multi-trade option sets.</p>
          </div>
        </div>
        <div class="signal-list">
          ${salesData.quoteOptions
            .map(
              (option) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${option.name}</div>
                    <div class="row-subtitle">${option.copy}</div>
                  </div>
                  <div class="chips">
                    <span class="status-pill ${toneClass(option.tone)}">${option.amount}</span>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-5">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Order and invoice handoff</h3>
            <p class="panel-copy">Signed work should move directly into production and billing states.</p>
          </div>
        </div>
        <div class="info-list">
          ${salesData.orders
            .map(
              (item) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${item.customer}</div>
                    <div class="row-subtitle">${item.doc}</div>
                  </div>
                  <div class="chips">
                    <span class="mini-pill">${item.status}</span>
                    <span class="status-pill">${item.amount}</span>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Lead channels</h3>
            <p class="panel-copy">Simple attribution view for managers and owners.</p>
          </div>
        </div>
        <div class="report-bars">
          ${salesData.channels
            .map(
              (channel) => `
                <div class="report-bar-row">
                  <div class="report-bar-label">${channel.label}</div>
                  <div class="report-track">
                    <div class="report-fill" style="width:${channel.value}%"></div>
                  </div>
                  <div>${channel.value}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-8">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Next actions</h3>
            <p class="panel-copy">Lead tracking should always end with a visible next step.</p>
          </div>
          <span class="status-pill warning">4 urgent</span>
        </div>
        <div class="timeline">
          ${salesData.actions
            .map(
              (action, index) => `
                <div class="timeline-item">
                  <div class="time-chip">Task ${index + 1}</div>
                  <div>
                    <div class="row-title">${action}</div>
                    <div class="row-subtitle">Tied to the customer, job, and rep who owns the follow-up.</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderCustomers() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-12">
        <p class="module-tag">Customer records</p>
        <h3 class="hero-title">Every customer should read like a living project file.</h3>
        <p class="hero-subtitle">
          ConTech keeps customer relationships tied to the property, documents, communication history,
          and work in progress so teams do not need one tool for CRM and another for operations.
        </p>
      </section>

      <section class="card span-7">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Customer roster</h3>
            <p class="panel-copy">The profile layer balances standard CRM contact data with job context.</p>
          </div>
        </div>
        <div class="customer-grid">
          ${customerData.cards
            .map(
              (customer) => `
                <div class="customer-card">
                  <h4>${customer.name}</h4>
                  <p>${customer.line1}</p>
                  <p>${customer.line2}</p>
                  <div class="chips">
                    ${customer.tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-5">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Active property profile</h3>
            <p class="panel-copy">Example detail stack for a sold but not-yet-completed job.</p>
          </div>
          <span class="status-pill success">Morris Residence</span>
        </div>
        <div class="info-list">
          ${customerData.profile
            .map(
              (item) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="metric-label">${item.label}</div>
                    <div class="row-title">${item.value}</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-6">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Communication timeline</h3>
            <p class="panel-copy">Contacts, updates, and signed milestones all belong on the same thread.</p>
          </div>
        </div>
        <div class="timeline">
          ${customerData.timeline
            .map(
              (item) => `
                <div class="timeline-item">
                  <div class="time-chip">${item.time}</div>
                  <div>
                    <div class="row-title">${item.title}</div>
                    <div class="row-subtitle">${item.copy}</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-6">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Retention signals</h3>
            <p class="panel-copy">A base CRM for contractors still needs healthy repeat-business visibility.</p>
          </div>
        </div>
        <div class="kpi-cluster">
          ${customerData.loyalty
            .map(
              (item) => `
                <div class="kpi-tile">
                  <span class="metric-label">${item.label}</span>
                  <strong>${item.value}</strong>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderReports() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-12">
        <p class="module-tag">Reporting</p>
        <h3 class="hero-title">Owners need profit, sales, churn, and job performance without exporting everything to a spreadsheet.</h3>
        <p class="hero-subtitle">
          This reporting module is built to answer both standard business questions and construction-specific ones,
          like material impact on margin, close rate by lead source, and on-time delivery performance.
        </p>
      </section>

      <section class="card span-12">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Core KPI deck</h3>
            <p class="panel-copy">The base report layer should answer the most frequent owner questions on the first screen.</p>
          </div>
        </div>
        <div class="kpi-cluster">
          ${reportData.kpis
            .map(
              (item) => `
                <div class="kpi-tile">
                  <span class="metric-label">${item.label}</span>
                  <strong>${item.value}</strong>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-8">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Revenue trend</h3>
            <p class="panel-copy">Example monthly report card with simple visual scan value.</p>
          </div>
        </div>
        <div class="report-bars">
          ${reportData.revenueBars
            .map(
              (bar) => `
                <div class="report-bar-row">
                  <div class="report-bar-label">${bar.label}</div>
                  <div class="report-track">
                    <div class="report-fill" style="width:${bar.value}%"></div>
                  </div>
                  <div>${bar.amount}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Report library</h3>
            <p class="panel-copy">Standard views available from day one.</p>
          </div>
        </div>
        <div class="report-list">
          ${reportData.library
            .map(
              (item) => `
                <div class="report-card">
                  <div class="row-title">${item}</div>
                  <div class="row-subtitle">Saved report or dashboard card</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Margin by trade</h3>
            <p class="panel-copy">Helpful for balancing roofing and siding work mix.</p>
          </div>
        </div>
        <div class="info-list">
          ${reportData.marginByTrade
            .map(
              (item) => `
                <div class="stat-row">
                  <span>${item.label}</span>
                  <strong>${item.value}</strong>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-8">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Decision notes</h3>
            <p class="panel-copy">Narrative insight blocks keep the reports actionable, not just decorative.</p>
          </div>
        </div>
        <div class="signal-list">
          ${reportData.notes
            .map(
              (note) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${note.title}</div>
                    <div class="row-subtitle">${note.copy}</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderDispatch() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-12">
        <p class="module-tag">Dispatch</p>
        <h3 class="hero-title">Deliveries and crews need a board, not a hidden list.</h3>
        <p class="hero-subtitle">
          The dispatch design combines scheduling, route awareness, crew load, and customer notifications
          so the office can react quickly without bouncing between disconnected screens.
        </p>
      </section>

      <section class="card span-8">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Today's dispatch board</h3>
            <p class="panel-copy">Delivery records are linked to jobs, trucks, and ETA communication.</p>
          </div>
          <span class="status-pill warning">1 weather risk</span>
        </div>
        <div class="timeline">
          ${dispatchData.board
            .map(
              (item) => `
                <div class="timeline-item">
                  <div class="time-chip">${item.time}</div>
                  <div>
                    <div class="row-title">${item.title}</div>
                    <div class="row-subtitle">${item.copy}</div>
                    <div class="chips">
                      <span class="mini-pill">${item.tag}</span>
                    </div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Route pulse</h3>
            <p class="panel-copy">A simple at-a-glance delivery health meter.</p>
          </div>
        </div>
        <div class="route-meter">
          ${dispatchData.routes
            .map(
              (route) => `
                <div>
                  <div class="row-title">${route.title}</div>
                  <div class="row-subtitle">${route.copy}</div>
                  <div class="route-track">
                    <div class="route-fill" style="width:${route.value}%"></div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-6">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Crew load</h3>
            <p class="panel-copy">A base schedule view for balancing teams before jobs stack up.</p>
          </div>
        </div>
        <div class="schedule-stack">
          ${dispatchData.crews
            .map(
              (crew) => `
                <div class="schedule-card">
                  <div class="row-title">${crew.label}</div>
                  <div class="row-subtitle">${crew.value}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-6">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Customer and ops notices</h3>
            <p class="panel-copy">Important route conditions should be obvious to dispatchers.</p>
          </div>
        </div>
        <div class="signal-list">
          ${dispatchData.notices
            .map(
              (notice) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${notice.title}</div>
                    <div class="row-subtitle">${notice.copy}</div>
                  </div>
                  <span class="status-pill ${toneClass(notice.tone)}">${notice.tone}</span>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderInventory() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-12">
        <p class="module-tag">Inventory</p>
        <h3 class="hero-title">Material control has to protect both schedule and margin.</h3>
        <p class="hero-subtitle">
          ConTech's inventory design supports job reservations, stock by location, vendor-driven replenishment,
          and pricing awareness so sales and operations make decisions from the same cost reality.
        </p>
      </section>

      <section class="card span-7">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Stock watch</h3>
            <p class="panel-copy">Core roofing and siding materials with sell price and stock pressure visible.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>SKU</th>
                <th>On hand</th>
                <th>Reserved</th>
                <th>Unit cost</th>
                <th>Sell price</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${inventoryData.stockRows
                .map(
                  (row) => `
                    <tr>
                      <td>${row.item}</td>
                      <td>${row.sku}</td>
                      <td>${row.stock}</td>
                      <td>${row.reserved}</td>
                      <td>${row.cost}</td>
                      <td>${row.price}</td>
                      <td>${row.status}</td>
                    </tr>
                  `,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </section>

      <section class="card span-5">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Purchasing queue</h3>
            <p class="panel-copy">Reorders and transfers tied directly to operational need.</p>
          </div>
          <span class="status-pill warning">3 actions</span>
        </div>
        <div class="info-list">
          ${inventoryData.purchasing
            .map(
              (item) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${item.title}</div>
                    <div class="row-subtitle">${item.copy}</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Control summary</h3>
            <p class="panel-copy">Warehouse, truck, and reserved-job visibility.</p>
          </div>
        </div>
        <div class="kpi-cluster">
          ${inventoryData.controls
            .map(
              (item) => `
                <div class="kpi-tile">
                  <span class="metric-label">${item.label}</span>
                  <strong>${item.value}</strong>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-8">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Margin protection rules</h3>
            <p class="panel-copy">The base system should reduce surprises instead of only recording them later.</p>
          </div>
        </div>
        <div class="timeline">
          ${inventoryData.marginSignals
            .map(
              (signal, index) => `
                <div class="timeline-item">
                  <div class="time-chip">Rule ${index + 1}</div>
                  <div>
                    <div class="row-title">${signal}</div>
                    <div class="row-subtitle">Design recommendation carried forward from roofing CRM research.</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderAccounting() {
  return `
    <div class="view-grid">
      <section class="card hero-card span-12">
        <p class="module-tag">Accounting</p>
        <h3 class="hero-title">The finance layer should explain what is happening in the business, not just store transactions.</h3>
        <p class="hero-subtitle">
          This base design focuses on visibility first: receivables, payables, cash movement, card usage,
          and payroll signals that stay connected to jobs, crews, vendors, and customers.
        </p>
      </section>

      <section class="card span-8">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Cash position</h3>
            <p class="panel-copy">A quick owner-level summary of the money picture.</p>
          </div>
        </div>
        <div class="mini-stat-grid">
          ${accountingData.balances
            .map(
              (item) => `
                <div class="mini-stat">
                  <span class="metric-label">${item.label}</span>
                  <strong>${item.value}</strong>
                  <div class="row-subtitle">${item.copy}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-4">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Company cards</h3>
            <p class="panel-copy">Controlled spending visibility for materials, fuel, and office overhead.</p>
          </div>
        </div>
        <div class="schedule-stack">
          ${accountingData.cards
            .map(
              (card) => `
                <div class="schedule-card">
                  <div class="row-title">${card.title}</div>
                  <div class="row-subtitle">${card.copy}</div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="card span-6">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Receivables aging</h3>
            <p class="panel-copy">Operational AR view tied back to real jobs and customers.</p>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Bucket</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${accountingData.aging
                .map(
                  (item) => `
                    <tr>
                      <td>${item.customer}</td>
                      <td>${item.bucket}</td>
                      <td>${item.amount}</td>
                      <td>${item.status}</td>
                    </tr>
                  `,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </section>

      <section class="card span-6">
        <div class="card-header">
          <div>
            <h3 class="panel-title">Payroll and vendor watch</h3>
            <p class="panel-copy">Phase one now assumes full bookkeeping and payroll capability for the single-branch business.</p>
          </div>
          <span class="status-pill success">Phase-one scope</span>
        </div>
        <div class="signal-list">
          ${accountingData.payroll
            .map(
              (item) => `
                <div class="info-row">
                  <div class="info-row-main">
                    <div class="row-title">${item.title}</div>
                    <div class="row-subtitle">${item.copy}</div>
                  </div>
                </div>
              `,
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function renderView(viewId) {
  switch (viewId) {
    case "sales":
      return renderSales();
    case "customers":
      return renderCustomers();
    case "reports":
      return renderReports();
    case "dispatch":
      return renderDispatch();
    case "inventory":
      return renderInventory();
    case "accounting":
      return renderAccounting();
    case "dashboard":
    default:
      return renderDashboard();
  }
}

function updateViewMeta() {
  const active = views.find((view) => view.id === appState.activeView) || views[0];
  viewTitle.textContent = active.label;
  viewKicker.textContent = active.kicker;
  viewDescription.textContent = active.description;
}

function setView(viewId) {
  appState.activeView = viewId;
  updateViewMeta();
  renderNav();
  viewRoot.innerHTML = renderView(viewId);
}

function applyBootstrapPayload(payload) {
  if (!payload) {
    return false;
  }

  overviewMetrics = payload.overviewMetrics || overviewMetrics;
  dashboardData = payload.dashboard || dashboardData;
  salesData = payload.sales || salesData;
  customerData = payload.customers || customerData;
  reportData = payload.reports || reportData;
  dispatchData = payload.dispatch || dispatchData;
  inventoryData = payload.inventory || inventoryData;
  accountingData = payload.accounting || accountingData;

  return true;
}

async function loadBootstrap() {
  try {
    const response = await fetch("/api/bootstrap", {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return false;
    }

    const payload = await response.json();
    return applyBootstrapPayload(payload);
  } catch (error) {
    console.info("ConTech bootstrap API not available, using embedded demo data.", error);
    return false;
  }
}

document.addEventListener("click", (event) => {
  const navButton = event.target.closest("[data-view]");
  const jumpButton = event.target.closest("[data-jump]");

  if (navButton) {
    setView(navButton.dataset.view);
  }

  if (jumpButton) {
    setView(jumpButton.dataset.jump);
  }
});

renderOverview();
setView(appState.activeView);
loadBootstrap().then((loaded) => {
  if (loaded) {
    renderOverview();
    setView(appState.activeView);
  }
});
