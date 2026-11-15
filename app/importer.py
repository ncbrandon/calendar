"""Turn a spreadsheet, or (optionally, with Claude) a permit PDF, into sampling requirements."""
from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import List

from .sampling import FREQUENCIES

COLUMNS = ["name", "program", "location", "frequency", "anchor_date", "end_date", "samples_per_period",
           "allowed_months", "cost", "lead_days", "lab", "notes"]
TEMPLATE = (
    ",".join(COLUMNS) + "\n"
    "Lead and Copper,drinking,Distribution (10 taps),triennial,2026-01-01,,1,\"6,7,8,9\",450,21,State lab,June-Sept only\n"
    "Inorganics (IOC),drinking,Well 1 entry point,triennial,2026-01-01,,1,,310,14,State lab,\n"
    "Nitrate,drinking,Well 1 entry point,annual,2026-01-01,,1,,35,14,State lab,\n"
    "Total Coliform,drinking,Distribution,monthly,2026-01-01,,2,,22,7,State lab,2 per month\n"
    "BOD5 / TSS,wastewater,Outfall 001,monthly,2026-01-01,,1,,95,7,Contract lab,Permit Part I.A\n"
    "Whole Effluent Toxicity,wastewater,Outfall 001,annual,2026-01-01,,1,,1200,21,Contract lab,\n"
)

_FREQ_WORDS = {
    "week": "weekly", "weekly": "weekly", "1/week": "weekly",
    "month": "monthly", "monthly": "monthly", "1/month": "monthly",
    "quarter": "quarterly", "quarterly": "quarterly", "1/quarter": "quarterly",
    "semiannual": "semiannual", "semi-annual": "semiannual", "twice a year": "semiannual", "2/year": "semiannual",
    "annual": "annual", "annually": "annual", "yearly": "annual", "year": "annual", "1/year": "annual",
    "triennial": "triennial", "3 year": "triennial", "3 years": "triennial", "3-year": "triennial",
    "every 3 years": "triennial", "3yr": "triennial",
    "six_year": "six_year", "6 year": "six_year", "6 years": "six_year", "6-year": "six_year", "every 6 years": "six_year",
    "nine_year": "nine_year", "9 year": "nine_year", "9 years": "nine_year", "9-year": "nine_year", "every 9 years": "nine_year",
    "once": "once", "one time": "once",
}


def clean(raw: dict) -> dict:
    """Validate one requirement (from a form, a spreadsheet row, or Claude) and fill in defaults."""
    get = lambda k: ("" if raw.get(k) is None else str(raw.get(k))).strip()
    name = get("name")
    if not name:
        raise ValueError("A requirement needs a name")
    freq = _FREQ_WORDS.get(get("frequency").lower(), get("frequency").lower())
    if freq not in FREQUENCIES:
        raise ValueError(f"{name}: unknown frequency '{get('frequency')}'. Use one of: {', '.join(FREQUENCIES)}")
    anchor = get("anchor_date")[:10] or date(date.today().year, 1, 1).isoformat()
    date.fromisoformat(anchor)
    end = get("end_date")[:10] or None
    if end:
        date.fromisoformat(end)
    months = raw.get("allowed_months") or []
    if isinstance(months, str):
        months = [int(m) for m in re.findall(r"\d+", months)]
    months = sorted({int(m) for m in months if 1 <= int(m) <= 12})
    number = lambda k, default: float(re.sub(r"[^0-9.]", "", get(k)) or default)
    program = get("program").lower() or "drinking"
    return {
        "name": name,
        "program": program if program in ("drinking", "wastewater", "other") else "other",
        "location": get("location"),
        "frequency": freq,
        "anchor_date": anchor,
        "end_date": end,
        "samples_per_period": max(1, int(number("samples_per_period", 1))),
        "allowed_months": json.dumps(months),
        "cost": number("cost", 0),
        "lead_days": int(number("lead_days", 14)),
        "lab": get("lab"),
        "notes": get("notes"),
        "active": 0 if str(raw.get("active", 1)).lower() in ("0", "false", "no") else 1,
    }


def parse_table(filename: str, data: bytes) -> List[dict]:
    """Read a .csv or .xlsx whose first row holds the column names in COLUMNS."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        table = [["" if c is None else c for c in row] for row in sheet.iter_rows(values_only=True)]
    else:
        table = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    table = [row for row in table if any(str(c).strip() for c in row)]
    if not table:
        return []
    header = [str(c).strip().lower().replace(" ", "_") for c in table[0]]
    if "name" not in header or "frequency" not in header:
        raise ValueError("The first row must contain at least the columns 'name' and 'frequency'")
    out = []
    for row in table[1:]:
        raw = {header[i]: row[i] for i in range(min(len(header), len(row)))}
        if hasattr(raw.get("anchor_date"), "isoformat"):
            raw["anchor_date"] = raw["anchor_date"].isoformat()
        if hasattr(raw.get("end_date"), "isoformat"):
            raw["end_date"] = raw["end_date"].isoformat()
        out.append(clean(raw))
    return out


# --- Optional: let Claude read the permit ---------------------------------

def ai_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


PROMPT = """You are reading a document from a small water and wastewater utility: either a wastewater
discharge permit (NPDES or state equivalent) or a drinking-water monitoring schedule issued by the state.

List every sampling or monitoring requirement that needs a sample collected and sent to a lab.
One entry per analyte group and sampling location. For each entry:

- name: short analyte or analyte-group name as the document writes it
- program: "drinking" or "wastewater"
- location: outfall, entry point, well, or distribution description
- frequency: the closest of weekly, monthly, quarterly, semiannual, annual, triennial (every 3 years),
  six_year, nine_year, once
- anchor_date: first day of the current monitoring period as YYYY-MM-DD. For 3-year drinking-water
  compliance periods the document usually states the period (for example 2026-2028 starts 2026-01-01).
  If the document does not say, use January 1 of {year}.
- samples_per_period: how many samples are required in each period
- allowed_months: month numbers when the sample must be taken (for example [6,7,8,9]); [] if any month
- notes: the page or section the requirement comes from, plus any condition a person should check

Skip continuous or operator-read measurements that need no lab bottle (flow, pH by meter, chlorine residual
by field kit) unless the document requires a lab sample. Do not invent requirements; if a value is unclear,
say so in notes. Leave cost and lab to the operator."""


def extract_with_claude(path: Path, filename: str) -> List[dict]:
    """Send the document to Claude and return draft requirements for a person to review."""
    try:
        import anthropic
        from pydantic import BaseModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the 'anthropic' package to use AI extraction (pip install anthropic)") from exc

    class Draft(BaseModel):
        name: str
        program: str
        location: str
        frequency: str
        anchor_date: str
        samples_per_period: int
        allowed_months: List[int]
        notes: str

    class Drafts(BaseModel):
        requirements: List[Draft]

    data = path.read_bytes()
    if filename.lower().endswith(".pdf"):
        if len(data) > 30 * 1024 * 1024:
            raise RuntimeError("That PDF is over 30 MB, which is too large to send. Split it and upload the monitoring section.")
        source = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                 "data": base64.standard_b64encode(data).decode("ascii")}}
    else:
        source = {"type": "text", "text": "DOCUMENT CONTENTS:\n\n" + data.decode("utf-8", "replace")}

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    response = client.messages.parse(
        model=os.environ.get("OPSBOARD_AI_MODEL", "claude-opus-5-5"),
        max_tokens=16000,
        messages=[{"role": "user", "content": [source, {"type": "text", "text": PROMPT.format(year=date.today().year)}]}],
        output_format=Drafts,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError("Claude could not read that document. Enter the requirements by hand or import a spreadsheet.")
    drafts: List[dict] = []
    for d in response.parsed_output.requirements:
        try:
            drafts.append(clean(d.model_dump()))
        except ValueError:
            continue
    return drafts

