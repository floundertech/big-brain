# Holds the token-usage histogram created during _init_tracing().
# Using a shared module avoids circular imports between main.py and services/claude.py
# while also bypassing the global OTel metrics API (which Traceloop may override).
_token_usage_histogram = None


def set_token_usage_histogram(h) -> None:
    global _token_usage_histogram
    _token_usage_histogram = h


def get_token_usage_histogram():
    return _token_usage_histogram
