"""Measure one visitor's real Jev usage for one game minute at 1x speed."""

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
import time
from typing import Any, Mapping

from dotenv import dotenv_values
import httpx

from tavern.server.runtime import TavernRuntime
import tavern.adapters.jev as jev


async def measure(root: Path, actor_id: str, seconds: int,
                  input_price_per_million: float) -> dict[str, Any]:
    """Run normal world/policy code and meter provider-reported token counts.

    Args:
        root: Repository containing the map and server-only dotenv file.
        actor_id: Initial visitor to retain in this isolated simulation.
        seconds: Simulated seconds, advanced at approximately real-time speed.
        input_price_per_million: Published USD input-token tariff.
    Returns:
        Request, token, action, latency, and calculated API-cost measurements.
    Raises:
        ValueError: Credentials or the selected visitor are missing.
    """
    values = dotenv_values(root / ".env")
    if not values.get("TYPESAFE_API_KEY"):
        raise ValueError("Set TYPESAFE_API_KEY in .env before measuring real AI usage")
    layout = json.loads((root / "data" / "tavern.json").read_text())
    layout["actors"] = [actor for actor in layout["actors"] if actor["id"] == actor_id]
    if len(layout["actors"]) != 1:
        raise ValueError("Choose an existing visitor")
    config = {"typesafe_api_key": values["TYPESAFE_API_KEY"],
              "model": values.get("TYPESAFE_MODEL", "jev-latest"),
              "timeout": float(values.get("AI_TIMEOUT", "8")),
              "temperature": float(values.get("AI_TEMPERATURE", "0.25"))}
    runtime = TavernRuntime(layout, root / "saves" / "unused-benchmark.json", config)
    requests: list[dict[str, Any]] = []
    models: set[str] = set()
    original_post = jev._post_scores

    async def metered_post(client: httpx.AsyncClient, body: Mapping[str, Any],
                           key: str, timeout: float) -> Any:
        row = {"simulation_time": round(runtime.world["time"], 2), "success": False}
        requests.append(row)
        started = time.monotonic()
        try:
            payload = await original_post(client, body, key, timeout)
            usage = payload.get("usage", {})
            row.update(success=True, input_tokens=usage.get("input_tokens"),
                       output_tokens=usage.get("output_tokens"))
            models.add(payload.get("model", config["model"]))
            return payload
        finally:
            row["latency_ms"] = round((time.monotonic() - started) * 1000, 1)

    jev._post_scores = metered_post
    started = time.monotonic()
    try:
        for _ in range(seconds * 10):
            runtime.advance(0.1)
            await asyncio.sleep(0.1)
        runtime.world["paused"] = True
        tasks = [task for task, _revision in runtime.pending.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return summarize(runtime, requests, models, seconds,
                         time.monotonic() - started, input_price_per_million)
    finally:
        jev._post_scores = original_post
        await runtime.close()


def summarize(runtime: TavernRuntime, requests: list[dict[str, Any]], models: set[str],
              seconds: int, wall_seconds: float, input_price: float) -> dict[str, Any]:
    """Calculate tariff cost from actual completed-response usage counters.

    Args:
        runtime: Isolated simulation used for the measurement.
        requests: Metered requests started during the observation window.
        models: Model versions reported by the provider.
        seconds: Length of the simulated observation window.
        wall_seconds: Elapsed real time, including pending-request completion.
        input_price: USD tariff per million input tokens; output is free.
    Returns:
        JSON-compatible measurements and an explicitly calculated cost estimate.
    """
    input_tokens = sum(row.get("input_tokens") or 0 for row in requests)
    output_tokens = sum(row.get("output_tokens") or 0 for row in requests)
    completed = Counter(event["message"].split("completed ", 1)[1]
                        for event in runtime.world["events"] if event["type"] == "action_completed")
    return {"actor": runtime.world["actors"][0]["id"], "game_seconds": seconds,
            "wall_seconds": round(wall_seconds, 2), "models": sorted(models),
            "requests": len(requests), "failed_requests": sum(not row["success"] for row in requests),
            "missing_usage": sum(row.get("input_tokens") is None for row in requests),
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "input_usd_per_million": input_price, "output_usd_per_million": 0,
            "estimated_api_cost_usd": input_tokens / 1_000_000 * input_price,
            "completed_actions": dict(completed), "request_details": requests}


def main(root: Path) -> None:
    """Read benchmark options, run the real simulation, and print safe measurements.

    Args:
        root: Repository directory.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", default="edda")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--input-price", type=float, default=0.042,
                        help="USD per million input tokens; verified 2026-10-01")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seconds <= 0 or args.input_price < 0:
        parser.error("seconds must be positive and price must be nonnegative")
    result = asyncio.run(measure(root, args.actor, args.seconds, args.input_price))
    encoded = json.dumps(result, indent=2)
    if args.output is not None:
        args.output.write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
