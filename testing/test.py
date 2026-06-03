import asyncio
import csv
import time
import io
import random
import argparse
import httpx
import torchvision
import torchvision.transforms as transforms
import datetime
from PIL import Image

SEND_WINDOW_SECONDS = 15
PAUSE_WINDOW_SECONDS = 5

CLIENT_MAP = [
    {
        "name": "orinnano-2",
        "ip_address": "10.19.4.22",
        "port": 30380,          
        "endpoint": "/predict",
        "metrics_port": 30383,  
        "load_rate": 200,      
    },
    {
        "name": "orinnano-3",
        "ip_address": "10.19.4.23",
        "port": 30381,         
        "endpoint": "/predict",
        "metrics_port": 30384,
        "load_rate": 100,
    },
    {
        "name": "orinnano-4",
        "ip_address": "10.19.4.24",
        "port": 30382,         
        "endpoint": "/predict",
        "metrics_port": 30385,
        "load_rate": 100,
    },
]

transform = transforms.Compose([
    transforms.ToPILImage()
])
testset = torchvision.datasets.CIFAR10(root="./data", train=False, download=False)


def _format_exception_chain(exc: Exception) -> str:
    parts = []
    seen = set()
    cur = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        parts.append(f"{type(cur).__name__}: {cur}")
        cur = cur.__cause__ or cur.__context__
    return " | caused_by: ".join(parts)


def get_random_image():
    idx = random.randint(0, len(testset) - 1)
    img, label = testset[idx]
    if not isinstance(img, Image.Image):
        img = transform(img)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_bytes = buffer.getvalue()
    return img_bytes, label


def get_random_batch(batch_size):
    images = []
    labels = []
    for _ in range(batch_size):
        img_bytes, label = get_random_image()
        images.append((img_bytes, label))
        labels.append(label)
    return images, labels


async def poll_proxy_metrics(
    client_session: httpx.AsyncClient,
    client: dict,
    stop_event: asyncio.Event,
    metrics_rows: list,
    interval_s: float = 1.0,
):
    metrics_port = client.get("metrics_port")
    if not metrics_port:
        return

    base_url = f"http://{client['ip_address']}:{metrics_port}"
    proxy_url = f"{base_url}/proxyMetrics"

    while not stop_event.is_set():
        row = {
            "timestamp": int(time.time() * 1000),
            "client_name": client["name"],
            "proxy_url": proxy_url,
            "proxy_status": None,
            "proxy_error": "",
            "inflight_60s_avg": None,
            "inflight_requests": None,
            "inflight_60s_max": None,
        }

        try:
            resp = await client_session.get(proxy_url, timeout=2.0)
            row["proxy_status"] = resp.status_code
            data = resp.json().get("data", {})
            row["inflight_60s_avg"] = data.get("inflight_60s_avg")
            row["inflight_requests"] = data.get("inflight_requests")
            row["inflight_60s_max"] = data.get("inflight_60s_max")
        except Exception as e:
            row["proxy_error"] = _format_exception_chain(e)

        metrics_rows.append(row)
        await asyncio.sleep(interval_s)


async def send_single_request(client, results, request_idx, batch_size, rate, client_session):
    url = f"http://{client['ip_address']}:{client['port']}{client['endpoint']}"
    images, labels = await asyncio.to_thread(get_random_batch, batch_size)
    start = time.time()
    timestamp = int(time.time() * 1000)

    try:
        files = [("files", (f"image_{i}.png", img_bytes, "image/png")) for i, (img_bytes, _) in enumerate(images)]
        response = await client_session.post(url, files=files)
        latency = time.time() - start
        error_msg = ''
        received_indices = []
        received_names = []
        received_confidences = []
        received = []
        try:
            resp_json = response.json()
            received = resp_json.get("results", [])
            if response.status_code != 200:
                error_msg = resp_json.get("error")
        except Exception:
            if response.status_code != 200:
                error_msg = str(response.status_code)
                
        correct = 0
        for i, r in enumerate(received):
            idx = r.get("label_index", -1)
            name = r.get("label_name", "")
            conf = r.get("confidence", None)
            received_indices.append(idx)
            received_names.append(name)
            received_confidences.append(conf)
            if i < len(labels) and idx == labels[i]:
                correct += 1
        batch_acc = correct / len(labels) if labels else None

        results.append({
            'timestamp': timestamp,
            'client_name': client['name'],
            'rate': rate,
            'request_idx': request_idx+1,
            'batch_size': batch_size,
            'correct_labels': labels,
            'received_label_indexes': received_indices,
            'received_label_names': received_names,
            'received_confidences': received_confidences,
            'latency': latency,
            'status': response.status_code,
            'batch_accuracy': batch_acc,
            'error': error_msg,
        })
    except Exception as e:
        error_msg = _format_exception_chain(e)
        print(f"[ERROR] {error_msg}")
        results.append({
            'timestamp': timestamp,
            'client_name': client['name'],
            'rate': rate,
            'request_idx': request_idx+1,
            'batch_size': batch_size,
            'correct_labels': labels,
            'received_label_indexes': [],
            'received_label_names': [],
            'received_confidences': [],
            'latency': -1,
            'status': -1,
            'batch_accuracy': None,
            'error': error_msg,
        })


async def run_continuous_load(client_map, scenario: str):
    results = []
    metrics_rows = []
    request_idx = 0
    stop_event = asyncio.Event()
    metrics_tasks = []
    pending_request_tasks = set()

    try:
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=100, keepalive_expiry=30)
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), trust_env=False, limits=limits) as client_session:
            metrics_tasks = [
                asyncio.create_task(poll_proxy_metrics(client_session, client, stop_event, metrics_rows))
                for client in client_map
            ]

            print("[WARMUP] Sending 10 warmup requests...")
            warmup_tasks = []
            for i in range(10):
                for client in client_map:
                    warmup_tasks.append(asyncio.create_task(send_single_request(client, [], i, 1, 0, client_session)))
            await asyncio.gather(*warmup_tasks, return_exceptions=True)
            print("[WARMUP] Done. Starting continuous load...")
            await asyncio.sleep(2)

            client_rates = [(c, c.get("load_rate", 1)) for c in client_map]
            rate_desc = ", ".join(f"{c['name']}={r}" for c, r in client_rates)
            print(f"[CONTINUOUS] rates: {rate_desc} | on={SEND_WINDOW_SECONDS}s off={PAUSE_WINDOW_SECONDS}s (Ctrl+C to stop)")

            # Semaphores cap concurrent open sockets per client to avoid port exhaustion
            client_semaphores = {c["name"]: asyncio.Semaphore(50) for c in client_map}

            send_phase_event = asyncio.Event()

            async def _phase_controller():
                cycle_idx = 1
                while True:
                    print(f"[PHASE] cycle={cycle_idx} sending for {SEND_WINDOW_SECONDS}s")
                    send_phase_event.set()
                    await asyncio.sleep(SEND_WINDOW_SECONDS)

                    print(f"[PHASE] cycle={cycle_idx} pausing for {PAUSE_WINDOW_SECONDS}s")
                    send_phase_event.clear()
                    await asyncio.sleep(PAUSE_WINDOW_SECONDS)
                    cycle_idx += 1

            async def _send_for_client(client, effective_rate):
                nonlocal request_idx
                interval = 1.0 / effective_rate if effective_rate > 0 else 1.0
                batch_size = int(client.get("batch_size", 1))
                sem = client_semaphores[client["name"]]
                while True:
                    await send_phase_event.wait()
                    await sem.acquire()
                    async def _guarded(c, ri, bs, er):
                        try:
                            await send_single_request(c, results, ri, bs, er, client_session)
                        finally:
                            sem.release()
                    task = asyncio.create_task(_guarded(client, request_idx, batch_size, effective_rate))
                    pending_request_tasks.add(task)
                    task.add_done_callback(pending_request_tasks.discard)
                    request_idx += 1
                    await asyncio.sleep(interval)

            await asyncio.gather(
                _phase_controller(),
                *[
                    _send_for_client(client, effective_rate)
                    for client, effective_rate in client_rates
                ],
            )
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("[INTERRUPTED] Stopping early and writing partial CSV outputs...")
    finally:
        stop_event.set()
        for t in metrics_tasks:
            t.cancel()
        if pending_request_tasks:
            try:
                await asyncio.wait(pending_request_tasks, timeout=2.0)
            except Exception:
                pass

    _ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = f'request_data_{scenario}_{_ts}.csv'
    with open(out_file, 'w', newline='') as file:
        fieldnames = [
            'timestamp', 'client_name', 'rate', 'request_idx', 'batch_size',
            'correct_labels', 'received_label_indexes', 'received_label_names', 'received_confidences',
            'latency', 'status', 'batch_accuracy', 'error'
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"[DONE] Results written to {out_file}")

    metrics_out_file = f'runtime_metrics_{scenario}_{_ts}.csv'
    with open(metrics_out_file, 'w', newline='') as file:
        fieldnames = [
            'timestamp', 'client_name',
            'proxy_url',
            'inflight_60s_avg', 'inflight_requests', 'inflight_60s_max',
            'proxy_status', 'proxy_error'
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in metrics_rows:
            writer.writerow(row)
    print(f"[DONE] Runtime metrics written to {metrics_out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        type=str,
        default="default",
        help="Scenario name used for output CSV filename, e.g. no_proxy, with_proxy, baseline"
    )
    args = parser.parse_args()
    try:
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_continuous_load(CLIENT_MAP, scenario=args.scenario))
    except KeyboardInterrupt:
        print("[INTERRUPTED] Exiting.")
