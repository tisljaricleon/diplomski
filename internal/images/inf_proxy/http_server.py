import logging
import json
import urllib.request
import threading
import time
from threading import Lock
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


try:
    from jtop import jtop
    JTOP_AVAILABLE = True
except ImportError:
    JTOP_AVAILABLE = False
    logging.warning("[JTOP] Jtop not available")


training_lock = Lock()
training_metrics: dict = {
    "is_training":               None,
    "loss":                      None,
    "accuracy":                  None,
}


app = FastAPI()


def _emit_proxy_log(level: str, message: str):
    print(message, flush=True)
    if level == "warning":
        logging.warning(message)
    else:
        logging.info(message)

def _proxy_metrics_logger():
    _emit_proxy_log("info", "[proxy/status] periodic logger thread started")
    while True:
        try:
            req = urllib.request.Request("http://127.0.0.1:80/proxy/status")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read())
            _emit_proxy_log(
                "info",
                f"[proxy/status] inflight={data.get('inflight_requests')} "
                f"avg60s={data.get('inflight_60s_avg')} "
                f"max60s={data.get('inflight_60s_max')}"
            )
        except Exception as e:
            _emit_proxy_log("warning", f"[proxy/status] fetch failed: {type(e).__name__}: {e}")
        time.sleep(5)


@app.on_event("startup")
def start_proxy_metrics_logger():
    _emit_proxy_log("info", "[proxy/status] scheduling periodic logger thread")
    threading.Thread(target=_proxy_metrics_logger, daemon=True, name="proxy-metrics-logger").start()

@app.post("/trainingMetrics")
async def set_training_metrics(request: Request):
    update = await request.json()
    with training_lock:
        if "is_training" in update and update["is_training"] is not None:
            training_metrics["is_training"] = update["is_training"]
        if "loss" in update:
            training_metrics["loss"] = update["loss"]
        if "accuracy" in update:
            training_metrics["accuracy"] = update["accuracy"]
    return JSONResponse({"ok": True})


@app.get("/deviceMetrics")
def get_device_metrics():
    try:
        if not JTOP_AVAILABLE:
            return JSONResponse({"data": {}, "error": "Jtop not available on this device"}, status_code=503)
        
        with jtop() as jetson:
            state = jetson.stats
            return JSONResponse({
                "data": {
                    "gpu_usage": state.get("GPU"),
                    "gpu_temperature": state.get("Temp GPU"),
                    "ram_usage": state.get("RAM"),
                }
            })
        
    except Exception as e:
        logging.error(f"[JTOP] Read error: {e}")
        return JSONResponse({"data": {}, "error": str(e)}, status_code=500)


@app.get("/trainingMetrics")
def get_training_metrics():
    with training_lock:
        filtered = {k: (v if v is not None else None) for k, v in training_metrics.items()}
    return JSONResponse({"data": filtered})


@app.get("/proxyMetrics")
def get_proxy_metrics():
    try:
        request = urllib.request.Request("http://127.0.0.1:80/proxy/status")
        with urllib.request.urlopen(request, timeout=2.0) as response:
            data = json.loads(response.read())
        avg_value = data.get("inflight_60s_avg")
        current_value = data.get("inflight_requests")
        max_value = data.get("inflight_60s_max")

        avg_num = float(avg_value) if avg_value is not None else 0.0
        current_num = float(current_value) if current_value is not None else 0.0
        max_num = float(max_value) if max_value is not None else 0.0
        effective = max(avg_num, current_num, max_num)

        logging.info(f"[proxyMetrics] raw_avg={avg_num} current={current_num} max={max_num} -> effective={effective}")

        return JSONResponse({
            "data": {
                "inflight_60s_avg": effective,
                "inflight_requests": current_num,
                "inflight_60s_max": max_num,
                "inflight_60s_avg_raw": avg_num,
            }
        })
    except Exception as e:
        logging.error(f"[proxyMetrics] Failed to fetch proxy metrics from nginx /proxy/status: {e}")
        return JSONResponse({"data": {}, "error": "Failed to fetch proxy metrics"}, status_code=500)
