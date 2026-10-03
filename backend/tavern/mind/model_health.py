"""Whether Jev and Claude can be used: failures classified, a window of recent calls, and the words for a banner."""

from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypedDict

SERVICES = ("jev", "claude")
# What a service can be: not heard from yet, working, without a key, refusing the key, out of credit,
# not answering, or answering badly too often.
STATUSES = ("checking", "ok", "no_key", "auth", "no_credit", "unreachable", "degraded")
# These end a live run before it starts: no call could succeed, however often it is retried.
UNUSABLE = ("no_key", "auth", "no_credit")
# A window of the latest calls decides: a service is degraded once this share of them failed.
WINDOW, FAILING_SHARE = 10, 0.5


class Health(TypedDict):
    """How one service is doing: its status and, for a failure, why."""

    status: str
    reason: str


def classify(error: BaseException) -> str:
    """Tell what a failed call says about the service.

    Args:
        error: The adapter's error; its `status` is an HTTP status when there was one.

    Returns:
        `auth` for 401 and 403, `no_credit` for 402, `unreachable` for a timeout, a failed connection
        or a 5xx, otherwise `degraded` (rate limits, bad answers, anything unforeseen).
    """
    status = getattr(error, "status", None)
    text = str(error).lower()
    if status in (401, 403):
        return "auth"
    if status == 402:
        return "no_credit"
    if "timed out" in text or "connection failed" in text or (isinstance(status, int) and status >= 500):
        return "unreachable"
    return "degraded"


def judge(recent: Sequence[str | None]) -> Health:
    """Say how a service is doing from its latest calls.

    Args:
        recent: Oldest first: None for a call that worked, else the status its failure was classified
            as. Only the latest `WINDOW` count.

    Returns:
        `checking` with no calls. A last call that failed with `auth`, `no_credit` or `unreachable`
        sets that status at once; one that worked means `ok`, unless half of the window failed in
        lesser ways (rate limits, bad answers), which is `degraded`.
    """
    window = list(recent)[-WINDOW:]
    if not window:
        return {"status": "checking", "reason": "Not asked yet"}
    last = window[-1]
    if last in ("auth", "no_credit", "unreachable"):
        return {"status": last, "reason": ""}
    # Earlier failures that retrying cured (`auth`, `no_credit`, `unreachable`) do not count against it.
    failed = sum(item == "degraded" for item in window)
    if failed / len(window) >= FAILING_SHARE:
        return {"status": "degraded", "reason": f"{failed} of the last {len(window)} calls failed"}
    return {"status": "ok", "reason": ""}


class HealthBoard:
    """The health of each service, kept from the calls made to it and from probes."""

    def __init__(self, keyed: Mapping[str, bool]) -> None:
        """Create a board.

        Args:
            keyed: Per service in `SERVICES`, whether its key reached the environment. One without
                stays `no_key` whatever is recorded.
        """
        self._keyed = dict(keyed)
        self._recent: dict[str, deque[str | None]] = {name: deque(maxlen=WINDOW) for name in SERVICES}
        self._last_error: dict[str, str] = {}

    def record(self, service: str, error: BaseException | None) -> None:
        """Note how a call to a service went.

        Args:
            service: One of `SERVICES`.
            error: What the call raised, or None when it worked.
        """
        self._recent[service].append(None if error is None else classify(error))
        if error is not None:
            self._last_error[service] = str(error)

    async def probe(self, service: str, call: Callable[[], Awaitable[object]]) -> Health:
        """Make one cheap call to a service and record how it went.

        Args:
            service: One of `SERVICES`.
            call: The smallest request that proves the key, the credit and the connection; raises the
                adapter's recoverable error on failure. It is not made for a service without a key.

        Returns:
            The service's health afterwards.

        Raises:
            ValueError: `call` fails with something else than a recoverable adapter error.
        """
        if self._keyed[service]:
            try:
                await call()
            except (RuntimeError, ValueError) as error:  # JevError and ClaudeError are RuntimeErrors.
                self.record(service, error)
            else:
                self.record(service, None)
        return self.snapshot()[service]

    def snapshot(self) -> dict[str, Health]:
        """Report every service.

        Returns:
            Status and reason per service; a failure's reason is the adapter's own message.
        """
        report: dict[str, Health] = {}
        for name in SERVICES:
            if not self._keyed[name]:
                report[name] = {"status": "no_key", "reason": "No key in the environment"}
                continue
            health = judge(list(self._recent[name]))
            if health["status"] not in ("ok", "checking") and not health["reason"]:
                health["reason"] = self._last_error.get(name, "")
            report[name] = health
        return report


def banner(health: Mapping[str, Health], used: Sequence[str]) -> str:
    """Write the one-line health banner of a run.

    Args:
        health: Status per service (`HealthBoard.snapshot`).
        used: Services this run asks; the others show as OFF.

    Returns:
        Like `JEV: OK  CLAUDE: NO CREDIT`.
    """
    parts = [f"{name.upper()}: {health[name]['status'].upper().replace('_', ' ') if name in used else 'OFF'}"
             for name in SERVICES]
    return "  ".join(parts)


def blocking(health: Mapping[str, Health], used: Sequence[str]) -> list[str]:
    """List the services in use that no retry can bring back.

    Args:
        health: Status per service.
        used: Services this run asks.

    Returns:
        Those without a key, with a refused key or without credit, in `SERVICES` order.
    """
    return [name for name in SERVICES if name in used and health[name]["status"] in UNUSABLE]
