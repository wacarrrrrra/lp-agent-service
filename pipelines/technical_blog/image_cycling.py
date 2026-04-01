import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger("uvicorn.error")

_STATE_FILE = Path("image_state.json")
_MAX_INDEX = 6


def _read_state() -> Dict:
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"product": {"current_index": 1, "last_updated": "", "last_slug": ""}}


def _write_state(state: Dict) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not write image_state.json: %s", e)


def get_and_advance_image_index(slug: str = "", category: str = "product") -> int:
    """Read current index, advance it (wrapping at _MAX_INDEX), persist, return current."""
    state = _read_state()
    cat = state.setdefault(category, {"current_index": 1, "last_updated": "", "last_slug": ""})
    idx = int(cat.get("current_index", 1))
    next_idx = (idx % _MAX_INDEX) + 1
    cat["current_index"] = next_idx
    cat["last_updated"] = datetime.utcnow().isoformat() + "Z"
    cat["last_slug"] = slug
    state[category] = cat
    _write_state(state)
    return idx


def get_image_filenames(idx: int, category: str = "product") -> Tuple[str, str, str]:
    """Return (hero, featured, socialcard) filenames for the given index."""
    idx_str = str(idx).zfill(2)
    return (
        f"images/{category}/{idx_str}-hero-{category}-blog-general.png",
        f"images/{category}/{idx_str}-featured-{category}-blog-general.png",
        f"images/{category}/{idx_str}-socialcard-{category}-blog-general.png",
    )
