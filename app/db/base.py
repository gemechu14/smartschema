# app/db/base.py
from sqlalchemy.orm import DeclarativeBase

# 1) Single Declarative Base used by ALL models
class Base(DeclarativeBase):
    pass

# 2) Import all model modules so their tables register with Base.metadata
#    (Do NOT put any runtime code here—just imports.)
#    Add new models here as your project grows.
from app.models import schema_spec          # noqa: F401
from app.models import auth_models          # noqa: F401
# from app.models import another_module     # noqa: F401  <-- add future models here
