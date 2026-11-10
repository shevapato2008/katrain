"""Document IDs and compact envelopes shared by the ES reader and writers."""

import base64
import hashlib

from katrain.web.kifu.identity import normalize_alias

SCHEMA_VERSION = "kifu-search-v1"
NAME_LANGUAGES = ("cn", "tw", "en", "jp", "ko")
SYNC_STATE_DOCUMENT_ID = "sync-state"


def album_document_id(album_id):
    return f"album:{int(album_id)}"


def _encoded(namespace, value):
    raw = value.encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    key = f"term:{namespace}:{encoded}"
    # ES limits IDs to 512 bytes. Digest the exact same bytes for rare long
    # labels; neither route performs width folding or casefold equivalence.
    return key if len(key) <= 512 else f"term:{namespace}h:{hashlib.sha256(raw).hexdigest()}"


def term_document_id(query):
    """Preserve the SQL exact/lower branch; width/casefold are not equivalence."""
    return _encoded("e", query.lower())


def alias_document_id(query):
    """Legacy aliases have their own explicitly normalized lookup namespace."""
    return _encoded("a", normalize_alias(query))


def public_player_document_id(player_id):
    return f"public-player:{int(player_id)}"


def document(document_id, source):
    return {"_id": document_id, "_source": source}
