# app/services/schema_inference.py

import io
import json
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import pdfplumber
import sqlparse
from filetype import guess

from app.services.type_inference import (
    best_regex,
    guess_scalar_type,
    is_age_column,
    is_id_like,
    numeric_bounds,
    EMAIL_RE,
)


def apply_header(df: pd.DataFrame, header_row: int) -> pd.DataFrame:
    """
    Promote a specific row to header and return the DataFrame with data rows below it.
    Raises ValueError if header_row is out of range.
    """
    if header_row < 0 or header_row >= len(df):
        raise ValueError(f"header_row {header_row} is out of range (rows: {len(df)})")
    df2 = df.copy()
    df2.columns = df2.iloc[header_row]
    df2 = df2[(header_row + 1) :]
    # Normalize column names to strings
    df2.columns = [str(c) for c in df2.columns]
    return df2

def infer_from_dataframe(df: pd.DataFrame, sample: int = 500) -> Dict[str, Any]:
    """
    Build schema+validators using heuristics, robust to duplicate/blank headers.
    - Types: uuid | integer | float | boolean | date | datetime | string
    - ID-like => required=True, unique=True
    - Email   => unique=True, standard regex
    - Others  => required=False, unique=False
    - Numeric: min/max=None, except Age has min=0 and NO max
    """
    # 1) Take a sample
    sample_df = df.head(sample).copy()

    # 2) Normalize/uniquify column names (avoid duplicate labels returning DataFrames)
    raw_cols = [str(c).strip() if str(c).strip() != "" else "None" for c in sample_df.columns]
    seen = {}
    uniq_cols = []
    for c in raw_cols:
        base = c
        if base in ("", "None"):
            base = "col"
        name = base
        i = 1
        while name in seen:
            i += 1
            name = f"{base}_{i}"
        seen[name] = True
        uniq_cols.append(name)
    sample_df.columns = uniq_cols

    schema_cols: List[Dict[str, Any]] = []
    validators: Dict[str, Dict[str, Any]] = {}

    for i, col_name in enumerate(sample_df.columns):
        # 3) Always select by POSITION to get a Series
        series = sample_df.iloc[:, i]
        values = series.where(pd.notnull(series), None).tolist()

        dtype = guess_scalar_type(values)
        schema_cols.append({"name": col_name, "type": dtype})

        # defaults
        rules: Dict[str, Any] = {"type": dtype, "required": False, "unique": False}

        # ID-like?
        if is_id_like(col_name, dtype, values):
            rules["required"] = True
            rules["unique"] = True

        # Email rule (must be unique + regex)
        if col_name.lower() == "email":
            rules["unique"] = True
            rules["regex"] = EMAIL_RE.pattern
        else:
            # pattern only if strong match
            rx = best_regex(values)
            if rx:
                rules["regex"] = rx

        # numeric rules
        if dtype in ("integer", "float"):
            if is_age_column(col_name):
                rules["min"] = 0
                rules["max"] = None
            else:
                rules["min"] = None
                rules["max"] = None

        validators[col_name] = rules

    return {"schema": {"columns": schema_cols}, "validators": validators}



# -------------------- File loaders --------------------


def infer_from_csv(file_bytes: bytes, header_row: int) -> List[Dict[str, Any]]:
    """
    CSV requires explicit header_row.
    Read with pandas using that row as the header directly, and skip malformed rows.
    This avoids the 'first junk line defines 1 column' problem.
    """
    try:
        df = pd.read_csv(
            io.BytesIO(file_bytes),
            header=header_row,           # <-- use the provided header row
            engine="python",
            on_bad_lines="skip",
            sep=",",                     # be explicit
            skip_blank_lines=True,
        )
    except Exception:
        # Fallback: skip the first header_row lines and treat the next line as header=0
        df = pd.read_csv(
            io.BytesIO(file_bytes),
            header=0,
            engine="python",
            on_bad_lines="skip",
            sep=",",
            skip_blank_lines=True,
            skiprows=list(range(header_row)) if header_row > 0 else None,
        )
    # Ensure string column names
    df.columns = [str(c) for c in df.columns]
    return [infer_from_dataframe(df)]


def infer_from_excel(
    file_bytes: bytes,
    header_row: int,
    sheets: Optional[List[str]] = None,
    sheet_header_rows: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Excel with control:
      - If 'sheets' is None: process all sheets using 'header_row'.
      - If 'sheets' is provided: process only those sheets (names or 0-based indices).
      - If 'sheet_header_rows' is provided: must match 'sheets' length; overrides header_row per sheet.
    """
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    all_names = xls.sheet_names

    # Build (sheet_name, hdr_row) plan
    plan: List[Tuple[str, int]] = []

    if sheets is None:
        # all sheets, same header_row
        for name in all_names:
            plan.append((name, header_row))
    else:
        # selected sheets
        for idx, sel in enumerate(sheets):
            # Resolve selector: numeric index or name
            if sel.isdigit():
                si = int(sel)
                if si < 0 or si >= len(all_names):
                    raise ValueError(f"Sheet index {si} out of range (0..{len(all_names)-1})")
                sname = all_names[si]
            else:
                if sel not in all_names:
                    raise ValueError(f"Sheet name '{sel}' not found. Available: {all_names}")
                sname = sel

            # Per-sheet header row override
            if sheet_header_rows is not None:
                hdr = sheet_header_rows[idx]
                if hdr < 0:
                    raise ValueError(f"Invalid header row {hdr} for sheet '{sname}'")
                plan.append((sname, hdr))
            else:
                plan.append((sname, header_row))

    results: List[Dict[str, Any]] = []
    for (sheet_name, hdr) in plan:
        # Parse using the decided header row for this sheet
        df = xls.parse(sheet_name=sheet_name, header=hdr)
        df.columns = [str(c) for c in df.columns]  # normalize to strings
        r = infer_from_dataframe(df)
        r["__source_sheet__"] = sheet_name
        results.append(r)

    return results



def infer_from_json(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    JSON arrays/objects -> DataFrame.
    """
    data = json.loads(file_bytes.decode("utf-8", errors="ignore"))
    if isinstance(data, dict):
        rows = [data]
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    if not rows:
        return [{"schema": {"columns": []}, "validators": {}}]
    df = pd.DataFrame(rows)
    return [infer_from_dataframe(df)]


def infer_from_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    pdfplumber-only extraction, multiple tables per page, two passes per page.
    Each detected table becomes a schema. No external helpers needed.
    """
    def _ensure_rectangular(tbl) -> pd.DataFrame:
        # tbl is a list of rows with possibly different lengths
        max_cols = max((len(r) for r in tbl if r is not None), default=0)
        df = pd.DataFrame(tbl)
        if df.shape[1] < max_cols:
            for _ in range(max_cols - df.shape[1]):
                df[df.shape[1]] = pd.NA
        return df

    def _promote_first_row_as_header(df: pd.DataFrame) -> pd.DataFrame:
        if df.shape[0] == 0:
            return df
        df2 = df.copy()
        # use row 0 as header; fill blanks with "None"
        df2.columns = [str(c).strip() if str(c).strip() != "" else "None" for c in df2.iloc[0]]
        df2 = df2.iloc[1:, :]
        df2.columns = [str(c) for c in df2.columns]
        return df2

    results: List[Dict[str, Any]] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for p_idx, page in enumerate(pdf.pages, start=1):
            # Pass 1: default extraction
            page_tables = page.extract_tables() or []

            # Pass 2: line-based strategies (if default returned nothing)
            if not page_tables:
                page_tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "intersection_y_tolerance": 5,
                        "intersection_x_tolerance": 5,
                    }
                ) or []

            for t_idx, tbl in enumerate(page_tables, start=1):
                if not tbl:
                    continue

                # Rectangularize and clean
                df = _ensure_rectangular(tbl)
                if df.empty:
                    continue

                # Drop fully empty rows/cols
                df = df.replace({None: ""}).fillna("")
                if df.shape[0] == 0 or df.shape[1] == 0:
                    continue
                mask_empty_rows = df.astype(str).apply(lambda r: "".join(r), axis=1).str.strip() == ""
                df = df.loc[~mask_empty_rows]
                if df.shape[0] == 0:
                    continue
                mask_empty_cols = df.astype(str).apply(lambda c: "".join(c)).str.strip() == ""
                df = df.loc[:, ~mask_empty_cols]
                if df.shape[1] == 0:
                    continue

                # Promote first row to header (like your Streamlit app)
                df = _promote_first_row_as_header(df)
                if df.shape[1] == 0:
                    continue
                df.columns = [str(c).strip() if str(c).strip() != "" else "None" for c in df.columns]

                # Build schema + validators using your existing logic
                r = infer_from_dataframe(df)
                r["__source_table__"] = f"page_{p_idx}_table_{t_idx}"
                results.append(r)

    if not results:
        results = [{"schema": {"columns": []}, "validators": {}}]
    return results



def infer_from_sql(file_text: str) -> List[Dict[str, Any]]:
    """
    Naive parser for CREATE TABLE statements.
    """
    results: List[Dict[str, Any]] = []
    statements = sqlparse.parse(file_text)
    for stmt in statements:
        s = str(stmt).strip()
        if not s.lower().startswith("create table"):
            continue

        name_part = s.split("(")[0]
        table_name = name_part.split()[-1].strip('"`')

        cols_part = s[s.find("(") + 1 : s.rfind(")")]
        cols: List[Dict[str, Any]] = []
        for raw in cols_part.split(","):
            line = raw.strip()
            if not line or line.lower().startswith(
                ("primary", "foreign", "unique", "constraint")
            ):
                continue
            pieces = line.split()
            col_name = pieces[0].strip('"`')
            type_token = (pieces[1] if len(pieces) > 1 else "text").lower()

            if any(t in type_token for t in ["uuid"]):
                ctype = "uuid"
            elif any(t in type_token for t in ["int", "serial", "bigint", "smallint"]):
                ctype = "integer"
            elif any(t in type_token for t in ["real", "double", "float", "numeric", "decimal"]):
                ctype = "float"
            elif "bool" in type_token:
                ctype = "boolean"
            elif "timestamp" in type_token:
                ctype = "datetime"
            elif any(t in type_token for t in ["date", "time"]):
                ctype = "date"
            else:
                ctype = "string"

            cols.append({"name": col_name, "type": ctype})

        # For SQL, mark only ID-like as required/unique
        validators: Dict[str, Dict[str, Any]] = {}
        for c in cols:
            is_id = is_id_like(c["name"], c["type"], [])
            validators[c["name"]] = {
                "type": c["type"],
                "required": bool(is_id),
                "unique": bool(is_id),
            }

        results.append(
            {
                "schema": {"columns": cols},
                "validators": validators,
                "__source_table__": table_name,
            }
        )

    if not results:
        results = [{"schema": {"columns": []}, "validators": {}}]
    return results


def infer_from_file(
    file_bytes: bytes,
    filename: str,
    source_hint: Optional[str],
    header_row: Optional[int] = None,
    sheets: Optional[List[str]] = None,
    sheet_header_rows: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    kind = (source_hint or (filename.split(".")[-1] if "." in filename else "")).lower()

    if kind in {"csv"}:
        if header_row is None:
            raise ValueError("header_row is required for csv (0-based index)")
        return infer_from_csv(file_bytes, header_row)

    if kind in {"xlsx", "xls", "excel"}:
        if header_row is None:
            raise ValueError("header_row is required for excel (0-based index)")
        return infer_from_excel(
            file_bytes,
            header_row,
            sheets=sheets,
            sheet_header_rows=sheet_header_rows,
        )

    if kind in {"json"}:
        return infer_from_json(file_bytes)

    if kind in {"pdf"}:
        return infer_from_pdf(file_bytes)

    ft = guess(file_bytes)
    if ft and ft.mime == "application/pdf":
        return infer_from_pdf(file_bytes)

    if header_row is None:
        raise ValueError("header_row is required for csv/excel (0-based index)")
    return infer_from_csv(file_bytes, header_row)