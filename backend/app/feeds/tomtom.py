"""Live TomTom Traffic Flow feed → observed leg travel times.

This is the only real-world input VA-QPSO's adaptive β consumes. It queries
TomTom's Flow Segment Data API at a deterministic probe point per route leg,
reads the *current* travel time against TomTom's free-flow travel time for the
same segment, and scales the graph's baseline leg time by that ratio:

    observed_w(leg) = baseline_leg_s * (currentTravelTime / freeFlowTravelTime)

Every observation is timestamped and counted. Nothing here fabricates a
reading: an unreachable API, a missing key, or a segment TomTom has no data
for is reported as a failed probe, and an all-failed call returns ``None`` so
the caller leaves the volatility window untouched.

Probe points are deterministic per leg (rounded coordinates), so two
observations of the same leg differ only because traffic moved, not because
the probe moved. Readings are cached for a short TTL so repeated solves in a
row do not burn API quota — inside that window the speeds are genuinely the
same values, which is what the volatility window should see.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.logging import get_logger

logger = get_logger("marga.feeds.tomtom")

_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative/11/json"
_DEFAULT_TIMEOUT_S = 4.0
#: Minimum spacing between outbound calls (free tier is 5 requests/second).
_MIN_INTERVAL_S = 0.21


@dataclass(frozen=True)
class FlowReading:
    """One TomTom flow reading for the road segment nearest a probe point."""

    current_kmh: float
    free_flow_kmh: float
    current_s: float
    free_flow_s: float
    confidence: float
    road_closure: bool

    @property
    def delay_ratio(self) -> float:
        """Observed travel time relative to free flow. 1.0 = running free."""
        if self.free_flow_s <= 0.0:
            return 1.0
        return self.current_s / self.free_flow_s


@dataclass
class TrafficObservation:
    """A batch of probe readings plus the leg weights derived from them."""

    source: str
    observed_at: str
    probes: int = 0
    failed: int = 0
    legs: Dict[str, float] = field(default_factory=dict)
    readings: List[Dict[str, float]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.probes > 0

    @property
    def mean_current_kmh(self) -> float:
        return (
            sum(r["current_kmh"] for r in self.readings) / len(self.readings)
            if self.readings
            else 0.0
        )

    @property
    def mean_free_flow_kmh(self) -> float:
        return (
            sum(r["free_flow_kmh"] for r in self.readings) / len(self.readings)
            if self.readings
            else 0.0
        )


class TomTomFlow:
    """Synchronous client for TomTom's Flow Segment Data endpoint.

    Parameters
    ----------
    api_key:
        TomTom key. Empty string means the feed is unconfigured and every
        call returns ``None`` — no silent fallback to synthetic speeds.
    max_legs:
        Upper bound on probes per observation batch, to keep latency and API
        quota bounded during a live demo.
    cache_ttl_s:
        How long an individual probe reading is reused. ``0`` disables caching.
    """

    def __init__(
        self,
        api_key: str = "",
        *,
        max_legs: int = 10,
        cache_ttl_s: float = 15.0,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._max_legs = max(1, max_legs)
        self._cache_ttl_s = max(0.0, cache_ttl_s)
        self._timeout_s = timeout_s
        self._client = client
        self._cache: Dict[Tuple[float, float], Tuple[float, FlowReading]] = {}
        self._last_call = 0.0

    # -- configuration --------------------------------------------------------

    @property
    def configured(self) -> bool:
        """True when a key is present; the API is still allowed to fail."""
        return bool(self._api_key)

    # -- probing --------------------------------------------------------------

    def read(self, lng: float, lat: float) -> Optional[FlowReading]:
        """Read current vs free-flow speeds for the segment nearest a point.

        Returns ``None`` on any failure (bad key, timeout, no segment data);
        failures are logged at debug level, never raised, so a traffic outage
        cannot take down an optimization run.
        """
        cache_key = (round(lat, 5), round(lng, 5))
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached is not None and now - cached[0] < self._cache_ttl_s:
            return cached[1]

        if not self.configured:
            return None

        wait = _MIN_INTERVAL_S - (now - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

        params = {
            "key": self._api_key,
            "point": f"{lat:.6f},{lng:.6f}",
            "unit": "KMPH",
        }
        try:
            response = self._get_client().get(_FLOW_URL, params=params)
            response.raise_for_status()
            payload = response.json().get("flowSegmentData") or {}
            current_s = float(payload["currentTravelTime"])
            free_s = float(payload["freeFlowTravelTime"])
            if free_s <= 0 or current_s < 0:
                raise ValueError("non-positive travel time in payload")
            reading = FlowReading(
                current_kmh=float(payload["currentSpeed"]),
                free_flow_kmh=float(payload["freeFlowSpeed"]),
                current_s=current_s,
                free_flow_s=free_s,
                confidence=float(payload.get("confidence", 0.0)),
                road_closure=bool(payload.get("roadClosure", False)),
            )
        except Exception as exc:  # noqa: BLE001 - feed must never raise
            logger.debug("TomTom probe failed at %.4f,%.4f: %s", lng, lat, exc)
            return None

        if self._cache_ttl_s > 0:
            self._cache[cache_key] = (time.monotonic(), reading)
        return reading

    def observe_legs(
        self,
        probes: Dict[str, Tuple[float, float]],
        baseline_s: Dict[str, float],
    ) -> Optional[TrafficObservation]:
        """Observe a batch of route legs.

        ``probes`` maps a caller's leg id (the solver's ``"u-v"`` stop-pair
        name) to the ``(lng, lat)`` point at which to read that leg, and
        ``baseline_s`` maps the same ids to the graph's uncongested leg time.

        Returns ``None`` when nothing could be read, so the caller can leave
        the rolling window untouched rather than recording zeros.
        """
        observation = TrafficObservation(
            source="tomtom",
            observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        for leg_id, (lng, lat) in list(probes.items())[: self._max_legs]:
            baseline = baseline_s.get(leg_id)
            if baseline is None or baseline <= 0:
                continue
            reading = self.read(lng, lat)
            if reading is None:
                observation.failed += 1
                continue
            observation.probes += 1
            observation.legs[leg_id] = round(baseline * reading.delay_ratio, 3)
            observation.readings.append(
                {
                    "leg": leg_id,
                    "lng": round(lng, 6),
                    "lat": round(lat, 6),
                    "current_kmh": reading.current_kmh,
                    "free_flow_kmh": reading.free_flow_kmh,
                    "delay_ratio": round(reading.delay_ratio, 4),
                    "confidence": reading.confidence,
                    "road_closure": reading.road_closure,
                }
            )
        if not observation.ok:
            return None
        return observation

    @property
    def max_legs(self) -> int:
        """Upper bound on probes per batch (bounds quota and latency)."""
        return self._max_legs

    def snapshot(self, points: List[Tuple[float, float]]) -> Optional[TrafficObservation]:
        """Read a spread of points (used by the UI's live traffic strip)."""
        observation = TrafficObservation(
            source="tomtom",
            observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        for lng, lat in points[: self._max_legs]:
            reading = self.read(lng, lat)
            if reading is None:
                observation.failed += 1
                continue
            observation.probes += 1
            observation.readings.append(
                {
                    "lng": round(lng, 6),
                    "lat": round(lat, 6),
                    "current_kmh": reading.current_kmh,
                    "free_flow_kmh": reading.free_flow_kmh,
                    "delay_ratio": round(reading.delay_ratio, 4),
                    "confidence": reading.confidence,
                    "road_closure": reading.road_closure,
                }
            )
        if not observation.ok:
            return None
        return observation

    # -- internals ------------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout_s)
        return self._client
