import os

import pytest

POSTGRES_URL = os.environ.get("STITCH_TEST_POSTGRES_URL")

if os.environ.get("STITCH_REQUIRE_POSTGRES_TESTS") and not POSTGRES_URL:
    raise RuntimeError(
        "STITCH_REQUIRE_POSTGRES_TESTS is set but STITCH_TEST_POSTGRES_URL is not: "
        "the Postgres tests would be skipped."
    )

requires_postgres = pytest.mark.skipif(
    not POSTGRES_URL, reason="set STITCH_TEST_POSTGRES_URL to run Postgres tests"
)
