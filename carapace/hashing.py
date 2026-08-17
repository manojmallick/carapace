"""Dual-key hashing for the hot tier.

The same pattern validated in production at ING: a cache entry is keyed
on BOTH the normalized query text and the content it was answered
against. If the underlying context changes, the content hash changes,
and the stale entry simply never matches again -- no invalidation job
required.
"""

import hashlib
import re


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def query_hash(query: str) -> str:
    return hashlib.sha256(normalize_query(query).encode()).hexdigest()


def content_hash(context: str) -> str:
    return hashlib.sha256(context.encode()).hexdigest()
