import re

_ALLOWED = re.compile(r"^[a-z0-9_]+$")

def slugify(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t

def validate_id(value: str) -> bool:
    return bool(_ALLOWED.match(value or ""))
