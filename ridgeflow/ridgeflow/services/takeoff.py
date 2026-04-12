from datetime import datetime


SUPPORTED_SYSTEMS = (
    "Architectural Shingles",
    "TPO",
    "EPDM",
    "Standing Seam Metal",
    "PVC",
    "Modified Bitumen",
)


DEFAULT_WASTE_BY_SYSTEM = {
    "Architectural Shingles": 8.0,
    "TPO": 5.0,
    "EPDM": 5.0,
    "Standing Seam Metal": 9.0,
    "PVC": 5.0,
    "Modified Bitumen": 6.0,
}


def _round_qty(value):
    return round(float(value), 1)


def _confidence_score(roof_area_squares, perimeter_feet, ridge_feet, valley_feet, eave_feet):
    completeness = 0
    for value in (roof_area_squares, perimeter_feet, ridge_feet, valley_feet, eave_feet):
        if value and float(value) > 0:
            completeness += 1
    return round(min(0.95, 0.62 + (completeness * 0.06)), 2)


def default_waste_pct(system_type):
    return DEFAULT_WASTE_BY_SYSTEM.get(system_type, 5.0)


def build_takeoff_items(
    system_type,
    roof_area_squares,
    waste_pct,
    perimeter_feet,
    ridge_feet,
    valley_feet,
    eave_feet,
):
    system_key = (system_type or "").strip().lower()
    waste_multiplier = 1 + (float(waste_pct or 0) / 100)
    roof_area_squares = float(roof_area_squares or 0)
    roof_area_sqft = roof_area_squares * 100
    perimeter_feet = float(perimeter_feet or 0)
    ridge_feet = float(ridge_feet or 0)
    valley_feet = float(valley_feet or 0)
    eave_feet = float(eave_feet or 0)

    if system_key in {"architectural shingles", "shingles"}:
        return [
            {
                "category": "Field Material",
                "material_name": "Laminated shingles",
                "unit_label": "bundle",
                "quantity": _round_qty(roof_area_squares * 3 * waste_multiplier),
                "vendor_hint": "Owens Corning / Malarkey / CertainTeed",
                "notes": "Primary field shingles with waste included.",
            },
            {
                "category": "Underlayment",
                "material_name": "Synthetic underlayment",
                "unit_label": "roll",
                "quantity": _round_qty((roof_area_sqft * waste_multiplier) / 1000),
                "vendor_hint": "Premium synthetic",
                "notes": "Coverage based on roof area and waste factor.",
            },
            {
                "category": "Edge",
                "material_name": "Drip edge",
                "unit_label": "lf",
                "quantity": _round_qty(perimeter_feet * 1.03),
                "vendor_hint": "Standard edge metal",
                "notes": "Perimeter-based allowance for eaves and rakes.",
            },
            {
                "category": "Accessory",
                "material_name": "Starter strip",
                "unit_label": "lf",
                "quantity": _round_qty(eave_feet * 1.05),
                "vendor_hint": "Starter course",
                "notes": "Eave-heavy allowance with small contingency.",
            },
            {
                "category": "Accessory",
                "material_name": "Hip and ridge cap",
                "unit_label": "lf",
                "quantity": _round_qty((ridge_feet + valley_feet * 0.25) * 1.1),
                "vendor_hint": "Matching ridge cap",
                "notes": "Includes ridge focus and minor valley allowance.",
            },
        ]

    if system_key in {"tpo", "pvc", "epdm"}:
        membrane_label = "TPO membrane" if system_key == "tpo" else "PVC membrane" if system_key == "pvc" else "EPDM membrane"
        adhesive_label = "Membrane adhesive" if system_key == "epdm" else "Bonding adhesive"
        return [
            {
                "category": "Membrane",
                "material_name": membrane_label,
                "unit_label": "sq ft",
                "quantity": _round_qty(roof_area_sqft * waste_multiplier),
                "vendor_hint": "60 mil roll goods",
                "notes": "Includes waste factor for roll layout and detailing.",
            },
            {
                "category": "Substrate",
                "material_name": "Cover board",
                "unit_label": "sq ft",
                "quantity": _round_qty(roof_area_sqft),
                "vendor_hint": "High-density cover board",
                "notes": "Base coverage at one-for-one roof area.",
            },
            {
                "category": "Adhesive",
                "material_name": adhesive_label,
                "unit_label": "pail",
                "quantity": _round_qty((roof_area_sqft * waste_multiplier) / 900),
                "vendor_hint": "Manufacturer-matched system adhesive",
                "notes": "Starter estimate only, final quantity depends on spec and substrate.",
            },
            {
                "category": "Perimeter",
                "material_name": "Termination bar and fasteners",
                "unit_label": "lf",
                "quantity": _round_qty(perimeter_feet * 1.05),
                "vendor_hint": "Perimeter securement",
                "notes": "Perimeter securement allowance.",
            },
            {
                "category": "Flashing",
                "material_name": "Wall flashing membrane",
                "unit_label": "lf",
                "quantity": _round_qty((perimeter_feet * 0.45) + (eave_feet * 0.15)),
                "vendor_hint": "Preformed or field-fabricated flashing",
                "notes": "Placeholder wall and curb flashing allowance.",
            },
        ]

    if system_key in {"standing seam metal", "sheet metal", "metal"}:
        return [
            {
                "category": "Panels",
                "material_name": "Standing seam panels",
                "unit_label": "sq ft",
                "quantity": _round_qty(roof_area_sqft * waste_multiplier),
                "vendor_hint": "Factory-formed metal panels",
                "notes": "Field panel area with waste for layout and cutoffs.",
            },
            {
                "category": "Trim",
                "material_name": "Ridge cap trim",
                "unit_label": "lf",
                "quantity": _round_qty(ridge_feet * 1.08),
                "vendor_hint": "Matching finish trim",
                "notes": "Includes splices and minor overage.",
            },
            {
                "category": "Trim",
                "material_name": "Valley metal",
                "unit_label": "lf",
                "quantity": _round_qty(valley_feet * 1.1),
                "vendor_hint": "Pre-finished valley trim",
                "notes": "Includes lap waste.",
            },
            {
                "category": "Fasteners",
                "material_name": "Panel clip and fastener kit",
                "unit_label": "box",
                "quantity": _round_qty(max(1, roof_area_sqft / 650)),
                "vendor_hint": "System-specific concealed fasteners",
                "notes": "Sizing should be confirmed against panel spacing.",
            },
            {
                "category": "Edge",
                "material_name": "Eave and rake trim",
                "unit_label": "lf",
                "quantity": _round_qty(perimeter_feet * 1.06),
                "vendor_hint": "Matching perimeter trim",
                "notes": "Perimeter trim with waste.",
            },
        ]

    return [
        {
            "category": "General",
            "material_name": f"{system_type} material package",
            "unit_label": "allowance",
            "quantity": 1.0,
            "vendor_hint": "Manual review required",
            "notes": "Fallback package because this roof system does not yet have a formula set.",
        }
    ]


def build_summary(system_type, roof_area_squares, waste_pct, item_count):
    return (
        f"Native AI takeoff prepared for {system_type} using {roof_area_squares:.1f} squares "
        f"with {waste_pct:.1f}% waste. {item_count} material lines generated for estimator review."
    )


def create_takeoff_run(
    db,
    project_id,
    blueprint_id,
    system_type,
    roof_area_squares,
    waste_pct,
    perimeter_feet,
    ridge_feet,
    valley_feet,
    eave_feet,
    ai_model,
    status="Review Required",
    source_mode="native-ai",
    blueprint_analysis_id=None,
    analysis_summary_override=None,
    confidence_override=None,
):
    roof_area_squares = float(roof_area_squares or 0)
    waste_pct = float(waste_pct or 0)
    perimeter_feet = float(perimeter_feet or 0)
    ridge_feet = float(ridge_feet or 0)
    valley_feet = float(valley_feet or 0)
    eave_feet = float(eave_feet or 0)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    items = build_takeoff_items(
        system_type=system_type,
        roof_area_squares=roof_area_squares,
        waste_pct=waste_pct,
        perimeter_feet=perimeter_feet,
        ridge_feet=ridge_feet,
        valley_feet=valley_feet,
        eave_feet=eave_feet,
    )
    confidence = float(confidence_override) if confidence_override is not None else _confidence_score(roof_area_squares, perimeter_feet, ridge_feet, valley_feet, eave_feet)
    reviewed_at = created_at if status == "Approved" else None
    approved_at = created_at if status == "Approved" else None

    run_id = db.execute(
        """
        INSERT INTO takeoff_runs (
            project_id, blueprint_id, blueprint_analysis_id, status, system_type, source_mode, ai_model, confidence,
            waste_pct, roof_area_squares, perimeter_feet, ridge_feet, valley_feet, eave_feet,
            analysis_summary, created_at, reviewed_at, approved_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            blueprint_id,
            blueprint_analysis_id,
            status,
            system_type,
            source_mode,
            ai_model,
            confidence,
            waste_pct,
            roof_area_squares,
            perimeter_feet,
            ridge_feet,
            valley_feet,
            eave_feet,
            analysis_summary_override or build_summary(system_type, roof_area_squares, waste_pct, len(items)),
            created_at,
            reviewed_at,
            approved_at,
        ),
    ).lastrowid

    for index, item in enumerate(items, start=1):
        db.execute(
            """
            INSERT INTO takeoff_items (
                takeoff_run_id, category, material_name, unit_label, quantity, waste_pct,
                vendor_hint, notes, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                item["category"],
                item["material_name"],
                item["unit_label"],
                item["quantity"],
                waste_pct,
                item.get("vendor_hint"),
                item.get("notes"),
                index,
            ),
        )

    return run_id
