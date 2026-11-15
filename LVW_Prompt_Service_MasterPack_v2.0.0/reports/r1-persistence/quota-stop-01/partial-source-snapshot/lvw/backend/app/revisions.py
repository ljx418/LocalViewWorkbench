"""The canonical content hash and the immutable revision operations.

This module owns ONE content hash for a canonical PromptSpec and ONE
edit token for a shot.  The implementation and the migration of the
same canonical rule may never grow a second, near approximate
algorithm: the hash of a revision and the hash of the draft of a shot
are both computed here and nowhere else.

The content hash of a specification is the SHA256 of the UTF-8
serialisation of the COMPLETE canonical PromptSpec with sorted keys,
compact separators, ensure_ascii False and allow_nan False.  The random
identifiers, the author and the timestamps are not part of the
specification and they are not part of the hash.

The edit token of a shot is the quoted strong ETag of the committed
state of that shot: the same committed state returns the same token
after a restart and every successful change of the draft or of the head
produces a new one.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import PromptSpec

# The canonical serialisation of every hash of this workpack.
CANONICAL_JSON = {"sort_keys": True, "separators": (",", ":"),
                  "ensure_ascii": False, "allow_nan": False}


def canonical_json(value: Any) -> str:
    """The canonical JSON text of a value."""
    return json.dumps(value, **CANONICAL_JSON)


def canonical_sha256(value: Any) -> str:
    """The SHA256 of the canonical JSON text of a value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def spec_content_sha256(spec: PromptSpec) -> str:
    """The content hash of a complete canonical PromptSpec."""
    return canonical_sha256(spec.model_dump(mode="json"))


def shot_state_sha256(*, title: str, media_ref_id: str | None, spec_sha256: str,
                       head_revision_id: str | None) -> str:
    """The hash of the committed state of a shot.

    The state is the title, the media association, the hash of the
    working draft and the head revision.  A change of the draft or a
    change of the head changes the state and therefore the token, and
    the same committed state always hashes to the same value.
    """
    return canonical_sha256({
        "title": title,
        "media_ref_id": media_ref_id,
        "spec_sha256": spec_sha256,
        "head_revision_id": head_revision_id,
    })


def shot_etag(state_sha256: str) -> str:
    """The quoted strong edit token of a shot."""
    return '"shot:%s"' % state_sha256


def revision_etag(revision_id: str, content_sha256: str) -> str:
    """The quoted strong token of one immutable revision."""
    return '"revision:%s:%s"' % (revision_id, content_sha256)
