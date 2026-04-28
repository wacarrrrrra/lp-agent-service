"""
Image index cycling — state persisted in WordPress as a draft post with slug
'blog-image-state'. This survives Render redeploys (no local filesystem dependency).

Falls back to local image_state.json if WP credentials are not available (local dev).
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import httpx

logger = logging.getLogger("uvicorn.error")

_MAX_INDEX = 6
_WP_STATE_SLUG = "blog-image-state"
_STATE_FILE = Path("image_state.json")  # local fallback only

WP_BASE_URL = os.getenv("WP_BASE_URL", "https://datahub.com")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")


def _auth_headers() -> Dict[str, str]:
    import base64
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# WordPress state store
# ---------------------------------------------------------------------------

def _wp_read_state() -> Dict:
    """Read state dict from the WP draft post content. Returns {} on any failure."""
    try:
        r = httpx.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts",
            params={"slug": _WP_STATE_SLUG, "status": "draft,private", "per_page": 1},
            headers=_auth_headers(),
            timeout=10,
        )
        data = r.json()
        if isinstance(data, list) and data:
            raw = data[0].get("excerpt", {}).get("raw") or data[0].get("excerpt", {}).get("rendered", "")
            # Strip HTML tags that WP may add
            raw = raw.strip().lstrip("<p>").rstrip("</p>").strip()
            return json.loads(raw)
    except Exception as e:
        logger.warning("wp_read_state failed: %s", e)
    return {}


def _wp_write_state(state: Dict) -> None:
    """Upsert the WP state post with the new state JSON in the excerpt field."""
    try:
        raw_json = json.dumps(state)
        headers = _auth_headers()

        # Check if post exists
        r = httpx.get(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts",
            params={"slug": _WP_STATE_SLUG, "status": "draft,private", "per_page": 1},
            headers=headers,
            timeout=10,
        )
        data = r.json()

        payload = {
            "title": "Blog Image State (do not delete)",
            "slug": _WP_STATE_SLUG,
            "status": "private",
            "excerpt": raw_json,
            "content": raw_json,
        }

        if isinstance(data, list) and data:
            post_id = data[0]["id"]
            httpx.post(
                f"{WP_BASE_URL}/wp-json/wp/v2/posts/{post_id}",
                json=payload,
                headers=headers,
                timeout=10,
            )
        else:
            httpx.post(
                f"{WP_BASE_URL}/wp-json/wp/v2/posts",
                json=payload,
                headers=headers,
                timeout=10,
            )
    except Exception as e:
        logger.warning("wp_write_state failed: %s", e)


# ---------------------------------------------------------------------------
# Local fallback (dev / no WP creds)
# ---------------------------------------------------------------------------

def _local_read_state() -> Dict:
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _local_write_state(state: Dict) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not write image_state.json: %s", e)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_and_advance_image_index(slug: str = "", category: str = "product") -> int:
    """
    Read current index for the category, advance it (wrapping at _MAX_INDEX),
    persist the new state, and return the index that should be used for this post.
    """
    use_wp = bool(WP_USER and WP_APP_PASSWORD)

    state = _wp_read_state() if use_wp else _local_read_state()
    if not state:
        state = {}

    cat = state.setdefault(category, {"current_index": 1, "last_updated": "", "last_slug": ""})
    idx = int(cat.get("current_index", 1))
    next_idx = (idx % _MAX_INDEX) + 1

    cat["current_index"] = next_idx
    cat["last_updated"] = datetime.utcnow().isoformat() + "Z"
    cat["last_slug"] = slug
    state[category] = cat

    if use_wp:
        _wp_write_state(state)
    else:
        _local_write_state(state)

    logger.info("Image index: using %d, next will be %d (slug=%s)", idx, next_idx, slug)
    return idx


def get_image_filenames(idx: int, category: str = "product") -> Tuple[str, str, str]:
    """Return (hero, featured, socialcard) filenames for the given index."""
    idx_str = str(idx).zfill(2)
    return (
        f"{idx_str}-hero-{category}-blog-general.png",
        f"{idx_str}-featured-{category}-blog-general.png",
        f"{idx_str}-socialcard-{category}-blog-general.png",
    )
