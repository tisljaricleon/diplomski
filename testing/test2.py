import asyncio
import io
import random
import time

import httpx
import torchvision
import torchvision.transforms as transforms
from PIL import Image

REQUESTS_PER_SECOND = 500
REQUEST_INTERVAL = 1.0 / REQUESTS_PER_SECOND
BATCH_SIZE = 1
MAX_IN_FLIGHT_REQUESTS = 1000
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=60.0)
HTTP_LIMITS = httpx.Limits(max_connections=2000, max_keepalive_connections=2000)

CLIENT_MAP = [
    {
        "name": "orinnano-2",
        "ip_address": "10.19.4.22",
        "port": 30380,
        "endpoint": "/predict",
    },
]

transform = transforms.Compose([
    transforms.ToPILImage(),
])
testset = torchvision.datasets.CIFAR10(root="./data", train=False, download=False)


def get_random_image():
    idx = random.randint(0, len(testset) - 1)
    img, label = testset[idx]
    if not isinstance(img, Image.Image):
        img = transform(img)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue(), label


def get_random_batch(batch_size):
    images = []
    labels = []
    for _ in range(batch_size):
        img_bytes, label = get_random_image()
        images.append((img_bytes, label))
        labels.append(label)
    return images, labels


async def send_single_request(client, request_idx, batch_size, client_session):
    url = f"http://{client['ip_address']}:{client['port']}{client['endpoint']}"
    images, labels = await asyncio.to_thread(get_random_batch, batch_size)
    start = time.time()

    try:
        files = [("files", (f"image_{i}.png", img_bytes, "image/png")) for i, (img_bytes, _) in enumerate(images)]
        response = await client_session.post(url, files=files)
        latency = time.time() - start
        print(
            f"[REQUEST {request_idx}] client={client['name']} status={response.status_code} "
            f"latency={latency:.3f}s labels={labels}"
        )
    except Exception as exc:
        latency = time.time() - start
        print(
            f"[REQUEST {request_idx}] client={client['name']} ERROR={type(exc).__name__}: {exc} "
            f"after {latency:.3f}s"
        )


async def run_forever(client_map):
    request_idx = 0
    pending = set()
    semaphore = asyncio.Semaphore(MAX_IN_FLIGHT_REQUESTS)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, limits=HTTP_LIMITS) as client_session:
        while True:
            loop_start = time.perf_counter()

            for client in client_map:
                await semaphore.acquire()

                async def _wrapped_send(target_client, target_request_idx):
                    try:
                        await send_single_request(target_client, target_request_idx, BATCH_SIZE, client_session)
                    finally:
                        semaphore.release()

                task = asyncio.create_task(_wrapped_send(client, request_idx + 1))
                pending.add(task)
                task.add_done_callback(pending.discard)
                request_idx += 1

                if request_idx % 25 == 0:
                    print(f"[INFO] queued {request_idx} requests; pending={len(pending)}")

            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0.0, REQUEST_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        asyncio.run(run_forever(CLIENT_MAP))
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
