def clean_name(s: str | None) -> str | None:
    if not s:
        return None
    s = " ".join(s.strip().split())  # collapse spaces
    # Simple capitalization; keep existing casing if you prefer
    return s[:80]

def names_from_google_userinfo(userinfo: dict, email: str) -> tuple[str | None, str | None]:
    gn = clean_name(userinfo.get("given_name"))
    fn = clean_name(userinfo.get("family_name"))
    if gn or fn:
        return gn, fn
    full = clean_name(userinfo.get("name"))
    if full:
        parts = [p for p in full.replace("_", " ").replace(".", " ").split() if p]
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return parts[0], None
    # Fallback last resort: email local-part
    local = email.split("@", 1)[0]
    pieces = [p for p in local.replace("_", " ").replace(".", " ").split() if p]
    if len(pieces) >= 2:
        return pieces[0].capitalize(), " ".join(p.capitalize() for p in pieces[1:])
    return local.capitalize(), None
