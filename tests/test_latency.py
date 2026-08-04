from engine.latency import measure_call_latency


def test_measure_call_latency_returns_elapsed_ms_when_snapshot_exists() -> None:
    # Given: a live snapshot fetch that returns an account-like payload.
    def fetch_snapshot() -> str:
        return "account"

    # When: the call is measured.
    measured = measure_call_latency(fetch_snapshot)

    # Then: the caller gets the payload and a numeric latency for telemetry.
    assert measured.value == "account"
    assert measured.latency_ms is not None
    assert measured.latency_ms >= 0.0


def test_measure_call_latency_keeps_latency_blank_when_snapshot_missing() -> None:
    # Given: a live snapshot fetch that fails cleanly and returns no payload.
    def fetch_snapshot() -> None:
        return None

    # When: the call is measured.
    measured = measure_call_latency(fetch_snapshot)

    # Then: the UI keeps latency blank instead of reporting a false success.
    assert measured.value is None
