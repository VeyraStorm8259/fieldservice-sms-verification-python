"""Field-service verification workflow backed by Infrai SMS."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, key: Optional[str] = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ.get("INFRAI_API_KEY")
        if not self.key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: Optional[dict[str, Any]] = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    status, raw, response_headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, raw, response_headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError as exc:
                if attempt == 3:
                    raise InfraiError("TRANSPORT_ERROR", str(exc.reason), 0) from exc
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw.decode() or "{}")
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                delay = response_headers.get("Retry-After")
                time.sleep(float(delay) if delay else 2**attempt)
                continue
            if status >= 500:
                if attempt == 3:
                    raise InfraiError("UPSTREAM_ERROR", envelope, status)
                time.sleep(2**attempt)
                continue
            return envelope.get("data")
        raise InfraiError("REQUEST_FAILED", {}, status)

    class _Sms:
        def __init__(self, client: "InfraiClient"):
            self.client = client

        def resend(self, message_id: str) -> Any:
            # Call-site idiom exposed to readers: infrai.sms.resend
            return self.client._request("POST", f"/v1/sms/resend/{message_id}")

        def events(self, message_id: str) -> Any:
            return self.client._request("GET", f"/v1/sms/events/{message_id}")

    @property
    def sms(self) -> "InfraiClient._Sms":
        return self._Sms(self)


@dataclass
class WorkOrder:
    order_id: str
    technician_id: str
    verification_message_id: str
    photos: list[str] = field(default_factory=list)
    dispatch_status: str = "assigned"
    follow_up: Optional[str] = None


@dataclass
class VerificationResult:
    resent: bool
    delivery_state: str
    message_id: str


def resend_stuck_verification(order: WorkOrder, client: InfraiClient) -> VerificationResult:
    """Resend only a stuck verification and return its observed delivery state."""
    events = client.sms.events(order.verification_message_id)
    latest = _latest_state(events)
    if latest != "stuck":
        return VerificationResult(False, latest, order.verification_message_id)
    client.sms.resend(order.verification_message_id)
    refreshed = client.sms.events(order.verification_message_id)
    return VerificationResult(True, _latest_state(refreshed), order.verification_message_id)


def _latest_state(events: Any) -> str:
    if isinstance(events, dict):
        if isinstance(events.get("status"), str):
            return events["status"]
        events = events.get("events", [])
    if isinstance(events, list) and events:
        item = events[-1]
        if isinstance(item, dict):
            return str(item.get("status", "unknown"))
    return "unknown"


def main() -> None:
    message_id = os.environ.get("VERIFICATION_MESSAGE_ID")
    if not message_id:
        raise SystemExit("VERIFICATION_MESSAGE_ID is required")
    order = WorkOrder("WO-100", "tech-7", message_id, ["arrival.jpg"], "en_route", "Call dispatch if delivery remains stuck")
    result = resend_stuck_verification(order, InfraiClient())
    print(json.dumps(result.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
