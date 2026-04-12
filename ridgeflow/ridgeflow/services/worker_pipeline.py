import base64
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import click
from flask import current_app

from ..db import get_db
from .pdf_pipeline import analyze_blueprint_file, analyze_text_content, get_latest_blueprint_analysis, merge_analysis_sources, record_blueprint_analysis
from .revision_compare import refresh_related_revision_compares


WORKER_JOB_RASTERIZE = "rasterize_blueprint"
WORKER_JOB_OCR = "ocr_blueprint_pages"
WORKER_JOB_VISION = "vision_blueprint_pages"
WORKER_JOB_CONSOLIDATE = "consolidate_blueprint_analysis"
_MOCK_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a8kAAAAASUVORK5CYII="


def _now():
    return time.strftime("%Y-%m-%d %H:%M")


def _json_dump(value):
    return json.dumps(value or {})


def _json_load(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _log_project_activity(db, blueprint_id, actor_name, event_type, event_text):
    project = db.execute(
        "SELECT project_id FROM blueprints WHERE id = ?",
        (blueprint_id,),
    ).fetchone()
    if project is None:
        return
    db.execute(
        """
        INSERT INTO project_activity (project_id, actor_name, event_type, event_text, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project["project_id"], actor_name, event_type, event_text, _now()),
    )


def _ensure_blueprint_page_folder(blueprint_id):
    base_folder = Path(current_app.config["BLUEPRINT_PAGE_IMAGE_FOLDER"])
    folder = base_folder / str(blueprint_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _clear_blueprint_page_artifacts(db, blueprint_id):
    rows = db.execute(
        "SELECT image_filename FROM blueprint_page_renders WHERE blueprint_id = ?",
        (blueprint_id,),
    ).fetchall()
    for row in rows:
        file_path = Path(current_app.config["BLUEPRINT_PAGE_IMAGE_FOLDER"]) / row["image_filename"]
        if file_path.exists():
            file_path.unlink()
    folder = Path(current_app.config["BLUEPRINT_PAGE_IMAGE_FOLDER"]) / str(blueprint_id)
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    db.execute("DELETE FROM blueprint_page_renders WHERE blueprint_id = ?", (blueprint_id,))
    db.execute("DELETE FROM blueprint_page_extractions WHERE blueprint_id = ?", (blueprint_id,))


def enqueue_blueprint_worker_pipeline(db, blueprint_id, reset=False):
    if reset:
        db.execute(
            "DELETE FROM worker_jobs WHERE blueprint_id = ? AND status IN ('queued', 'running')",
            (blueprint_id,),
        )
    pending = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM worker_jobs
        WHERE blueprint_id = ? AND status IN ('queued', 'running')
        """,
        (blueprint_id,),
    ).fetchone()["count"]
    if pending > 0 and not reset:
        return None

    job_id = db.execute(
        """
        INSERT INTO worker_jobs (blueprint_id, job_type, status, payload_json, created_at)
        VALUES (?, ?, 'queued', ?, ?)
        """,
        (blueprint_id, WORKER_JOB_RASTERIZE, _json_dump({}), _now()),
    ).lastrowid
    return job_id


def list_blueprint_worker_jobs(db, blueprint_id):
    rows = db.execute(
        """
        SELECT *
        FROM worker_jobs
        WHERE blueprint_id = ?
        ORDER BY id DESC
        """,
        (blueprint_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def summarize_blueprint_worker_state(db, blueprint_id):
    latest_job = db.execute(
        """
        SELECT *
        FROM worker_jobs
        WHERE blueprint_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (blueprint_id,),
    ).fetchone()
    render_count = db.execute(
        "SELECT COUNT(*) AS count FROM blueprint_page_renders WHERE blueprint_id = ?",
        (blueprint_id,),
    ).fetchone()["count"]
    completed_ocr = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM blueprint_page_extractions
        WHERE blueprint_id = ? AND source_type = 'ocr' AND status = 'Completed'
        """,
        (blueprint_id,),
    ).fetchone()["count"]
    completed_vision = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM blueprint_page_extractions
        WHERE blueprint_id = ? AND source_type = 'vision' AND status = 'Completed'
        """,
        (blueprint_id,),
    ).fetchone()["count"]
    return {
        "latest_job": dict(latest_job) if latest_job is not None else None,
        "render_count": render_count,
        "ocr_count": completed_ocr,
        "vision_count": completed_vision,
    }


def _create_followup_job(db, blueprint_id, job_type, payload=None):
    db.execute(
        """
        INSERT INTO worker_jobs (blueprint_id, job_type, status, payload_json, created_at)
        VALUES (?, ?, 'queued', ?, ?)
        """,
        (blueprint_id, job_type, _json_dump(payload), _now()),
    )


def _claim_next_job(db):
    row = db.execute(
        """
        SELECT *
        FROM worker_jobs
        WHERE status = 'queued'
        ORDER BY id ASC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    updated = db.execute(
        """
        UPDATE worker_jobs
        SET status = 'running', attempts = attempts + 1, leased_at = ?
        WHERE id = ? AND status = 'queued'
        """,
        (_now(), row["id"]),
    )
    if updated.rowcount != 1:
        return None
    return db.execute("SELECT * FROM worker_jobs WHERE id = ?", (row["id"],)).fetchone()


def _complete_job(db, job_id, status="completed", last_error=None):
    db.execute(
        """
        UPDATE worker_jobs
        SET status = ?, last_error = ?, completed_at = ?
        WHERE id = ?
        """,
        (status, last_error, _now(), job_id),
    )


def _blueprint_context(db, blueprint_id):
    return db.execute(
        """
        SELECT b.*, p.roof_system, p.project_id, p.name AS project_name
        FROM blueprints b
        JOIN (
            SELECT id AS project_id, roof_system, name
            FROM projects
        ) p ON p.project_id = b.project_id
        WHERE b.id = ?
        """,
        (blueprint_id,),
    ).fetchone()


def _mime_type_for_suffix(path):
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _resolve_command_path(command_name):
    if not command_name:
        return None
    if os.path.isabs(command_name) and Path(command_name).exists():
        return command_name
    return shutil.which(command_name)


def _page_role_from_keyword_counts(keyword_counts):
    role_scores = {}
    for key, value in keyword_counts.items():
        if key.startswith("plan:"):
            role_scores[key.split(":", 1)[1]] = value
    if not role_scores:
        return None
    role_name, score = max(role_scores.items(), key=lambda item: item[1])
    return role_name if score > 0 else None


def _build_page_extraction(text_excerpt, source_type, backend_name, page_number, roof_system_hint=None, measurement_data=None, warnings=None, confidence=None):
    signal_analysis = analyze_text_content(
        text_excerpt,
        roof_system_hint=roof_system_hint,
        page_count=1,
        parser_name=f"{source_type}-{backend_name}",
        pipeline_version="2026.04-page-worker-v1",
        warnings=warnings,
    )
    measurements = dict(signal_analysis["structured_data"])
    for key, value in (measurement_data or {}).items():
        if value is not None:
            measurements[key] = value
    return {
        "page_number": page_number,
        "source_type": source_type,
        "backend_name": backend_name,
        "status": "Completed" if text_excerpt else "Skipped",
        "text_excerpt": (text_excerpt or "")[:1200],
        "sheet_label": signal_analysis["sheet_labels"][0] if signal_analysis["sheet_labels"] else None,
        "page_role": _page_role_from_keyword_counts(signal_analysis["keyword_counts"]),
        "roof_system_hint": signal_analysis["roof_system_suggestion"],
        "confidence": float(confidence if confidence is not None else signal_analysis["confidence"]),
        "measurement_data": measurements,
        "warnings": signal_analysis["warnings"],
    }


def _store_page_extraction(db, blueprint_id, extraction):
    db.execute(
        """
        INSERT INTO blueprint_page_extractions (
            blueprint_id, page_number, source_type, backend_name, status, text_excerpt,
            sheet_label, page_role, roof_system_hint, confidence, measurement_json,
            warnings_json, created_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            blueprint_id,
            extraction["page_number"],
            extraction["source_type"],
            extraction["backend_name"],
            extraction["status"],
            extraction["text_excerpt"],
            extraction["sheet_label"],
            extraction["page_role"],
            extraction["roof_system_hint"],
            extraction["confidence"],
            json.dumps(extraction["measurement_data"]),
            json.dumps(extraction["warnings"]),
            _now(),
            _now(),
        ),
    )


def _list_completed_page_extractions(db, blueprint_id):
    rows = db.execute(
        """
        SELECT *
        FROM blueprint_page_extractions
        WHERE blueprint_id = ? AND status = 'Completed'
        ORDER BY page_number, id
        """,
        (blueprint_id,),
    ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["measurement_data"] = _json_load(item.get("measurement_json"), {})
        item["warnings"] = _json_load(item.get("warnings_json"), [])
        payload.append(item)
    return payload


class MockRasterizerBackend:
    name = "mock"

    def rasterize(self, pdf_path, output_folder, dpi):
        analysis = analyze_blueprint_file(pdf_path)
        page_count = max(1, analysis["page_count"])
        image_bytes = base64.b64decode(_MOCK_PNG_BASE64)
        pages = []
        for page_number in range(1, page_count + 1):
            file_path = output_folder / f"page-{page_number:03d}.png"
            file_path.write_bytes(image_bytes)
            pages.append(
                {
                    "page_number": page_number,
                    "image_path": file_path,
                    "mime_type": "image/png",
                    "width_px": 1,
                    "height_px": 1,
                }
            )
        return pages


class PdftoppmRasterizerBackend:
    name = "pdftoppm"

    def __init__(self, command_name):
        self.command_name = command_name

    def rasterize(self, pdf_path, output_folder, dpi):
        prefix = output_folder / "page"
        command = [
            self.command_name,
            "-png",
            "-r",
            str(dpi),
            str(pdf_path),
            str(prefix),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "pdftoppm rasterization failed.")
        pages = []
        for path in sorted(output_folder.glob("page-*.png")):
            page_number = int(path.stem.split("-")[-1])
            pages.append(
                {
                    "page_number": page_number,
                    "image_path": path,
                    "mime_type": "image/png",
                    "width_px": 0,
                    "height_px": 0,
                }
            )
        if not pages:
            raise RuntimeError("pdftoppm completed without generating page images.")
        return pages


class MagickRasterizerBackend:
    name = "magick"

    def __init__(self, command_name):
        self.command_name = command_name

    def rasterize(self, pdf_path, output_folder, dpi):
        output_pattern = output_folder / "page-%03d.png"
        command = [
            self.command_name,
            "-density",
            str(dpi),
            str(pdf_path),
            str(output_pattern),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "ImageMagick rasterization failed.")
        pages = []
        for index, path in enumerate(sorted(output_folder.glob("page-*.png")), start=1):
            pages.append(
                {
                    "page_number": index,
                    "image_path": path,
                    "mime_type": "image/png",
                    "width_px": 0,
                    "height_px": 0,
                }
            )
        if not pages:
            raise RuntimeError("ImageMagick completed without generating page images.")
        return pages


class MockOcrBackend:
    name = "mock"

    def extract_text(self, image_path, blueprint_pdf_path, page_number):
        analysis = analyze_blueprint_file(blueprint_pdf_path)
        return {
            "text": analysis["extracted_text_excerpt"] if page_number == 1 else "",
            "warnings": [] if page_number == 1 else ["Mock OCR emits text on the first page only."],
        }


class TesseractOcrBackend:
    name = "tesseract"

    def __init__(self, command_name):
        self.command_name = command_name

    def extract_text(self, image_path, blueprint_pdf_path, page_number):
        command = [self.command_name, str(image_path), "stdout", "--psm", "6"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Tesseract OCR failed.")
        return {
            "text": result.stdout.strip(),
            "warnings": [],
        }


class MockVisionBackend:
    name = "mock"

    def inspect_page(self, image_path, blueprint_pdf_path, page_number, roof_system_hint):
        analysis = analyze_blueprint_file(blueprint_pdf_path, roof_system_hint=roof_system_hint)
        return {
            "visible_text_excerpt": analysis["extracted_text_excerpt"] if page_number == 1 else "",
            "sheet_label": analysis["sheet_labels"][0] if analysis["sheet_labels"] else None,
            "page_role": "roof_plan",
            "roof_system_hint": analysis["roof_system_suggestion"],
            "measurements": analysis["structured_data"],
            "warnings": [],
            "confidence": max(0.65, analysis["confidence"]),
        }


class OpenAIVisionBackend:
    name = "openai"

    def __init__(self, api_key, model, detail):
        self.api_key = api_key
        self.model = model
        self.detail = detail

    def inspect_page(self, image_path, blueprint_pdf_path, page_number, roof_system_hint):
        mime_type = _mime_type_for_suffix(image_path)
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        data_url = f"data:{mime_type};base64,{image_data}"
        prompt = (
            "You are reading a construction blueprint page for a roofing takeoff workflow. "
            "Return only JSON with keys: visible_text_excerpt, sheet_label, page_role, "
            "roof_system_hint, measurements, warnings, confidence. "
            "Use measurements object keys like roof_area_sqft, roof_area_squares, perimeter_feet, "
            "ridge_feet, valley_feet, eave_feet, waste_pct, drains_count, penetrations_count, "
            "parapet_feet, scale_text, flashing_types when present. "
            f"Page number is {page_number}. Preferred roof system hint: {roof_system_hint or 'unknown'}."
        )
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url, "detail": self.detail},
                    ],
                }
            ],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI vision request failed: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI vision request failed: {exc.reason}") from exc

        output_text = response_payload.get("output_text") or self._extract_output_text(response_payload)
        structured = self._parse_json(output_text)
        if structured is None:
            raise RuntimeError("OpenAI vision response did not contain valid JSON output.")
        return structured

    def _extract_output_text(self, response_payload):
        texts = []
        for output in response_payload.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    texts.append(content["text"])
        return "\n".join(texts).strip()

    def _parse_json(self, text):
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None


def _resolve_rasterizer_backend():
    preferred = current_app.config.get("RASTERIZER_BACKEND", "auto")
    if preferred == "mock":
        return MockRasterizerBackend()
    pdftoppm_command = _resolve_command_path(current_app.config.get("PDFTOPPM_COMMAND", "pdftoppm"))
    magick_command = _resolve_command_path(current_app.config.get("MAGICK_COMMAND", "magick"))
    if preferred in {"auto", "pdftoppm"} and pdftoppm_command:
        return PdftoppmRasterizerBackend(pdftoppm_command)
    if preferred in {"auto", "magick"} and magick_command:
        return MagickRasterizerBackend(magick_command)
    return None


def _resolve_ocr_backend():
    preferred = current_app.config.get("OCR_BACKEND", "auto")
    if preferred == "mock":
        return MockOcrBackend()
    command_name = current_app.config.get("TESSERACT_COMMAND", "tesseract")
    command_path = _resolve_command_path(command_name)
    if preferred in {"auto", "tesseract"} and command_path:
        return TesseractOcrBackend(command_path)
    return None


def _resolve_vision_backend():
    preferred = current_app.config.get("VISION_BACKEND", "auto")
    if preferred == "mock":
        return MockVisionBackend()
    api_key = os.getenv("OPENAI_API_KEY")
    if preferred in {"auto", "openai"} and api_key:
        return OpenAIVisionBackend(
            api_key=api_key,
            model=current_app.config.get("OPENAI_VISION_MODEL", "gpt-4.1"),
            detail=current_app.config.get("OPENAI_VISION_DETAIL", "high"),
        )
    return None


def _process_rasterize_job(db, blueprint):
    backend = _resolve_rasterizer_backend()
    if backend is None:
        raise RuntimeError("No rasterizer backend available. Install pdftoppm or ImageMagick, or configure RASTERIZER_BACKEND=mock for tests.")

    if not blueprint["stored_filename"]:
        raise RuntimeError("Blueprint has no stored PDF filename.")
    pdf_path = Path(current_app.config["BLUEPRINT_UPLOAD_FOLDER"]) / blueprint["stored_filename"]
    if not pdf_path.exists():
        raise RuntimeError("Blueprint PDF file could not be found.")

    _clear_blueprint_page_artifacts(db, blueprint["id"])
    output_folder = _ensure_blueprint_page_folder(blueprint["id"])
    dpi = int(current_app.config.get("RASTERIZER_DPI", 144))
    pages = backend.rasterize(pdf_path, output_folder, dpi=dpi)
    for page in pages:
        relative_name = Path(str(blueprint["id"])) / page["image_path"].name
        db.execute(
            """
            INSERT INTO blueprint_page_renders (
                blueprint_id, page_number, image_filename, mime_type, width_px, height_px,
                dpi, render_backend, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Completed', ?)
            """,
            (
                blueprint["id"],
                page["page_number"],
                str(relative_name).replace("\\", "/"),
                page["mime_type"],
                page["width_px"],
                page["height_px"],
                dpi,
                backend.name,
                _now(),
            ),
        )
    _create_followup_job(db, blueprint["id"], WORKER_JOB_OCR)
    _log_project_activity(db, blueprint["id"], "RidgeFlow Worker", "blueprint_rasterized", f"Rasterized {len(pages)} blueprint page(s).")


def _process_ocr_job(db, blueprint):
    backend = _resolve_ocr_backend()
    renders = db.execute(
        """
        SELECT *
        FROM blueprint_page_renders
        WHERE blueprint_id = ?
        ORDER BY page_number, id
        """,
        (blueprint["id"],),
    ).fetchall()
    if not renders:
        raise RuntimeError("No rendered blueprint pages exist for OCR.")

    pdf_path = Path(current_app.config["BLUEPRINT_UPLOAD_FOLDER"]) / blueprint["stored_filename"]
    for render in renders:
        image_path = Path(current_app.config["BLUEPRINT_PAGE_IMAGE_FOLDER"]) / render["image_filename"]
        if backend is None:
            extraction = _build_page_extraction(
                "",
                source_type="ocr",
                backend_name="unconfigured",
                page_number=render["page_number"],
                roof_system_hint=blueprint["roof_system"],
                warnings=["No OCR backend is configured. Install Tesseract or set OCR_BACKEND=mock for tests."],
                confidence=0.0,
            )
            extraction["status"] = "Skipped"
        else:
            result = backend.extract_text(image_path=image_path, blueprint_pdf_path=pdf_path, page_number=render["page_number"])
            extraction = _build_page_extraction(
                result.get("text", ""),
                source_type="ocr",
                backend_name=backend.name,
                page_number=render["page_number"],
                roof_system_hint=blueprint["roof_system"],
                warnings=result.get("warnings"),
            )
        _store_page_extraction(db, blueprint["id"], extraction)
    _create_followup_job(db, blueprint["id"], WORKER_JOB_VISION)
    _log_project_activity(db, blueprint["id"], "RidgeFlow Worker", "blueprint_ocr_processed", "Processed OCR step for rendered blueprint pages.")


def _process_vision_job(db, blueprint):
    backend = _resolve_vision_backend()
    renders = db.execute(
        """
        SELECT *
        FROM blueprint_page_renders
        WHERE blueprint_id = ?
        ORDER BY page_number, id
        """,
        (blueprint["id"],),
    ).fetchall()
    if not renders:
        raise RuntimeError("No rendered blueprint pages exist for vision.")

    pdf_path = Path(current_app.config["BLUEPRINT_UPLOAD_FOLDER"]) / blueprint["stored_filename"]
    for render in renders:
        image_path = Path(current_app.config["BLUEPRINT_PAGE_IMAGE_FOLDER"]) / render["image_filename"]
        if backend is None:
            extraction = {
                "page_number": render["page_number"],
                "source_type": "vision",
                "backend_name": "unconfigured",
                "status": "Skipped",
                "text_excerpt": "",
                "sheet_label": None,
                "page_role": None,
                "roof_system_hint": blueprint["roof_system"],
                "confidence": 0.0,
                "measurement_data": {},
                "warnings": ["No vision backend is configured. Set OPENAI_API_KEY and VISION_BACKEND=openai, or use VISION_BACKEND=mock for tests."],
            }
        else:
            result = backend.inspect_page(
                image_path=image_path,
                blueprint_pdf_path=pdf_path,
                page_number=render["page_number"],
                roof_system_hint=blueprint["roof_system"],
            )
            extraction = _build_page_extraction(
                result.get("visible_text_excerpt", ""),
                source_type="vision",
                backend_name=backend.name,
                page_number=render["page_number"],
                roof_system_hint=result.get("roof_system_hint") or blueprint["roof_system"],
                measurement_data=result.get("measurements"),
                warnings=result.get("warnings"),
                confidence=result.get("confidence"),
            )
            extraction["sheet_label"] = result.get("sheet_label") or extraction["sheet_label"]
            extraction["page_role"] = result.get("page_role") or extraction["page_role"]
        _store_page_extraction(db, blueprint["id"], extraction)
    _create_followup_job(db, blueprint["id"], WORKER_JOB_CONSOLIDATE)
    _log_project_activity(db, blueprint["id"], "RidgeFlow Worker", "blueprint_vision_processed", "Processed vision step for rendered blueprint pages.")


def _process_consolidate_job(db, blueprint):
    base_analysis = get_latest_blueprint_analysis(db, blueprint["id"])
    extractions = _list_completed_page_extractions(db, blueprint["id"])
    if not extractions:
        _log_project_activity(db, blueprint["id"], "RidgeFlow Worker", "blueprint_pipeline_skipped", "Worker pipeline finished without OCR or vision text to consolidate.")
        return
    merged = merge_analysis_sources(base_analysis, extractions, roof_system_hint=blueprint["roof_system"])
    record_blueprint_analysis(db, blueprint["id"], merged)
    refresh_related_revision_compares(db, blueprint["project_id"], blueprint["id"])
    _log_project_activity(db, blueprint["id"], "RidgeFlow Worker", "blueprint_analysis_enhanced", "Stored worker-enhanced blueprint analysis from raster, OCR, and vision outputs.")


def process_next_worker_job():
    db = get_db()
    job = _claim_next_job(db)
    if job is None:
        return None

    blueprint = _blueprint_context(db, job["blueprint_id"])
    if blueprint is None:
        _complete_job(db, job["id"], status="failed", last_error="Blueprint was not found.")
        db.commit()
        return {"job_id": job["id"], "status": "failed", "job_type": job["job_type"]}

    try:
        if job["job_type"] == WORKER_JOB_RASTERIZE:
            _process_rasterize_job(db, blueprint)
        elif job["job_type"] == WORKER_JOB_OCR:
            _process_ocr_job(db, blueprint)
        elif job["job_type"] == WORKER_JOB_VISION:
            _process_vision_job(db, blueprint)
        elif job["job_type"] == WORKER_JOB_CONSOLIDATE:
            _process_consolidate_job(db, blueprint)
        else:
            raise RuntimeError(f"Unknown worker job type: {job['job_type']}")
        _complete_job(db, job["id"], status="completed")
        db.commit()
        return {"job_id": job["id"], "status": "completed", "job_type": job["job_type"], "blueprint_id": blueprint["id"]}
    except Exception as exc:
        _complete_job(db, job["id"], status="failed", last_error=str(exc))
        db.commit()
        return {"job_id": job["id"], "status": "failed", "job_type": job["job_type"], "error": str(exc), "blueprint_id": blueprint["id"]}


@click.command("run-worker")
@click.option("--once", "run_once", is_flag=True, help="Process at most one queued worker job.")
@click.option("--max-jobs", default=10, show_default=True, type=int, help="Maximum jobs to process before exiting.")
@click.option("--poll-seconds", default=None, type=float, help="Poll interval when waiting for jobs.")
def run_worker_command(run_once, max_jobs, poll_seconds):
    processed = 0
    sleep_seconds = poll_seconds if poll_seconds is not None else float(current_app.config.get("WORKER_POLL_SECONDS", 5))
    while True:
        result = process_next_worker_job()
        if result is None:
            if run_once or processed >= max_jobs:
                break
            time.sleep(sleep_seconds)
            continue
        processed += 1
        click.echo(f"{result['status']}: {result['job_type']} for blueprint {result.get('blueprint_id', '?')}")
        if run_once or processed >= max_jobs:
            break


@click.command("queue-blueprint-workers")
@click.argument("blueprint_id", type=int)
@click.option("--reset", is_flag=True, help="Clear queued/running jobs before enqueuing a new worker pipeline.")
def queue_blueprint_workers_command(blueprint_id, reset):
    db = get_db()
    job_id = enqueue_blueprint_worker_pipeline(db, blueprint_id, reset=reset)
    db.commit()
    if job_id is None:
        click.echo(f"Blueprint {blueprint_id} already has pending worker jobs.")
    else:
        click.echo(f"Queued worker pipeline for blueprint {blueprint_id} with job {job_id}.")
