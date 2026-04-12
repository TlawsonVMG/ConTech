import json
import re
import zlib
from datetime import datetime
from pathlib import Path


PIPELINE_VERSION = "2026.04-native-pdf-v2"
PARSER_NAME = "native-pdf-heuristics"
_NUMBER_PATTERN = r"(\d+(?:,\d{3})*(?:\.\d+)?)"

CORE_TAKEOFF_FIELDS = (
    "roof_area_sqft",
    "roof_area_squares",
    "perimeter_feet",
    "ridge_feet",
    "valley_feet",
    "eave_feet",
    "waste_pct",
)
NUMERIC_STRUCTURED_FIELDS = CORE_TAKEOFF_FIELDS + (
    "drains_count",
    "penetrations_count",
    "parapet_feet",
)
TEXT_STRUCTURED_FIELDS = ("scale_text",)
LIST_STRUCTURED_FIELDS = ("flashing_types",)
CORRECTABLE_ANALYSIS_FIELDS = (
    "roof_system_suggestion",
    *NUMERIC_STRUCTURED_FIELDS,
    *TEXT_STRUCTURED_FIELDS,
    *LIST_STRUCTURED_FIELDS,
)

SYSTEM_KEYWORDS = {
    "Architectural Shingles": (
        "architectural shingle",
        "laminated shingle",
        "shingle roof",
        "starter strip",
        "ridge cap",
        "ice and water",
    ),
    "TPO": ("tpo", "thermoplastic polyolefin", "single ply membrane", "welded seam"),
    "EPDM": ("epdm", "rubber membrane", "fully adhered epdm"),
    "Standing Seam Metal": ("standing seam", "metal roof", "sheet metal", "panel clip", "ridge cap metal"),
    "PVC": ("pvc membrane", "vinyl membrane", "hot air welded pvc"),
    "Modified Bitumen": ("modified bitumen", "mod bit", "torch down", "cap sheet"),
}

PLAN_TYPE_KEYWORDS = {
    "roof_plan": ("roof plan", "roofing plan", "main roof", "roof layout"),
    "detail": ("detail", "flashing detail", "coping detail", "edge detail"),
    "section": ("section", "wall section", "roof section"),
    "schedule": ("schedule", "legend", "material schedule"),
    "notes": ("general notes", "notes", "specifications"),
}

FLASHING_TYPE_KEYWORDS = {
    "base flashing": ("base flashing", "base flashings"),
    "coping": ("coping", "coping cap"),
    "counterflashing": ("counterflashing", "counter flashing"),
    "drip edge": ("drip edge",),
    "edge metal": ("edge metal", "gravel stop", "fascia metal"),
    "pipe boots": ("pipe boot", "pipe boots"),
    "ridge cap": ("ridge cap",),
    "step flashing": ("step flashing",),
    "valley metal": ("valley metal",),
    "wall flashing": ("wall flashing",),
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _normalize_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_number(value):
    return float(value.replace(",", ""))


def _decode_pdf_literal(value):
    result = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        index += 1
        if index >= len(value):
            break
        escaped = value[index]
        escape_map = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "b": "\b",
            "f": "\f",
            "\\": "\\",
            "(": "(",
            ")": ")",
        }
        if escaped in escape_map:
            result.append(escape_map[escaped])
            index += 1
            continue
        if escaped in "\r\n":
            index += 1
            if escaped == "\r" and index < len(value) and value[index] == "\n":
                index += 1
            continue
        if escaped.isdigit():
            octal_digits = escaped
            index += 1
            while index < len(value) and len(octal_digits) < 3 and value[index].isdigit():
                octal_digits += value[index]
                index += 1
            result.append(chr(int(octal_digits, 8)))
            continue

        result.append(escaped)
        index += 1

    return "".join(result)


def _decode_pdf_hex(value):
    compact = re.sub(r"\s+", "", value)
    if len(compact) % 2 == 1:
        compact += "0"
    try:
        raw_bytes = bytes.fromhex(compact)
    except ValueError:
        return ""

    if b"\x00" in raw_bytes:
        try:
            return raw_bytes.decode("utf-16-be")
        except UnicodeDecodeError:
            pass
    return raw_bytes.decode("latin-1", errors="ignore")


def _decompress_stream(stream_bytes):
    candidates = (stream_bytes, stream_bytes.rstrip(b"\r\n"), stream_bytes.strip())
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return zlib.decompress(candidate)
        except zlib.error:
            continue
    return None


def _extract_content_streams(raw_bytes, warnings):
    pattern = re.compile(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", re.S)
    content_streams = []
    for match in pattern.finditer(raw_bytes):
        dictionary_bytes = match.group(1)
        stream_bytes = match.group(2)
        if b"/FlateDecode" in dictionary_bytes:
            inflated = _decompress_stream(stream_bytes)
            if inflated is None:
                warnings.append("Could not inflate one compressed PDF content stream.")
                continue
            content_streams.append(inflated)
            continue
        content_streams.append(stream_bytes)
    return content_streams


def _extract_text_fragments(raw_text):
    text_blocks = re.findall(r"BT(.*?)ET", raw_text, re.S)
    fragments = []
    for block in text_blocks or [raw_text]:
        for literal_match in re.finditer(r"\((?:\\.|[^\\()])*\)", block):
            fragment = _decode_pdf_literal(literal_match.group(0)[1:-1])
            fragment = _normalize_text(fragment)
            if fragment:
                fragments.append(fragment)

        for hex_match in re.finditer(r"<([0-9A-Fa-f\s]+)>", block):
            fragment = _normalize_text(_decode_pdf_hex(hex_match.group(1)))
            if fragment:
                fragments.append(fragment)
    return fragments


def _extract_fallback_text(raw_bytes):
    fallback = []
    raw_text = raw_bytes.decode("latin-1", errors="ignore")
    for literal_match in re.finditer(r"\((?:\\.|[^\\()])*\)", raw_text):
        fragment = _normalize_text(_decode_pdf_literal(literal_match.group(0)[1:-1]))
        if fragment:
            fallback.append(fragment)

    if not fallback:
        ascii_runs = re.findall(rb"[A-Za-z0-9][A-Za-z0-9\s#:/._,%()-]{6,}", raw_bytes)
        for run in ascii_runs[:120]:
            fragment = _normalize_text(run.decode("latin-1", errors="ignore"))
            if fragment:
                fallback.append(fragment)
    return fallback


def _extract_pdf_text(raw_bytes, warnings):
    text_fragments = []
    for stream_bytes in _extract_content_streams(raw_bytes, warnings):
        stream_text = stream_bytes.decode("latin-1", errors="ignore")
        text_fragments.extend(_extract_text_fragments(stream_text))

    if not text_fragments:
        text_fragments = _extract_fallback_text(raw_bytes)

    deduped = []
    seen = set()
    for fragment in text_fragments:
        normalized = _normalize_text(fragment)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return " ".join(deduped)


def _count_pages(raw_bytes):
    count = len(re.findall(rb"/Type\s*/Page\b", raw_bytes))
    return count if count > 0 else 1


def _extract_sheet_labels(text):
    patterns = (
        r"\b[A-Z]{1,3}-\d{1,3}(?:\.\d{1,2})?\b",
        r"\b[A-Z]{1,3}\d{1,3}(?:\.\d{1,2})?\b",
    )
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    normalized = sorted({match.upper() for match in matches})
    return normalized[:24]


def _count_keywords(text, keywords):
    counts = {}
    lower_text = text.lower()
    for label, terms in keywords.items():
        counts[label] = sum(lower_text.count(term) for term in terms)
    return counts


def _extract_first_measurement(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return _parse_number(match.group(1))
    return None


def _extract_first_text(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = _normalize_text(match.group(1))
            if value:
                return value
    return None


def _extract_measurements(text):
    measurements = {}
    sqft_patterns = (
        rf"(?:roof area|total roof area|roofing area)[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*(?:sf|sq\.?\s*ft|square feet)",
        rf"{_NUMBER_PATTERN}\s*(?:sf|sq\.?\s*ft|square feet)\b",
    )
    squares_patterns = (
        rf"(?:roof area|total roof area|roofing area)[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*(?:squares|square|sqr)",
        rf"{_NUMBER_PATTERN}\s*(?:squares|square|sqr)\b",
    )
    linear_unit = r"(?:lf|lin(?:ear)?\.?\s*(?:ft|feet)|feet|ft)"
    measurements["roof_area_sqft"] = _extract_first_measurement(text, sqft_patterns)
    measurements["roof_area_squares"] = _extract_first_measurement(text, squares_patterns)
    measurements["perimeter_feet"] = _extract_first_measurement(
        text,
        (
            rf"(?:roof\s+)?perimeter[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
            rf"perimeter[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
        ),
    )
    measurements["ridge_feet"] = _extract_first_measurement(
        text,
        (
            rf"ridge(?:\s+length)?[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
        ),
    )
    measurements["valley_feet"] = _extract_first_measurement(
        text,
        (
            rf"valley(?:\s+length)?[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
        ),
    )
    measurements["eave_feet"] = _extract_first_measurement(
        text,
        (
            rf"eave(?:\s+length)?[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
            rf"eaves[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
        ),
    )
    measurements["waste_pct"] = _extract_first_measurement(
        text,
        (
            rf"waste[^0-9]{{0,12}}{_NUMBER_PATTERN}\s*%",
            rf"{_NUMBER_PATTERN}\s*%\s*waste",
        ),
    )
    measurements["drains_count"] = _extract_first_measurement(
        text,
        (
            rf"(?:roof\s+drains?|drains?|drain count)[^0-9]{{0,12}}{_NUMBER_PATTERN}\b",
            rf"{_NUMBER_PATTERN}\s+(?:roof\s+)?drains?\b",
        ),
    )
    measurements["penetrations_count"] = _extract_first_measurement(
        text,
        (
            rf"(?:penetrations?|roof penetrations?|curb count|curbs?)[^0-9]{{0,12}}{_NUMBER_PATTERN}\b",
            rf"{_NUMBER_PATTERN}\s+(?:roof\s+)?penetrations?\b",
        ),
    )
    measurements["parapet_feet"] = _extract_first_measurement(
        text,
        (
            rf"parapet(?:\s+wall)?[^0-9]{{0,24}}{_NUMBER_PATTERN}\s*{linear_unit}",
        ),
    )
    return {key: value for key, value in measurements.items() if value is not None}


def _extract_scale_text(text):
    return _extract_first_text(
        text,
        (
            r"scale(?:\s*:\s*|\s+)([^.;,\n]{4,40})",
        ),
    )


def _extract_flashing_types(text):
    lower_text = text.lower()
    found = []
    for label, keywords in FLASHING_TYPE_KEYWORDS.items():
        if any(keyword in lower_text for keyword in keywords):
            found.append(label)
    return found


def _suggest_roof_system(text, roof_system_hint=None):
    lower_text = text.lower()
    scores = {}
    for system_name, keywords in SYSTEM_KEYWORDS.items():
        score = sum(lower_text.count(keyword) for keyword in keywords)
        if roof_system_hint and roof_system_hint == system_name:
            score += 2
        scores[system_name] = score

    system_name, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return roof_system_hint, 0.35 if roof_system_hint else 0.0
    confidence = min(0.93, 0.44 + (score * 0.08))
    return system_name, round(confidence, 2)


def _page_role_summary_from_plan_counts(plan_counts, page_count):
    summary = {}
    for label, count in plan_counts.items():
        if count > 0:
            summary[label] = min(int(count), page_count or 1)
    return summary


def _dominant_page_role(page_role_summary):
    populated = [(label, count) for label, count in (page_role_summary or {}).items() if count > 0]
    if not populated:
        return None
    return max(populated, key=lambda item: item[1])[0]


def _build_structured_data(normalized_text, measurements):
    structured = dict(measurements)
    scale_text = _extract_scale_text(normalized_text)
    if scale_text:
        structured["scale_text"] = scale_text
    flashing_types = _extract_flashing_types(normalized_text)
    if flashing_types:
        structured["flashing_types"] = flashing_types
    return structured


def _build_field_confidence(structured_data, roof_system_suggestion, roof_system_confidence, page_role_summary, roof_sheet_labels):
    field_confidence = {}
    has_roof_plan = bool((page_role_summary or {}).get("roof_plan"))
    has_detail = bool((page_role_summary or {}).get("detail"))
    has_schedule = bool((page_role_summary or {}).get("schedule"))

    field_confidence["roof_system_suggestion"] = round(
        max(0.0, min(0.95, roof_system_confidence + (0.05 if has_roof_plan else 0.0))),
        2,
    ) if roof_system_suggestion else 0.0
    field_confidence["page_classification"] = 0.88 if has_roof_plan else 0.72 if page_role_summary else 0.18

    for field_name in NUMERIC_STRUCTURED_FIELDS:
        value = structured_data.get(field_name)
        if value is None:
            field_confidence[field_name] = 0.0
            continue

        if field_name in {"roof_area_sqft", "roof_area_squares"}:
            base_score = 0.78
        elif field_name in {"perimeter_feet", "ridge_feet", "valley_feet", "eave_feet", "waste_pct"}:
            base_score = 0.72
        else:
            base_score = 0.66

        if has_roof_plan:
            base_score += 0.08
        if field_name in {"drains_count", "penetrations_count", "parapet_feet"} and has_detail:
            base_score += 0.08
        if roof_sheet_labels:
            base_score += 0.04
        field_confidence[field_name] = round(min(0.95, base_score), 2)

    if structured_data.get("roof_area_sqft") is not None and structured_data.get("roof_area_squares") is not None:
        field_confidence["roof_area_sqft"] = max(field_confidence["roof_area_sqft"], 0.91)
        field_confidence["roof_area_squares"] = max(field_confidence["roof_area_squares"], 0.91)

    field_confidence["scale_text"] = round(0.74 if has_roof_plan else 0.62, 2) if structured_data.get("scale_text") else 0.0
    field_confidence["flashing_types"] = round(0.78 if has_detail or has_schedule else 0.68, 2) if structured_data.get("flashing_types") else 0.0
    return field_confidence


def _build_review_required(structured_data, field_confidence, roof_system_suggestion, page_role_summary):
    items = []
    if not (page_role_summary or {}).get("roof_plan"):
        items.append("Classify at least one roof plan page.")
    if not roof_system_suggestion or field_confidence.get("roof_system_suggestion", 0.0) < 0.7:
        items.append("Confirm the roof system.")
    if structured_data.get("roof_area_squares") is None and structured_data.get("roof_area_sqft") is None:
        items.append("Confirm total roof area.")
    if structured_data.get("perimeter_feet") is None:
        items.append("Confirm perimeter footage.")
    if not structured_data.get("flashing_types"):
        items.append("Review flashing and edge conditions.")
    if (page_role_summary or {}).get("detail") and structured_data.get("drains_count") is None:
        items.append("Review roof drains from detail sheets.")
    if (page_role_summary or {}).get("detail") and structured_data.get("penetrations_count") is None:
        items.append("Review penetrations and curbs from detail sheets.")
    deduped = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _analysis_confidence(text_length, sheet_labels, page_role_summary, field_confidence):
    score = 0.22 if text_length else 0.05
    score += min(0.18, text_length / 1800)
    score += min(0.12, len(sheet_labels) * 0.02)
    score += min(0.14, sum((page_role_summary or {}).values()) * 0.04)
    critical_fields = (
        field_confidence.get("roof_system_suggestion", 0.0),
        max(field_confidence.get("roof_area_squares", 0.0), field_confidence.get("roof_area_sqft", 0.0)),
        field_confidence.get("perimeter_feet", 0.0),
    )
    populated = [value for value in critical_fields if value > 0]
    if populated:
        score += min(0.3, (sum(populated) / len(populated)) * 0.32)
    return round(min(0.96, score), 2)


def _build_summary(page_count, roof_system_suggestion, structured_data, page_role_summary, warnings, review_required):
    signals = []
    if roof_system_suggestion:
        signals.append(f"Suggested system: {roof_system_suggestion}")
    if structured_data.get("roof_area_squares") is not None:
        signals.append(f"roof area {structured_data['roof_area_squares']:.1f} squares")
    elif structured_data.get("roof_area_sqft") is not None:
        signals.append(f"roof area {structured_data['roof_area_sqft']:.0f} sq ft")
    if structured_data.get("perimeter_feet") is not None:
        signals.append(f"perimeter {structured_data['perimeter_feet']:.0f} lf")
    dominant_role = _dominant_page_role(page_role_summary)
    if dominant_role:
        signals.append(f"primary sheets {dominant_role.replace('_', ' ')}")
    if structured_data.get("flashing_types"):
        signals.append(f"{len(structured_data['flashing_types'])} flashing types")
    if review_required:
        signals.append(f"{len(review_required)} review item(s)")
    if warnings:
        signals.append(f"{len(warnings)} warning(s)")
    return f"{page_count} page PDF analyzed; " + ", ".join(signals) if signals else f"{page_count} page PDF analyzed."


def analyze_text_content(
    raw_text,
    roof_system_hint=None,
    original_filename=None,
    page_count=1,
    parser_name=PARSER_NAME,
    pipeline_version=PIPELINE_VERSION,
    warnings=None,
    page_role_summary_override=None,
):
    warnings = list(warnings or [])
    normalized_text = _normalize_text(raw_text)
    sheet_labels = _extract_sheet_labels(normalized_text.upper())
    roof_sheet_labels = [label for label in sheet_labels if label.startswith("R")]
    keyword_counts = _count_keywords(normalized_text, SYSTEM_KEYWORDS)
    plan_counts = _count_keywords(normalized_text, PLAN_TYPE_KEYWORDS)
    measurements = _extract_measurements(normalized_text.lower())
    structured_data = _build_structured_data(normalized_text.lower(), measurements)
    roof_system_suggestion, roof_system_confidence = _suggest_roof_system(normalized_text, roof_system_hint=roof_system_hint)

    if not normalized_text:
        warnings.append("No readable text was extracted. This PDF may require OCR or raster vision.")

    page_role_summary = dict(page_role_summary_override or _page_role_summary_from_plan_counts(plan_counts, page_count))
    field_confidence = _build_field_confidence(
        structured_data,
        roof_system_suggestion,
        roof_system_confidence,
        page_role_summary,
        roof_sheet_labels,
    )
    review_required = _build_review_required(
        structured_data,
        field_confidence,
        roof_system_suggestion,
        page_role_summary,
    )
    confidence = _analysis_confidence(
        text_length=len(normalized_text),
        sheet_labels=sheet_labels,
        page_role_summary=page_role_summary,
        field_confidence=field_confidence,
    )
    status = (
        "Completed"
        if normalized_text and roof_system_suggestion and (structured_data.get("roof_area_squares") is not None or structured_data.get("roof_area_sqft") is not None)
        else "Review Required"
    )
    summary = _build_summary(page_count, roof_system_suggestion, structured_data, page_role_summary, warnings, review_required)
    excerpt = normalized_text[:1200]

    return {
        "status": status,
        "pipeline_version": pipeline_version,
        "parser_name": parser_name,
        "page_count": page_count,
        "raw_text_length": len(normalized_text),
        "extracted_text_excerpt": excerpt,
        "roof_system_suggestion": roof_system_suggestion,
        "confidence": confidence,
        "summary": summary,
        "sheet_labels": sheet_labels,
        "roof_sheet_labels": roof_sheet_labels,
        "keyword_counts": {**keyword_counts, **{f"plan:{key}": value for key, value in plan_counts.items()}},
        "measurement_data": measurements,
        "page_role_summary": page_role_summary,
        "structured_data": structured_data,
        "field_confidence": field_confidence,
        "review_required": review_required,
        "warnings": warnings,
        "original_filename": original_filename,
    }


def analyze_blueprint_bytes(raw_bytes, roof_system_hint=None, original_filename=None):
    warnings = []
    page_count = _count_pages(raw_bytes)
    extracted_text = _extract_pdf_text(raw_bytes, warnings)
    return analyze_text_content(
        extracted_text,
        roof_system_hint=roof_system_hint,
        original_filename=original_filename,
        page_count=page_count,
        parser_name=PARSER_NAME,
        pipeline_version=PIPELINE_VERSION,
        warnings=warnings,
    )


def analyze_blueprint_file(file_path, roof_system_hint=None, original_filename=None):
    raw_bytes = Path(file_path).read_bytes()
    return analyze_blueprint_bytes(raw_bytes, roof_system_hint=roof_system_hint, original_filename=original_filename)


def merge_analysis_sources(base_analysis, page_extractions, roof_system_hint=None):
    combined_fragments = []
    warnings = []
    page_count = 0
    original_filename = None
    page_role_summary = {}
    structured_overrides = {}
    structured_confidence = {}

    if base_analysis:
        if base_analysis.get("extracted_text_excerpt"):
            combined_fragments.append(base_analysis["extracted_text_excerpt"])
        warnings.extend(base_analysis.get("warnings", []))
        page_count = max(page_count, int(base_analysis.get("page_count") or 0))
        original_filename = base_analysis.get("original_filename")
        for role_name, count in (base_analysis.get("page_role_summary") or {}).items():
            page_role_summary[role_name] = max(page_role_summary.get(role_name, 0), int(count or 0))

    inferred_roof_system = None
    for extraction in page_extractions:
        if extraction.get("text_excerpt"):
            combined_fragments.append(extraction["text_excerpt"])
        warnings.extend(extraction.get("warnings", []))
        page_count = max(page_count, int(extraction.get("page_number") or 0))
        role_name = extraction.get("page_role")
        if role_name:
            page_role_summary[role_name] = page_role_summary.get(role_name, 0) + 1
        if not inferred_roof_system and extraction.get("roof_system_hint"):
            inferred_roof_system = extraction["roof_system_hint"]
        for key, value in (extraction.get("measurement_data") or {}).items():
            if value in (None, "", []):
                continue
            if structured_overrides.get(key) in (None, "", []):
                structured_overrides[key] = value
            structured_confidence[key] = max(structured_confidence.get(key, 0.0), float(extraction.get("confidence") or 0.0))

    merged = analyze_text_content(
        " ".join(combined_fragments),
        roof_system_hint=roof_system_hint or inferred_roof_system or (base_analysis or {}).get("effective_roof_system_suggestion") or (base_analysis or {}).get("roof_system_suggestion"),
        original_filename=original_filename,
        page_count=page_count or 1,
        parser_name="worker-enhanced-pipeline",
        pipeline_version="2026.04-worker-enhanced-v2",
        warnings=warnings,
        page_role_summary_override=page_role_summary or None,
    )

    for key, value in structured_overrides.items():
        if merged["structured_data"].get(key) in (None, "", []):
            merged["structured_data"][key] = value
        if isinstance(value, (int, float)) and key not in merged["measurement_data"]:
            merged["measurement_data"][key] = value
        merged["field_confidence"][key] = round(max(merged["field_confidence"].get(key, 0.0), structured_confidence.get(key, 0.0)), 2)

    merged["review_required"] = _build_review_required(
        merged["structured_data"],
        merged["field_confidence"],
        merged.get("roof_system_suggestion"),
        merged.get("page_role_summary"),
    )
    merged["confidence"] = _analysis_confidence(
        text_length=merged["raw_text_length"],
        sheet_labels=merged["sheet_labels"],
        page_role_summary=merged["page_role_summary"],
        field_confidence=merged["field_confidence"],
    )
    merged["summary"] = _build_summary(
        merged["page_count"],
        merged.get("roof_system_suggestion"),
        merged["structured_data"],
        merged["page_role_summary"],
        merged["warnings"],
        merged["review_required"],
    )
    merged["status"] = (
        "Completed"
        if merged["raw_text_length"] and merged.get("roof_system_suggestion") and (
            merged["structured_data"].get("roof_area_squares") is not None or merged["structured_data"].get("roof_area_sqft") is not None
        )
        else "Review Required"
    )
    return merged


def _json_load(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _analysis_payload(row):
    if row is None:
        return None
    payload = dict(row)
    payload["sheet_labels"] = _json_load(payload.get("sheet_labels_json"), [])
    payload["roof_sheet_labels"] = _json_load(payload.get("roof_sheet_labels_json"), [])
    payload["keyword_counts"] = _json_load(payload.get("keyword_counts_json"), {})
    payload["measurement_data"] = _json_load(payload.get("measurement_json"), {})
    payload["page_role_summary"] = _json_load(payload.get("page_role_summary_json"), {})
    payload["structured_data"] = _json_load(payload.get("structured_data_json"), {})
    payload["field_confidence"] = _json_load(payload.get("field_confidence_json"), {})
    payload["review_required"] = _json_load(payload.get("review_required_json"), [])
    payload["warnings"] = _json_load(payload.get("warnings_json"), [])
    payload.setdefault("effective_roof_system_suggestion", payload.get("roof_system_suggestion"))
    payload.setdefault("effective_structured_data", dict(payload.get("structured_data") or payload.get("measurement_data") or {}))
    payload.setdefault("effective_field_confidence", dict(payload.get("field_confidence") or {}))
    payload.setdefault("corrections", [])
    return payload


def record_blueprint_analysis(db, blueprint_id, analysis):
    timestamp = _now()
    analysis_id = db.execute(
        """
        INSERT INTO blueprint_analyses (
            blueprint_id, status, pipeline_version, parser_name, page_count, raw_text_length,
            extracted_text_excerpt, roof_system_suggestion, confidence, summary,
            sheet_labels_json, roof_sheet_labels_json, keyword_counts_json, measurement_json,
            page_role_summary_json, structured_data_json, field_confidence_json, review_required_json,
            warnings_json, created_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            blueprint_id,
            analysis["status"],
            analysis["pipeline_version"],
            analysis["parser_name"],
            analysis["page_count"],
            analysis["raw_text_length"],
            analysis["extracted_text_excerpt"],
            analysis.get("roof_system_suggestion"),
            analysis["confidence"],
            analysis["summary"],
            json.dumps(analysis["sheet_labels"]),
            json.dumps(analysis["roof_sheet_labels"]),
            json.dumps(analysis["keyword_counts"]),
            json.dumps(analysis["measurement_data"]),
            json.dumps(analysis.get("page_role_summary", {})),
            json.dumps(analysis.get("structured_data", {})),
            json.dumps(analysis.get("field_confidence", {})),
            json.dumps(analysis.get("review_required", [])),
            json.dumps(analysis["warnings"]),
            timestamp,
            timestamp,
        ),
    ).lastrowid
    db.execute(
        """
        UPDATE blueprints
        SET page_count = ?, status = ?, analysis_status = ?, analysis_summary = ?,
            analysis_confidence = ?, last_analyzed_at = ?
        WHERE id = ?
        """,
        (
            analysis["page_count"],
            "Analyzed" if analysis["status"] == "Completed" else "Review Required",
            analysis["status"],
            analysis["summary"],
            analysis["confidence"],
            timestamp,
            blueprint_id,
        ),
    )
    return analysis_id


def _deserialize_correction(row):
    payload = dict(row)
    field_name = payload["field_name"]
    if field_name in NUMERIC_STRUCTURED_FIELDS:
        value = payload.get("field_value_number")
    elif field_name in LIST_STRUCTURED_FIELDS:
        value = [item.strip() for item in re.split(r"[,;\n]", payload.get("field_value_text") or "") if item.strip()]
    else:
        value = _normalize_text(payload.get("field_value_text"))
    payload["value"] = value
    return payload


def list_analysis_field_corrections(db, blueprint_id):
    rows = db.execute(
        """
        SELECT *
        FROM analysis_field_corrections
        WHERE blueprint_id = ?
        ORDER BY id DESC
        """,
        (blueprint_id,),
    ).fetchall()
    return [_deserialize_correction(row) for row in rows]


def get_latest_field_corrections(db, blueprint_id):
    latest = {}
    for correction in list_analysis_field_corrections(db, blueprint_id):
        if correction["field_name"] not in latest:
            latest[correction["field_name"]] = correction
    return latest


def record_analysis_corrections(db, blueprint_id, blueprint_analysis_id, corrected_by_name, values, notes=None):
    created = 0
    timestamp = _now()
    for field_name, value in values.items():
        if field_name not in CORRECTABLE_ANALYSIS_FIELDS:
            continue
        field_value_text = None
        field_value_number = None
        if field_name in NUMERIC_STRUCTURED_FIELDS:
            field_value_number = float(value)
        elif field_name in LIST_STRUCTURED_FIELDS:
            if isinstance(value, (list, tuple)):
                field_value_text = ", ".join(str(item).strip() for item in value if str(item).strip())
            else:
                field_value_text = str(value).strip()
        else:
            field_value_text = str(value).strip()
        db.execute(
            """
            INSERT INTO analysis_field_corrections (
                blueprint_id, blueprint_analysis_id, field_name, field_value_text,
                field_value_number, corrected_by_name, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                blueprint_id,
                blueprint_analysis_id,
                field_name,
                field_value_text,
                field_value_number,
                corrected_by_name,
                notes,
                timestamp,
            ),
        )
        created += 1
    return created


def apply_field_corrections(analysis, latest_corrections):
    if analysis is None:
        return None

    effective_structured_data = dict(analysis.get("structured_data") or analysis.get("measurement_data") or {})
    effective_field_confidence = dict(analysis.get("field_confidence") or {})
    effective_roof_system = analysis.get("roof_system_suggestion")

    for field_name, correction in (latest_corrections or {}).items():
        if field_name == "roof_system_suggestion":
            effective_roof_system = correction["value"]
        else:
            effective_structured_data[field_name] = correction["value"]
        effective_field_confidence[field_name] = 1.0

    hydrated = dict(analysis)
    hydrated["effective_roof_system_suggestion"] = effective_roof_system
    hydrated["effective_structured_data"] = effective_structured_data
    hydrated["effective_field_confidence"] = effective_field_confidence
    hydrated["corrections"] = list((latest_corrections or {}).values())
    hydrated["review_required"] = _build_review_required(
        effective_structured_data,
        effective_field_confidence,
        effective_roof_system,
        hydrated.get("page_role_summary"),
    )
    return hydrated


def get_latest_blueprint_analysis(db, blueprint_id):
    row = db.execute(
        """
        SELECT *
        FROM blueprint_analyses
        WHERE blueprint_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (blueprint_id,),
    ).fetchone()
    payload = _analysis_payload(row)
    if payload is None:
        return None
    hydrated = apply_field_corrections(payload, get_latest_field_corrections(db, blueprint_id))
    hydrated["takeoff_seed"] = build_takeoff_seed(hydrated)
    return hydrated


def takeoff_confidence_from_analysis(analysis):
    if not analysis:
        return 0.0
    field_confidence = analysis.get("effective_field_confidence") or analysis.get("field_confidence") or {}
    critical = [
        field_confidence.get("roof_system_suggestion", 0.0),
        max(field_confidence.get("roof_area_squares", 0.0), field_confidence.get("roof_area_sqft", 0.0)),
        field_confidence.get("perimeter_feet", 0.0),
        field_confidence.get("waste_pct", 0.0),
    ]
    populated = [value for value in critical if value > 0]
    if not populated:
        return 0.0
    return round(sum(populated) / len(populated), 2)


def build_takeoff_seed(analysis, project_roof_system=None):
    if not analysis:
        return None

    measurements = dict(analysis.get("effective_structured_data") or analysis.get("structured_data") or analysis.get("measurement_data") or {})
    roof_area_squares = measurements.get("roof_area_squares")
    if roof_area_squares is None and measurements.get("roof_area_sqft") is not None:
        roof_area_squares = round(float(measurements["roof_area_sqft"]) / 100, 1)

    system_type = analysis.get("effective_roof_system_suggestion") or analysis.get("roof_system_suggestion") or project_roof_system
    waste_pct = float(measurements.get("waste_pct", 7 if system_type == "Architectural Shingles" else 5))
    can_generate = roof_area_squares is not None and roof_area_squares > 0 and system_type

    missing = []
    if roof_area_squares is None:
        missing.append("roof area")
    if not system_type:
        missing.append("roof system")

    return {
        "system_type": system_type,
        "roof_area_squares": roof_area_squares,
        "waste_pct": waste_pct,
        "perimeter_feet": float(measurements.get("perimeter_feet", 0)),
        "ridge_feet": float(measurements.get("ridge_feet", 0)),
        "valley_feet": float(measurements.get("valley_feet", 0)),
        "eave_feet": float(measurements.get("eave_feet", 0)),
        "can_generate": bool(can_generate),
        "missing_fields": missing,
        "confidence": takeoff_confidence_from_analysis(analysis),
        "review_required": list(analysis.get("review_required", [])),
    }


def serialize_analysis(row):
    payload = _analysis_payload(row)
    if payload is None:
        return None
    hydrated = apply_field_corrections(payload, {})
    hydrated["takeoff_seed"] = build_takeoff_seed(hydrated)
    return hydrated
