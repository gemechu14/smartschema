"""
Import every model module here once so that Base.metadata is fully populated.

Add a single import line here whenever you create a new model module.
"""

from app.db.base import Base  # the shared Declarative Base

# --- import all your model modules (side-effect: tables register on Base.metadata)
from app.models import schema_spec  # noqa
from app.models import auth_models  # noqa
# from app.models import projects  # <- add new modules like this

# expose for Alembic
metadata = Base.metadata
