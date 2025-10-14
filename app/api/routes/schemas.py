from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.api.deps_auth import get_db, require_role_for_account  # <-- path-only dep
from app.models.auth_models import Role, Membership
from app.models.schema_spec import SchemaSpecification
from app.schemas.schema_spec import SchemaSpecCreate, SchemaSpecRead, SchemaSpecUpdate
from app.services.schema_inference import infer_from_file, infer_from_sql

router = APIRouter(prefix="/accounts/{account_id}/schemas", tags=["schemas"])


def _next_default_name(db: Session, account_id: UUID) -> str:
    """Generate a per-account default name like 'Schema 3'."""
    cnt = (
        db.query(func.count(SchemaSpecification.id))
        .filter(SchemaSpecification.account_id == account_id)
        .scalar()
        or 0
    )
    return f"Schema {cnt + 1}"


def _format_schema(obj: SchemaSpecification) -> dict:
    """Return a dict matching SchemaSpecRead with computed columns and formatted dates."""
    cols = 0
    try:
        cols = len(obj.schema.get("columns", [])) if obj.schema else 0
    except Exception:
        cols = 0

    fmt = lambda dt: dt.strftime("%b %d, %Y") if dt else None

    return {
        "id": obj.id,
        "schema_name": obj.schema_name,
        "description": getattr(obj, "description", None),
        "schema": obj.schema,
        "validators": obj.validators,
        "columns": cols,
        "created_at": fmt(obj.created_at),
        "updated_at": fmt(obj.updated_at),
    }


# ------------------------- CREATE -------------------------
@router.post(
    "",
    response_model=SchemaSpecRead,
    summary="Create schema (Owner/Admin only)",
    description="""
Create a schema under the account identified by the path parameter.
Only **OWNER** or **ADMIN** can create schemas. The new schema is stamped with the account and creator.
""",
)
def create_schema(
    account_id: UUID,
    body: SchemaSpecCreate,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    name = body.schema_name or _next_default_name(db, account_id)
    # normalize name for comparison
    name = name.strip() if isinstance(name, str) else name
    # ensure uniqueness per account (case-insensitive)
    existing = (
        db.query(SchemaSpecification)
        .filter(
            SchemaSpecification.account_id == account_id,
            func.lower(SchemaSpecification.schema_name) == func.lower(name),
            SchemaSpecification.deleted_at == None,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="A schema with that name already exists in this account")
    obj = SchemaSpecification(
        schema_name=name,
        schema=body.schema_body.model_dump(),
        validators=body.validators,
        account_id=account_id,            # stamp account
        created_by_user_id=user.id,       # stamp creator
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _format_schema(obj)


# ------------------------- LIST -------------------------
@router.get(
    "",
    response_model=List[SchemaSpecRead],
    summary="List schemas in account (visibility-aware)",
    description="""
Returns schemas for the account identified by the path parameter.

- **OWNER/ADMIN**: see all schemas.
- **MEMBER/VIEWER**: see only schemas explicitly granted in their `manage_schema_ids`.
"""
)
def list_schemas(
    account_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, role = tup

    q = db.query(SchemaSpecification).filter(
        SchemaSpecification.account_id == account_id,
        SchemaSpecification.deleted_at == None,
    )

    def _format(obj: SchemaSpecification) -> dict:
        # compute number of columns from the stored JSON schema
        cols = 0
        try:
            cols = len(obj.schema.get("columns", [])) if obj.schema else 0
        except Exception:
            cols = 0

        fmt = lambda dt: dt.strftime("%b %d, %Y") if dt else None

        return {
            "id": obj.id,
            "schema_name": obj.schema_name,
            "description": getattr(obj, "description", None),
            "schema": obj.schema,
            "validators": obj.validators,
            "columns": cols,
            "created_at": fmt(obj.created_at),
            "updated_at": fmt(obj.updated_at),
        }

    if role in {Role.OWNER, Role.ADMIN}:
        objs = q.order_by(SchemaSpecification.created_at.desc()).all()
        return [_format(o) for o in objs]

    # member/viewer: restrict to allowed schema ids
    mem = (
        db.query(Membership)
        .filter(Membership.account_id == account_id, Membership.user_id == user.id)
        .first()
    )
    raw_ids = mem.manage_schema_ids or []
    allowed_ids: list[UUID] = []
    for x in raw_ids:
        try:
            allowed_ids.append(UUID(str(x)))
        except Exception:
            continue

    if not allowed_ids:
        return []

    objs = (
        q.filter(SchemaSpecification.id.in_(allowed_ids))
         .order_by(SchemaSpecification.created_at.desc())
         .all()
    )

    return [_format(o) for o in objs]



# ------------------------- GET ONE -------------------------
@router.get(
    "/{schema_id}",
    response_model=SchemaSpecRead,
    summary="Get schema by id (visibility-aware)",
    description="""
Fetch a single schema by id, scoped to the account in the path.

- **OWNER/ADMIN**: can view any schema in the account.
- **MEMBER/VIEWER**: can view only if the schema is in their `manage_schema_ids`.

Returns **404** if not found or not visible to the caller.
"""
)
def get_schema(
    account_id: UUID,
    schema_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, role = tup

    # Try fetch within account first
    obj = (
        db.query(SchemaSpecification)
        .filter(
            SchemaSpecification.id == schema_id,
            SchemaSpecification.account_id == account_id,
            SchemaSpecification.deleted_at == None,
        )
        .first()
    )
    if not obj:
        # Do not leak whether it exists in another account
        raise HTTPException(404, "Schema not found")

    if role in {Role.OWNER, Role.ADMIN}:
        return _format_schema(obj)

    # member/viewer: check visibility
    mem = (
        db.query(Membership)
        .filter(Membership.account_id == account_id, Membership.user_id == user.id)
        .first()
    )
    raw_ids = mem.manage_schema_ids or []
    allowed = {str(UUID(str(x))) for x in raw_ids if str(x)}
    if str(obj.id) not in allowed:
        # Hide existence to avoid enumeration
        raise HTTPException(404, "Schema not found")

    return _format_schema(obj)



# ------------------------- UPDATE -------------------------
@router.put(
    "/{schema_id}",
    response_model=SchemaSpecRead,
    summary="Update schema (Owner/Admin only)",
    description="Update a schema in the account identified by the path parameter. Only **OWNER** or **ADMIN** may update.",
)
def update_schema(
    account_id: UUID,
    schema_id: UUID,
    body: SchemaSpecUpdate,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(SchemaSpecification)
        .filter(SchemaSpecification.id == schema_id, SchemaSpecification.account_id == account_id)
        .first()
    )
    if not obj:
        raise HTTPException(404, "Schema not found")

    if body.schema_name is not None:
        new_name = body.schema_name.strip() if isinstance(body.schema_name, str) else body.schema_name
        # check uniqueness per account (case-insensitive), ignoring current object
        conflict = (
            db.query(SchemaSpecification)
            .filter(
                SchemaSpecification.account_id == account_id,
                func.lower(SchemaSpecification.schema_name) == func.lower(new_name),
                SchemaSpecification.id != obj.id,
                SchemaSpecification.deleted_at == None,
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="A schema with that name already exists in this account")
        obj.schema_name = new_name
    if body.schema_body is not None:
        obj.schema = body.schema_body.model_dump()
    if body.validators is not None:
        obj.validators = body.validators

    db.commit()
    db.refresh(obj)
    return _format_schema(obj)


# ------------------------- DELETE -------------------------
@router.delete(
    "/{schema_id}",
    status_code=204,
    summary="Delete schema (Owner/Admin only)",
    description="Delete a schema in the account identified by the path parameter. Only **OWNER** or **ADMIN** may delete.",
)
def delete_schema(
    account_id: UUID,
    schema_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(SchemaSpecification)
        .filter(SchemaSpecification.id == schema_id, SchemaSpecification.account_id == account_id)
        .first()
    )
    if not obj:
        raise HTTPException(404, "Schema not found")

    # soft-delete
    obj.deleted_at = datetime.utcnow()
    db.commit()
    return


# ------------------------- IMPORT -------------------------
# The import endpoint is temporarily disabled so the first 'create' API
# is used for creating schema specifications. To re-enable, uncomment
# the following function and its decorator.
#
## @router.post(
##     "/import",
##     response_model=List[SchemaSpecRead],
##     summary="Import schemas from file/SQL (Owner/Admin only)",
##     description="""
## Parse a file (csv/excel/pdf/json/sql) and create one or more schemas for this account.
## Requires **OWNER/ADMIN**. For CSV/Excel, `header_row` is required (0-based). For Excel, you can pass `sheets`
## and `sheet_header_rows` to control per-sheet parsing.
## """,
## )
## async def import_schema(
##     account_id: UUID,
##     file: UploadFile = File(...),
##     source_type: str | None = Query(default=None, description="csv|excel|pdf|sql|json"),
##     header_row: int | None = Query(
##         default=None,
##         ge=0,
##         description="REQUIRED for csv/excel. 0-based row index of the header within the file/sheet."
##     ),
##     sheets: str | None = Query(
##         default=None,
##         description="(excel only) Comma-separated sheet names or 0-based indices to include. Omit for all."
##     ),
##     sheet_header_rows: str | None = Query(
##         default=None,
##         description="(excel only) Comma-separated integers matching 'sheets' to override header_row per sheet."
##     ),
##     tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
##     db: Session = Depends(get_db),
## ):
##     user, _aid, _role = tup
##
##     raw = await file.read()
##     st = (source_type or "").lower()
##
##     # Enforce header_row for CSV/Excel
##     if st in {"csv", "excel"} and header_row is None:
##         raise HTTPException(
##             status_code=400,
##             detail="header_row is required for csv/excel (0-based index). Example: ?source_type=csv&header_row=2"
##         )
##
##     # Parse optional Excel helpers
##     sheets_list = None
##     per_sheet_rows = None
##     if st == "excel":
##         if sheets:
##             sheets_list = [s.strip() for s in sheets.split(",") if s.strip() != ""]
##         if sheet_header_rows:
##             try:
##                 per_sheet_rows = [int(x.strip()) for x in sheet_header_rows.split(",")]
##             except ValueError:
##                 raise HTTPException(status_code=400, detail="sheet_header_rows must be comma-separated integers")
##             if not sheets_list or len(per_sheet_rows) != len(sheets_list):
##                 raise HTTPException(
##                     status_code=400,
##                     detail="sheet_header_rows count must match 'sheets' count"
##                 )
##
##     try:
##         if st == "sql" or file.filename.lower().endswith(".sql"):
##             inferred = infer_from_sql(raw.decode("utf-8", errors="ignore"))
##         else:
##             inferred = infer_from_file(
##                 raw,
##                 file.filename,
##                 st,
##                 header_row=header_row,
##                 sheets=sheets_list,
##                 sheet_header_rows=per_sheet_rows,
##             )
##     except ValueError as e:
##         raise HTTPException(status_code=400, detail=str(e))
##     except Exception as e:
##         raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
##
##     created: List[SchemaSpecification] = []
##     for item in inferred:
##         name_hint = item.get("__source_sheet__") or item.get("__source_table__")
##         schema_name = name_hint or _next_default_name(db, account_id)
##         obj = SchemaSpecification(
##             schema_name=schema_name,
##             schema=item["schema"],
##             validators=item.get("validators", {}),
##             account_id=account_id,          # stamp account
##             created_by_user_id=user.id,     # stamp creator
##         )
##         db.add(obj)
##         db.commit()
##         db.refresh(obj)
##         created.append(obj)
##     return created
