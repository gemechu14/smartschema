from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ColumnDef(BaseModel):
    name: str
    # allowed: "string" | "integer" | "float" | "boolean" | "date" | "datetime"
    type: str

class SchemaJSON(BaseModel):
    columns: List[ColumnDef] = Field(default_factory=list)

# ---------- CREATE ----------
class SchemaSpecCreate(BaseModel):
    schema_name: Optional[str] = None
    # optional human-readable description for the schema specification
    description: Optional[str] = None
    # external key is "schema"; internal field is "schema_body"
    schema_body: SchemaJSON = Field(alias="schema", validation_alias="schema")
    # validators is a plain dict: column -> rules
    validators: Dict[str, Dict[str, Any]]

    # allow using internal names when constructing in Python
    model_config = ConfigDict(populate_by_name=True)

# ---------- READ ----------
class SchemaSpecRead(BaseModel):
    id: UUID
    schema_name: str
    description: Optional[str] = None
    # expose "schema" in JSON; read from ORM attr "schema"
    schema_body: SchemaJSON = Field(alias="schema", validation_alias="schema")
    validators: Dict[str, Dict[str, Any]]

    # computed / presentation-only fields (not stored in DB)
    columns: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # pydantic v2 style
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# ---------- UPDATE ----------
class SchemaSpecUpdate(BaseModel):
    schema_name: Optional[str] = None
    description: Optional[str] = None
    schema_body: Optional[SchemaJSON] = Field(default=None, alias="schema", validation_alias="schema")
    validators: Optional[Dict[str, Dict[str, Any]]] = None

    model_config = ConfigDict(populate_by_name=True)
