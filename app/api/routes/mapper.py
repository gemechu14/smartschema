from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

router = APIRouter()


class LociMapperRequest(BaseModel):
    schema_columns: List[str] = Field(..., description="List of canonical schema column names")
    import_columns: List[str] = Field(..., description="List of incoming import column names to match")
    min_confidence: Optional[float] = Field(0.50, description="Minimum confidence threshold to consider a match (0-1)")
    model_name: Optional[str] = Field("sentence-transformers/all-MiniLM-L6-v2", description="SentenceTransformer model to use; optional")


class LociMapperMatch(BaseModel):
    schema: str
    import_: str = Field(..., alias="import")
    confidence: float


class LociMapperResponse(BaseModel):
    matches: List[Dict[str, Any]]
    unmatched_schema: List[str]
    unmatched_import: List[str]


def _norm(s: str) -> str:
    import re
    _ABBREV = {
        "dob": "date_of_birth", "fname": "first_name", "lname": "last_name",
        "tel": "phone", "ph": "phone", "mob": "mobile", "addr": "address",
        "zip": "postal_code", "qty": "quantity", "amt": "amount", "ssn": "social_security_number",
    }
    _STOP = {"id", "no", "num", "code"}
    s = s.strip().lower()
    s = re.sub(r"[\s\-.]+", "_", s)
    parts = [p for p in re.split(r"[_/]", s) if p]
    parts = [_ABBREV.get(p, p) for p in parts if p not in _STOP]
    return "_".join(parts)


class ColumnMatcherFast:
    """Lightweight column matcher that lazily loads heavy dependencies at runtime.

    It combines sentence-transformer embeddings with Jaro-Winkler lexical similarity
    and solves an assignment problem (Hungarian) to produce one-to-one matches.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", w_embed: float = 0.85, w_lex: float = 0.15):
        self.model_name = model_name
        self._model = None
        self.w_embed = w_embed
        self.w_lex = w_lex

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                # Force CPU load to avoid device-movement of meta tensors in some
                # environments (this reduces GPU/accelerate-related complexity
                # when loading models on serverless or CPU-only deployments).
                # Passing device='cpu' is supported by SentenceTransformer and
                # avoids an occasional RuntimeError coming from PyTorch when
                # attempting to copy out of "meta" tensors. If this still
                # fails, surface a clear error explaining likely causes.
                try:
                    self._model = SentenceTransformer(self.model_name, device="cpu")
                except Exception as e_inner:
                    msg = str(e_inner)
                    if "meta tensor" in msg or "to_empty" in msg:
                        # Provide a helpful, actionable error for the user.
                        raise RuntimeError(
                            "sentence-transformers failed to load the model due to PyTorch 'meta' tensors ("
                            + "this can happen with certain torch/transformers combinations). "
                            + "Common fixes: upgrade/downgrade `torch` and `sentence-transformers` to compatible versions, "
                            + "or ensure the model is loaded with a device_map that places parameters on CPU. "
                            + "Example: `pip install -U sentence-transformers torch` or try a different model release. "
                            + "Original error: " + msg
                        )
                    # re-raise other errors as a RuntimeError to be handled by the
                    # caller and turned into a 500 with a helpful message.
                    raise
            except Exception as e:
                raise RuntimeError("sentence-transformers is required for /loci-ai-mapper endpoint: " + str(e))

    def _prep_texts(self, names):
        return [f"{_norm(n)}" for n in names]

    def _sim_matrix(self, schema_cols, import_cols):
        import numpy as np
        from rapidfuzz.distance import JaroWinkler

        schema_txt = self._prep_texts(schema_cols)
        import_txt = self._prep_texts(import_cols)
        self._ensure_model()
        emb_schema = self._model.encode(schema_txt, normalize_embeddings=True)
        emb_import = self._model.encode(import_txt, normalize_embeddings=True)
        emb_sim = (emb_import @ emb_schema.T + 1.0) / 2.0
        jw = np.zeros_like(emb_sim)
        for i, imp in enumerate(import_txt):
            for j, sch in enumerate(schema_txt):
                jw[i, j] = JaroWinkler.normalized_similarity(imp, sch)
        return self.w_embed * emb_sim + self.w_lex * jw

    def match(self, schema_cols, import_cols, min_confidence=0.50):
        # defensive
        if len(schema_cols) == 0 or len(import_cols) == 0:
            return [], schema_cols[:], import_cols[:]
        import numpy as np
        from scipy.optimize import linear_sum_assignment

        sim = self._sim_matrix(schema_cols, import_cols)
        cost = 1.0 - sim
        r_idx, c_idx = linear_sum_assignment(cost)
        pairs, used_schema, used_import = [], set(), set()
        for ri, ci in zip(r_idx, c_idx):
            conf = float(sim[ri, ci])
            if conf >= min_confidence:
                pairs.append({
                    "schema": schema_cols[ci],
                    "import": import_cols[ri],
                    "confidence": round(conf, 3)
                })
                used_schema.add(ci)
                used_import.add(ri)
        unmatched_schema = [s for j, s in enumerate(schema_cols) if j not in used_schema]
        unmatched_import = [c for i, c in enumerate(import_cols) if i not in used_import]
        pairs.sort(key=lambda x: x["confidence"], reverse=True)
        return pairs, unmatched_schema, unmatched_import


@router.post("/loci-ai-mapper", response_model=LociMapperResponse, summary="Map import columns to schema columns using embeddings and lexical similarity", description="Unauthenticated helper endpoint that attempts to match incoming import column names to canonical schema column names and returns matches with confidence and unmatched lists.")
def loci_ai_mapper(body: LociMapperRequest):
    matcher = ColumnMatcherFast(model_name=body.model_name)
    try:
        pairs, unmatched_schema, unmatched_import = matcher.match(body.schema_columns, body.import_columns, min_confidence=body.min_confidence)
    except RuntimeError as e:
        # bubble a helpful error if model deps are missing
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "matches": pairs,
        "unmatched_schema": unmatched_schema,
        "unmatched_import": unmatched_import,
    }
