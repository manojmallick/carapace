from carapace.hashing import content_hash, normalize_query, query_hash


def test_normalize_query_collapses_whitespace_and_case():
    assert normalize_query("  How  should\nI handle Errors?  ") == "how should i handle errors?"


def test_query_hash_is_stable_across_whitespace_and_case_variants():
    assert query_hash("How should I handle errors?") == query_hash(
        "  how   should i handle errors?  "
    )


def test_query_hash_differs_for_different_queries():
    assert query_hash("How should I handle errors?") != query_hash(
        "How should I paginate results?"
    )


def test_content_hash_changes_when_context_changes():
    # The whole point of the dual-hash design: a changed context must
    # invalidate a cache entry keyed on the old context's hash.
    h1 = content_hash("service: payments-api, uses ApiError")
    h2 = content_hash("service: payments-api, uses HttpError")
    assert h1 != h2


def test_content_hash_stable_for_identical_context():
    ctx = "service: payments-api, uses ApiError"
    assert content_hash(ctx) == content_hash(ctx)
