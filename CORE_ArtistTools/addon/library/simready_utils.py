# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import time

import bpy
import requests
from PIL import Image

blip_model = None
blip_processor = None

# --- Module-level guards/state ---
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "BlenderCORETools/0.1.0 (nvidia-internal-application)"})

_LAST_CALL_TS = 0.0  # for naive rate limiting
_MIN_INTERVAL = 0.6  # seconds between calls (adjust as needed)
_CACHE = {}  # query -> (ts, result)
_CACHE_TTL = 3600  # 1 hour cache
_MAX_RETRIES = 2  # how many times to retry on 429/403
_BASE_BACKOFF = 0.8  # seconds; exponential-ish backoff


def _get_cached(query: str):
    entry = _CACHE.get(query)
    if not entry:
        return None
    ts, result = entry
    if time.monotonic() - ts < _CACHE_TTL:
        return result
    # expired
    _CACHE.pop(query, None)
    return None


def _set_cache(query: str, result):
    _CACHE[query] = (time.monotonic(), result)


def _respect_rate_limit():
    global _LAST_CALL_TS
    now = time.monotonic()
    elapsed = now - _LAST_CALL_TS
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL_TS = time.monotonic()


def search_wikidata(query: str):
    """Safe Wikidata search with rate limit, caching, and polite retries."""
    if not query or not query.strip():
        return []

    # 1) Serve from cache if available
    cached = _get_cached(query)
    if cached is not None:
        return cached

    url = "https://www.wikidata.org/w/api.php"
    params = {"action": "wbsearchentities", "format": "json", "language": "en", "search": query}

    # 2) Rate limit (helps if Blender is accidentally looping)
    _respect_rate_limit()

    # 3) Try with a couple of retries on 429/403, respecting Retry-After if present
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _SESSION.get(url, params=params, timeout=5, verify=True)

            # Handle rate limiting / temporary blocks explicitly
            if resp.status_code in (429, 403):
                retry_after = resp.headers.get("Retry-After")
                if attempt < _MAX_RETRIES:
                    # polite backoff
                    wait = float(retry_after) if retry_after else _BASE_BACKOFF * (attempt + 1)
                    print(f"Wikidata returned {resp.status_code}. Backing off for {wait:.2f}s…")
                    time.sleep(wait)
                    continue
                else:
                    print(f"Wikidata returned {resp.status_code} after retries.")
                    return []

            resp.raise_for_status()
            data = resp.json()
            results = data.get("search", [])
            _set_cache(query, results)
            return results

        except requests.exceptions.Timeout:
            print("Wikidata request timed out.")
            if attempt < _MAX_RETRIES:
                time.sleep(_BASE_BACKOFF * (attempt + 1))
                continue
            return []
        except requests.exceptions.SSLError as e:
            print(f"SSL verification failed: {e}")
            return []
        except requests.RequestException as e:
            # Covers ConnectionError, HTTPError after non-429/403, etc.
            print(f"Request failed: {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(_BASE_BACKOFF * (attempt + 1))
                continue
            return []


def get_wikidata_by_id(wikidata_id: str):
    """Get a specific Wikidata entity by ID and return it in search format."""
    if not wikidata_id or not wikidata_id.strip():
        return []

    # Clean the ID - remove whitespace and ensure uppercase
    wikidata_id = wikidata_id.strip().upper()

    # Validate that it looks like a Wikidata ID (Q followed by numbers, or P for properties)
    if not (wikidata_id.startswith("Q") or wikidata_id.startswith("P")):
        print(f"Invalid Wikidata ID format: {wikidata_id}. Should start with Q or P.")
        return []

    # 1) Serve from cache if available
    cache_key = f"ID:{wikidata_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": wikidata_id,
        "languages": "en",
        "props": "labels|descriptions",
    }

    # 2) Rate limit
    _respect_rate_limit()

    # 3) Try with retries
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _SESSION.get(url, params=params, timeout=5, verify=True)

            # Handle rate limiting / temporary blocks
            if resp.status_code in (429, 403):
                retry_after = resp.headers.get("Retry-After")
                if attempt < _MAX_RETRIES:
                    wait = float(retry_after) if retry_after else _BASE_BACKOFF * (attempt + 1)
                    print(f"Wikidata returned {resp.status_code}. Backing off for {wait:.2f}s…")
                    time.sleep(wait)
                    continue
                else:
                    print(f"Wikidata returned {resp.status_code} after retries.")
                    return []

            resp.raise_for_status()
            data = resp.json()

            # Parse the entity data
            entities = data.get("entities", {})
            if wikidata_id not in entities:
                print(f"Wikidata ID {wikidata_id} not found.")
                return []

            entity = entities[wikidata_id]

            # Check if entity was found (missing=-1 means it doesn't exist)
            if "missing" in entity:
                print(f"Wikidata ID {wikidata_id} does not exist.")
                return []

            # Format the result to match search_wikidata format
            result = {
                "id": wikidata_id,
                "label": entity.get("labels", {}).get("en", {}).get("value", wikidata_id),
                "description": entity.get("descriptions", {}).get("en", {}).get("value", ""),
            }

            results = [result]
            _set_cache(cache_key, results)
            return results

        except requests.exceptions.Timeout:
            print("Wikidata request timed out.")
            if attempt < _MAX_RETRIES:
                time.sleep(_BASE_BACKOFF * (attempt + 1))
                continue
            return []
        except requests.exceptions.SSLError as e:
            print(f"SSL verification failed: {e}")
            return []
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(_BASE_BACKOFF * (attempt + 1))
                continue
            return []

    return []


# Track last processed query to avoid redundant updates
_last_enum_query = ""
# Store current enum items for property access
_current_enum_items = [("NONE", "Search first", "")]


def get_wikidata_items(self, context):
    """Dynamic items function for wikidata_results EnumProperty"""
    global _current_enum_items
    return _current_enum_items


def update_enum_items(self, context):
    global _last_enum_query

    # Check if we're in ID mode
    use_id_mode = getattr(context.scene.global_metadata, "wikidata_use_id", False)

    if use_id_mode:
        # ID mode - use wikidata_query_id
        query = getattr(context.scene.global_metadata, "wikidata_query_id", "")
        query_key = f"ID:{query}"
    else:
        # Text search mode - use wikidata_query
        query = getattr(context.scene, "wikidata_query", "")
        query_key = query

    # Early return for empty queries - just set default state
    if not query or not query.strip():
        default_items = [("NONE", "Enter ID" if use_id_mode else "Search first", "")]
        # Reset scene value to safe default
        try:
            context.scene.wikidata_results = "NONE"
        except (AttributeError, TypeError):
            pass  # Property might not exist yet
        _last_enum_query = ""
        return default_items

    # Skip if query hasn't changed
    query_clean = query.strip()
    query_key_clean = query_key.strip() if not use_id_mode else f"ID:{query_clean}"
    if query_key_clean == _last_enum_query:
        # Return current items without rebuilding
        current_enum = getattr(bpy.types.Scene, "wikidata_results", None)
        if current_enum and hasattr(current_enum, "keywords") and "items" in current_enum.keywords:
            return current_enum.keywords["items"]

    # Search based on mode
    if use_id_mode:
        results = get_wikidata_by_id(query_clean)
    else:
        results = search_wikidata(query_clean)

    items = []
    for i, item in enumerate(results):
        label = item.get("label", "Unknown")
        desc = item.get("description", "")
        display = f"{label} — {desc}" if desc else label
        items.append((item["id"], display, desc))

    # Process items and store in module variable for the property to use
    items = items or [("NONE", "No results found" if not use_id_mode else "ID not found", "")]

    # Store items globally so the enum property can access them
    global _current_enum_items
    _current_enum_items = items

    # Update tracking
    _last_enum_query = query_key_clean
    return items


def load_blip_model():
    global blip_model, blip_processor
    if blip_model is None or blip_processor is None:
        try:
            import torch
            from transformers import BlipForConditionalGeneration, BlipProcessor

            blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            blip_model.to("cuda" if torch.cuda.is_available() else "cpu")
        except ImportError as e:
            print(f"Error loading BLIP model: {e}")
            print("PyTorch or transformers may not be installed correctly.")
            raise


def generate_caption(image_path):
    raw_image = Image.open(image_path).convert("RGB")
    inputs = blip_processor(raw_image, return_tensors="pt")
    out = blip_model.generate(**inputs)
    caption = blip_processor.decode(out[0], skip_special_tokens=True)
    return caption


def generate_caption_for_scene():
    """Generate a dense caption for the entire scene by rendering it and using BLIP"""
    try:
        import os
        import tempfile

        import bpy

        # Create a temporary file for the render
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            temp_path = tmp_file.name

        try:
            # Set up render settings for a quick preview
            scene = bpy.context.scene
            original_engine = scene.render.engine
            original_resolution_x = scene.render.resolution_x
            original_resolution_y = scene.render.resolution_y

            # Use Eevee for faster rendering
            scene.render.engine = "BLENDER_EEVEE"
            scene.render.resolution_x = 512
            scene.render.resolution_y = 512

            # Set output path
            scene.render.filepath = temp_path

            # Render the scene
            bpy.ops.render.render(write_still=True)

            # Restore original settings
            scene.render.engine = original_engine
            scene.render.resolution_x = original_resolution_x
            scene.render.resolution_y = original_resolution_y

            # Generate caption from the rendered image
            caption = generate_caption(temp_path)

            return caption

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        print(f"Error generating scene caption: {str(e)}")
        return None
