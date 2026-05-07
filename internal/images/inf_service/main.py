from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import io
import torch
import os
import logging
from torchvision import transforms, models
import torch.nn as nn

import asyncio
import time
from typing import List


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


FL_MODEL_FILE = os.getenv("FL_MODEL_FILE", "/home/model/model.pt")
LABEL_NAMES = [
    "airplane", "automobile", "bird", "cat", "deer",
    "dog", "frog", "horse", "ship", "truck"
]


cuda_available = torch.cuda.is_available()
device = torch.device("cuda:0" if cuda_available else "cpu")
cifar10_transform = transforms.Compose([
    transforms.Resize((32, 32)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
])


def Net():
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 10)
    return model


def load_model():
    if not os.path.exists(FL_MODEL_FILE):
        logging.info(f"[load_model] No model found at {FL_MODEL_FILE}")
        return None
    try:
        logging.info(f"[load_model] Loading model from {FL_MODEL_FILE}")
        state_dict = torch.load(FL_MODEL_FILE, map_location=torch.device('cpu'))
        model = Net()
        model.load_state_dict(state_dict)
        model.eval()
        model.to(device)
        logging.info(f"[load_model] Model loaded and moved to device: {device}")
        return model
    except Exception as e:
        logging.exception(f"[load_model] Error: {e}")
        return None

model = load_model()


def inference(tensor):
    with torch.no_grad():
        output = model(tensor)
        preds = output.argmax(dim=1)
        return preds.cpu().numpy(), output.cpu().numpy()


app = FastAPI()
@app.post("/predict")
async def predict(files: List[UploadFile] = File(...)):
    global model
    try:
        if model is None:
            model = load_model()
        if model is None:
            logging.warning("[predict] Model not found")
            return JSONResponse({"results": None, "error": "Model not found"}, status_code=404)

        images = []
        for file in files:
            image = Image.open(io.BytesIO(await file.read())).convert("RGB")
            tensor = cifar10_transform(image)
            images.append(tensor)
        batch_tensor = torch.stack(images).to(device)

        start_time = time.time()
        preds, logits = await asyncio.to_thread(inference, batch_tensor)
        end_time = time.time()
        logging.info(f"[predict] duration: {(end_time - start_time) * 1000:.2f}ms")

        probs = torch.nn.functional.softmax(torch.from_numpy(logits), dim=1).numpy()
        results = []
        for idx in range(len(preds)):
            label_idx = int(preds[idx])
            label_name = LABEL_NAMES[label_idx]
            confidence = float(probs[idx][label_idx])
            results.append({
                "label_index": label_idx,
                "label_name": label_name,
                "confidence": confidence
            })
        return JSONResponse({"results": results}, status_code=200)
    except Exception as e:
        logging.exception(f"[predict] {e}")
        return JSONResponse({ "results": None, "error": str(e)}, status_code=500)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.exception(f"[global_exception_handler] {exc}")
    return JSONResponse({"results": None, "error": str(exc)}, status_code=500)
