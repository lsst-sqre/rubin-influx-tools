"""Test int -> duration_literal conversion."""

from rubin_influx_tools.influxfns import seconds_to_duration_literal as sl


def test_duration_literal() -> None:
    assert sl(0) == "infinite"
    assert sl(1) == "1s"
    assert sl(10) == "10s"
    assert sl(100) == "1m40s"
    assert sl(1000) == "16m40s"
    assert sl(10000) == "2h46m40s"
    assert sl(100000) == "1d3h46m40s"
    assert sl(1000000) == "1w4d13h46m40s"
    assert sl(10000000) == "16w3d17h46m40s"
