import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import io
import torch
import os
from torchvision import transforms


# Inline Net model definition (copied from task.py)
import torch.nn as nn
import torch.nn.functional as F

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

app = FastAPI()

def get_model_path():
    return f"/home/model/model.pt"


def load_model():
    model_path = get_model_path()
    if not os.path.exists(model_path):
        return None
    try:
        model = Net()
        state_dict = torch.load(model_path, map_location=torch.device('cpu'))
        model.load_state_dict(state_dict)
        model.eval()
        return model
    except Exception as e:
        print(f"[MODEL LOAD ERROR] {e}")
        return None

cifar10_transform = transforms.Compose([
    transforms.Resize((32, 32)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
])

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    model = load_model()
    if model is None:
        return JSONResponse({"prediction": None, "error": "Model not found"}, status_code=200)
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        tensor = cifar10_transform(image).unsqueeze(0)
        with torch.no_grad():
            output = model(tensor)
            pred = output.argmax(dim=1).item()
        return JSONResponse({"prediction": int(pred)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    with open("global_server_serving_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    address = config.get("server", {}).get("address", "0.0.0.0:8000")

    if ":" in address:
        host, port_str = address.rsplit(":", 1)
        port = int(port_str)

    uvicorn.run(app, host=host, port=port)
    print(f"Global Server Serving started at {host}:{port}")
