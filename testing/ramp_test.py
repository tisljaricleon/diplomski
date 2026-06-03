"""
ramp_test.py — Ramp up req/s to find the breaking point on a single client.

Usage:
    python ramp_test.py --ip 10.19.4.22 --port 30380

Each step runs for STEP_DURATION seconds at a fixed rate, then prints a
latency/error summary. Watch for where p95 latency spikes or error rate rises.
That rate is your inflight threshold candidate.
"""

import asyncio
import time
import io
import random
import argparse
import httpx
import torchvision
from PIL import Image

# ── tune these ────────────────────────────────────────────────────────────────
STEP_DURATION = 15          # seconds per rate step
RATES = [150, 175, 200, 250, 300, 400, 500, 600, 750, 1000]  # req/s to test (per-client load_rate overrides this)
# ──────────────────────────────────────────────────────────────────────────────

testset = torchvision.datasets.CIFAR10(root="./data", train=False, download=False)


def get_image_bytes():
    idx = random.randint(0, len(testset) - 1)
    img, _ = testset[idx]
    if not isinstance(img, Image.Image):
        img = torchvision.transforms.ToPILImage()(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def fire(session: httpx.AsyncClient, url: str, results: list):
    img = await asyncio.to_thread(get_image_bytes)
    start = time.time()
    try:
        resp = await session.post(url, files=[("files", ("img.png", img, "image/png"))])
        latency = time.time() - start
        results.append((latency, resp.status_code, None))
    except Exception as e:
        latency = time.time() - start
        results.append((latency, -1, type(e).__name__))


async def run_step(session: httpx.AsyncClient, url: str, rate: int, duration: int) -> list:
    results = []
    interval = 1.0 / rate
    deadline = time.time() + duration
    while time.time() < deadline:
        asyncio.create_task(fire(session, url, results))
        await asyncio.sleep(interval)
    # wait a moment for in-flight requests to land
    await asyncio.sleep(2)
    return results


def summarise(rate: int, results: list):
    if not results:
        print(f"  rate={rate:>4} req/s  NO RESULTS")
        return

    latencies   = [r[0] for r in results if r[1] != -1]
    errors      = [r for r in results if r[1] == -1 or r[1] >= 500]
    timeouts    = [r for r in results if r[2] and "Timeout" in r[2]]
    total       = len(results)
    err_rate    = len(errors) / total * 100

    if latencies:
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = sum(latencies) / len(latencies)
    else:
        p50 = p95 = p99 = avg = float("nan")

    flag = ""
    if err_rate > 5:
        flag = "  ⚠  ERROR RATE HIGH"
    if p95 > 2.0:
        flag = "  ⚠  LATENCY SPIKE"
    if err_rate > 20 or p95 > 5.0:
        flag = "  ✖  BREAKING POINT"

    print(
        f"  rate={rate:>4} req/s | "
        f"total={total:>5} | "
        f"errors={len(errors):>4} ({err_rate:4.1f}%) | "
        f"timeouts={len(timeouts):>3} | "
        f"avg={avg:.3f}s  p50={p50:.3f}s  p95={p95:.3f}s  p99={p99:.3f}s"
        f"{flag}"
    )


async def main(ip: str, port: int):
    url = f"http://{ip}:{port}/predict"
    print(f"\nTarget: {url}")
    print(f"Steps:  {RATES}  ({STEP_DURATION}s each)\n")

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as session:
        # warmup
        print("Warmup (5 req)...")
        warmup = []
        for _ in range(5):
            await fire(session, url, warmup)
        print("Warmup done.\n")
        print(f"{'─'*100}")

        for rate in RATES:
            print(f"→ Starting {rate} req/s for {STEP_DURATION}s ...")
            results = await run_step(session, url, rate, STEP_DURATION)
            summarise(rate, results)
            await asyncio.sleep(3)   # brief pause between steps

    print(f"{'─'*100}")
    print("\nDone. Pick your inflight threshold just BELOW the rate where p95 spikes or errors appear.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip",   required=True, help="Node IP, e.g. 10.19.4.22")
    parser.add_argument("--port", type=int, default=30380, help="NodePort for inf-proxy")
    args = parser.parse_args()
    asyncio.run(main(args.ip, args.port))
