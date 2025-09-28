import re
from datetime import datetime
from dateutil.parser import parse as dtparse
from typing import Iterable, Optional, Tuple, List

# Standard, widely-used email pattern (your request)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
UUID_RE  = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
PHONE_RE = re.compile(r"^\+?\d[\d\s\-\(\)]{7,}$")

BOOL_TRUES  = {"true","t","1","yes","y"}
BOOL_FALSES = {"false","f","0","no","n"}

def try_bool(x: str) -> Optional[bool]:
    s = str(x).strip().lower()
    if s in BOOL_TRUES: return True
    if s in BOOL_FALSES: return False
    return None

def _non_null(values: Iterable) -> List[str]:
    nn = []
    for v in values:
        if v is None: 
            continue
        sv = str(v).strip()
        if sv == "":
            continue
        nn.append(sv)
    return nn

def guess_scalar_type(values: Iterable) -> str:
    """Return one of: uuid, integer, float, boolean, date, datetime, string."""
    nn = _non_null(values)
    if not nn:
        return "string"

    # UUID majority?
    uuid_hits = sum(1 for v in nn if UUID_RE.match(v))
    if uuid_hits / len(nn) >= 0.8:
        return "uuid"

    # boolean?
    bools = sum(1 for v in nn if try_bool(v) is not None)
    # integer?
    ints = 0
    floats = 0
    dates = 0
    dts = 0
    for v in nn:
        if try_bool(v) is not None:
            continue
        try:
            # int if representation is clean integer
            if str(int(float(v))) == v or v.isdigit():
                ints += 1
                continue
        except Exception:
            pass
        try:
            float(v)
            floats += 1
            continue
        except Exception:
            pass
        try:
            d = dtparse(v)
            if d.time() == datetime.min.time():
                dates += 1
            else:
                dts += 1
        except Exception:
            pass

    counts = [
        ("integer", ints),
        ("float", floats),
        ("boolean", bools),
        ("date", dates),
        ("datetime", dts),
    ]
    best = max(counts, key=lambda x: x[1])
    return best[0] if best[1] > 0 else "string"

def best_regex(values: Iterable) -> Optional[str]:
    """Return a useful regex if most values match a pattern (email/uuid/phone)."""
    nn = _non_null(values)
    if not nn:
        return None
    candidates = [EMAIL_RE, UUID_RE, PHONE_RE]
    for rx in candidates:
        m = sum(1 for v in nn if rx.match(v))
        if m / len(nn) >= 0.8:
            return rx.pattern
    return None

def numeric_bounds(values: Iterable) -> Tuple[Optional[float], Optional[float]]:
    nums = []
    for v in values:
        if v is None or str(v).strip()=="":
            continue
        try:
            nums.append(float(v))
        except Exception:
            continue
    if not nums:
        return None, None
    return min(nums), max(nums)

def is_id_like(col_name: str, dtype: str, values: Iterable) -> bool:
    """
    Heuristics to tag a column as 'ID-like':
      - name contains 'id' or equals 'uuid'
      - or dtype == 'uuid'
      - or numeric, unique, and looks like a surrogate key (no negatives, many distincts)
    """
    name = (col_name or "").strip().lower()
    if name in {"id", "uuid"} or name.endswith("_id") or name.startswith("id_"):
        return True
    if dtype == "uuid":
        return True

    nn = _non_null(values)
    distinct = len(set(nn))
    # numeric candidate
    if dtype in {"integer","float"} and distinct >= max(3, int(0.9 * len(nn))):
        # no negatives for ids (common)
        try:
            if all(float(v) >= 0 for v in nn):
                return True
        except Exception:
            pass
    return False

def is_age_column(col_name: str) -> bool:
    n = (col_name or "").strip().lower()
    return n in {"age", "ages"} or n.endswith("_age")
