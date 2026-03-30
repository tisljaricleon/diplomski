import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import io
import torch
import os
import yaml
from torchvision import transforms
import torch.nn as nn
import torch.nn.functional as F
import threading
import csv
import datetime
from jtop import jtop


ongoing_requests = 0
ongoing_requests_lock = threading.Lock()

cuda_available = torch.cuda.is_available()
device = torch.device("cuda:0" if cuda_available else "cpu")
cifar10_transform = transforms.Compose([
    transforms.Resize((32, 32)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
])

app = FastAPI()


def log_resource_usage(ongoing_requests):
    jtop_stats = None
    try:
        with jtop() as jetson:
            if jetson.ok():
                stats = jetson.stats
                if 'time' in stats and isinstance(stats['time'], datetime.datetime):
                    stats['timestamp'] = stats['time']
                jtop_stats = {
                    'timestamp': stats.get('timestamp'),
                    'ongoing_requests': ongoing_requests,
                    'cpu1': stats.get('CPU1'),
                    'cpu2': stats.get('CPU2'),
                    'cpu3': stats.get('CPU3'),
                    'cpu4': stats.get('CPU4'),
                    'cpu5': stats.get('CPU5'),
                    'cpu6': stats.get('CPU6'),
                    'gpu': stats.get('GPU'),
                    'ram': stats.get('RAM'),
                    'swap': stats.get('SWAP'),
                    'fan': stats.get('Fan pwmfan0'),
                    'temp_cpu': stats.get('Temp cpu'),
                    'temp_gpu': stats.get('Temp gpu'),
                    'temp_soc0': stats.get('Temp soc0'),
                    'temp_soc1': stats.get('Temp soc1'),
                    'temp_soc2': stats.get('Temp soc2'),
                    'temp_therm_junction': stats.get('Temp tj'),
                    'power_vdd_cpu_gpu_cv': stats.get('Power VDD_CPU_GPU_CV'),
                    'power_vdd_soc': stats.get('Power VDD_SOC'),
                    'power_tot': stats.get('Power TOT'),
                    'jetson_clocks': stats.get('jetson_clocks'),
                    'nvp_model': stats.get('nvp model')
                }
    except Exception as e:
        print(f"[RESOURCE LOG] Error: {e}")

    log_path = "/home/model/resource_log.csv"
    stat_fields = [
        'timestamp', 'ongoing_requests', 'cpu1', 'cpu2', 'cpu3', 'cpu4', 'cpu5', 'cpu6', 'gpu', 'ram', 'swap',
        'fan', 'temp_cpu', 'temp_gpu', 'temp_soc0', 'temp_soc1', 'temp_soc2', 'temp_therm_junction',
        'power_vdd_cpu_gpu_cv', 'power_vdd_soc', 'power_tot', 'jetson_clocks', 'nvp_model'
    ]
    with open(log_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(stat_fields)
        if jtop_stats is not None:
            row = [jtop_stats.get(field, '') for field in stat_fields]
        else:
            row = ['' for _ in stat_fields]
        writer.writerow(row)


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 16 * 5 * 5)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


def load_model():
    model_path = "/home/model/model.pt"
    if not os.path.exists(model_path):
        return None
    try:
        print(f"[MODEL LOAD] Loading model from {model_path}")
        state_dict = torch.load(model_path, map_location=torch.device('cpu'))
        print(f"[MODEL LOAD] Loaded object type: {type(state_dict)}")
        model = Net()
        model.load_state_dict(state_dict)
        model.eval()
        model.to(device)
        print(f"[MODEL LOAD] Model moved to device: {device}")
        return model
    except Exception as e:
        print(f"[MODEL LOAD] Error: {e}")
        return None

model = load_model()


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    global model, ongoing_requests

    with ongoing_requests_lock:
        ongoing_requests += 1
        current_ongoing = ongoing_requests

    try:
        if model is None:
            model = load_model()
            if model is None:
                log_resource_usage(current_ongoing)
                return JSONResponse({"label": None, "error": "Model not found"}, status_code=404)
            
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        tensor = cifar10_transform(image).unsqueeze(0)
        tensor = tensor.to(device)
        with torch.no_grad():
            output = model(tensor)
            pred = output.argmax(dim=1).item()

        log_resource_usage(current_ongoing)
        return JSONResponse({"label": int(pred)})
    except Exception as e:
        log_resource_usage(current_ongoing)
        return JSONResponse({ "label": None, "error": str(e)}, status_code=500)
    finally:
        with ongoing_requests_lock:
            ongoing_requests -= 1


if __name__ == "__main__":
    with open("client_serving_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    address = config.get("server", {}).get("address", "0.0.0.0:8000")
    if ":" in address:
        host, port_str = address.rsplit(":", 1)
        port = int(port_str)

    uvicorn.run(app, host=host, port=port)
    print(f"Client serving started at {host}:{port}")