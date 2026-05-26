import logging
import json
import urllib.request
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
        with urllib.request.urlopen(request, timeout=0.5) as response:
            data = json.loads(response.read())
        value = data.get("inflight_60s_avg")
        return JSONResponse({"data": {"inflight_60s_avg": float(value) if value is not None else None}})
    except Exception:
        return JSONResponse({"data": {}, "error": "Failed to fetch proxy metrics"}, status_code=500)
