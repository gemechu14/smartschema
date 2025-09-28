from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ColumnDef(BaseModel):
    name: str
    # allowed: "string" | "integer" | "float" | "boolean" | "date" | "datetime"
    type: str

class SchemaJSON(BaseModel):
    columns: List[ColumnDef] = Field(default_factory=list)

class SchemaSpecCreate(BaseModel):
    schema_name: Optional[str] = None
    schema: SchemaJSON
    # validators is a plain dict: column -> rules
    validators: Dict[str, Dict[str, Any]]

class SchemaSpecRead(BaseModel):
    id: UUID
    schema_name: str
    schema: SchemaJSON
    validators: Dict[str, Dict[str, Any]]

    # pydantic v2 style
    model_config = ConfigDict(from_attributes=True)

class SchemaSpecUpdate(BaseModel):
    schema_name: Optional[str] = None
    schema: Optional[SchemaJSON] = None
    validators: Optional[Dict[str, Dict[str, Any]]] = None
