from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Set, Tuple

# Generic safe converters

def to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    return str(value).lower() in ("true", "1", "yes", "y")


def map_to_model_columns(
    model,
    data: Mapping[str, Any],
    *,
    exclude: Optional[Iterable[str]] = None,
    aliases: Optional[Mapping[str, str]] = None,
    transforms: Optional[Mapping[str, Callable[[Any], Any]]] = None,
    defaults: Optional[Mapping[str, Any]] = None,
    inject: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Map an input dict to a SQLAlchemy model's column kwargs.

    Steps:
    - apply aliases (rename input keys)
    - apply transforms (value-level coercions)
    - apply defaults (only if key missing or value is None/"")
    - inject values (override)
    - filter to model columns minus excluded
    """
    # start with a shallow copy
    out: Dict[str, Any] = dict(data)

    # apply aliases
    if aliases:
        for src, dst in aliases.items():
            if src in out:
                # don't clobber an explicitly provided destination key
                if dst not in out:
                    out[dst] = out[src]
                # remove the source key regardless; it isn't a model column
                del out[src]

    # apply transforms
    if transforms:
        for key, fn in transforms.items():
            if key in out:
                out[key] = fn(out.get(key))

    # apply defaults (fill only when missing or empty)
    if defaults:
        for key, val in defaults.items():
            if key not in out or out.get(key) in (None, ""):
                out[key] = val

    # apply inject (always override)
    if inject:
        out.update(inject)

    # filter to model columns
    allowed: Set[str] = {c.name for c in model.__table__.columns}
    excluded: Set[str] = set(exclude or ()) | {"created_at", "updated_at", "bpa_json"}
    allowed = allowed - excluded

    # Drop None/empty-string values so DB defaults can apply
    return {k: v for k, v in out.items() if k in allowed and v not in (None, "")}
