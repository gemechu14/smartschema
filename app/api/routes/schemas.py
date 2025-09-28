from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_db
from app.models.schema_spec import SchemaSpecification
from app.schemas.schema_spec import SchemaSpecCreate, SchemaSpecRead, SchemaSpecUpdate
from app.services.schema_inference import infer_from_file, infer_from_sql

router = APIRouter(prefix="/schemas", tags=["schemas"])

def _next_default_name(db: Session) -> str:
    cnt = db.query(func.count(SchemaSpecification.id)).scalar() or 0
    return f"Schema {cnt + 1}"

@router.post("", response_model=SchemaSpecRead)
def create_schema(body: SchemaSpecCreate, db: Session = Depends(get_db)):
    name = body.schema_name or _next_default_name(db)
    obj = SchemaSpecification(
        schema_name=name,
        schema=body.schema.model_dump(),
        validators=body.validators
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("", response_model=List[SchemaSpecRead])
def list_schemas(db: Session = Depends(get_db)):
    return db.query(SchemaSpecification).order_by(SchemaSpecification.created_at.desc()).all()

@router.get("/{schema_id}", response_model=SchemaSpecRead)
def get_schema(schema_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(SchemaSpecification, schema_id)
    if not obj:
        raise HTTPException(404, "Schema not found")
    return obj

@router.put("/{schema_id}", response_model=SchemaSpecRead)
def update_schema(schema_id: UUID, body: SchemaSpecUpdate, db: Session = Depends(get_db)):
    obj = db.get(SchemaSpecification, schema_id)
    if not obj:
        raise HTTPException(404, "Schema not found")
    if body.schema_name is not None:
        obj.schema_name = body.schema_name
    if body.schema is not None:
        obj.schema = body.schema.model_dump()
    if body.validators is not None:
        obj.validators = body.validators
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{schema_id}", status_code=204)
def delete_schema(schema_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(SchemaSpecification, schema_id)
    if not obj:
        raise HTTPException(404, "Schema not found")
    db.delete(obj)
    db.commit()
    return

@router.post("/import", response_model=List[SchemaSpecRead])
async def import_schema(
    file: UploadFile = File(...),
    source_type: str | None = Query(default=None, description="csv|excel|pdf|sql|json"),
    header_row: int | None = Query(
        default=None,
        ge=0,
        description="REQUIRED for csv/excel. 0-based row index of the header within the file/sheet."
    ),
    sheets: str | None = Query(
        default=None,
        description="(excel only) Comma-separated sheet names or 0-based indices to include. Omit for all."
    ),
    sheet_header_rows: str | None = Query(
        default=None,
        description="(excel only) Comma-separated integers matching 'sheets' to override header_row per sheet."
    ),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    st = (source_type or "").lower()

    # Enforce header_row for CSV/Excel
    if st in {"csv", "excel"} and header_row is None:
        raise HTTPException(
            status_code=400,
            detail="header_row is required for csv/excel (0-based index). Example: ?source_type=csv&header_row=2"
        )

    # Parse optional Excel helpers
    sheets_list = None
    per_sheet_rows = None
    if st == "excel":
        if sheets:
            sheets_list = [s.strip() for s in sheets.split(",") if s.strip() != ""]
        if sheet_header_rows:
            try:
                per_sheet_rows = [int(x.strip()) for x in sheet_header_rows.split(",")]
            except ValueError:
                raise HTTPException(status_code=400, detail="sheet_header_rows must be comma-separated integers")
            if not sheets_list or len(per_sheet_rows) != len(sheets_list):
                raise HTTPException(
                    status_code=400,
                    detail="sheet_header_rows count must match 'sheets' count"
                )

    try:
        if st == "sql" or file.filename.lower().endswith(".sql"):
            inferred = infer_from_sql(raw.decode("utf-8", errors="ignore"))
        else:
            inferred = infer_from_file(
                raw,
                file.filename,
                st,
                header_row=header_row,
                sheets=sheets_list,
                sheet_header_rows=per_sheet_rows,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    created = []
    for item in inferred:
        name_hint = item.get("__source_sheet__") or item.get("__source_table__")
        schema_name = name_hint or _next_default_name(db)
        obj = SchemaSpecification(schema_name=schema_name, schema=item["schema"], validators=item["validators"])
        db.add(obj)
        db.commit()
        db.refresh(obj)
        created.append(obj)
    return created