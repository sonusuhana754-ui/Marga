"""Live data feeds consumed by the optimizer.

Only real, third-party data lives here. There is deliberately no synthetic
fallback: if a feed is unconfigured or unreachable the caller reports the gap
(``volatility_signal: false``) rather than inventing observations.
"""

from app.feeds.tomtom import TomTomFlow, TrafficObservation

__all__ = ["TomTomFlow", "TrafficObservation"]
