import os
import logging
import time
import json
import urllib.request
from collections import OrderedDict
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.utils.data import DataLoader, Subset, random_split
from torchvision.transforms import Compose, Normalize, ToTensor
from torchvision.datasets import CIFAR10
import torchvision.models as models


def Net():
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 10)
    return model


def get_weights(net):
    return [val.cpu().numpy() for _, val in net.state_dict().items()]


def set_weights(net, parameters):
    params_dict = zip(net.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
    net.load_state_dict(state_dict, strict=True)


def load_model(model_file, device):
    net = Net()
    if os.path.exists(model_file):
        try:
            net.load_state_dict(torch.load(model_file, map_location=device))
            logging.info(f"[load_model] Loaded model weights from {model_file}")
        except Exception as e:
            logging.error(f"[load_model] Failed to load model from {model_file}: {e}")
            logging.info("[load_model] Initializing new model")
    else:
        logging.info(f"[load_model] No model found at {model_file}, initializing new model")
    return net


def save_model(net, model_file):
    os.makedirs(os.path.dirname(model_file), exist_ok=True)
    torch.save(net.state_dict(), model_file)
    logging.info(f"[save_model] Model saved to {model_file}")


def post_training_metrics(metrics_server_url, is_training=None, loss=None, accuracy=None):
    payload = {}
    if is_training is not None:
        payload["is_training"] = bool(is_training)
    if loss is not None:
        payload["loss"] = float(loss)
    if accuracy is not None:
        payload["accuracy"] = float(accuracy)
    if not payload:
        return

    try:
        endpoint = metrics_server_url + "/trainingMetrics"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=0.5):
            pass
        logging.info(f"[post_training_metrics] Posted metrics to {endpoint}: {payload}")
    except Exception as e:
        logging.warning(f"[post_training_metrics] Failed to post metrics: {e}")
    

def load_data(dataset_dir: str, partition_id: int, num_partitions: int, batch_size: int, num_workers: int = 4, pin_memory: bool = True):
    transform = Compose([
        ToTensor(),
        Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])

    os.makedirs(dataset_dir, exist_ok=True)
    full_dataset = CIFAR10(root=dataset_dir, train=True, download=True, transform=transform)
    full_dataset = Subset(full_dataset, range(50000))
    total_size = len(full_dataset)

    partition_size = total_size // num_partitions
    start_idx = partition_id * partition_size
    end_idx = start_idx + partition_size
    indices = list(range(start_idx, end_idx))

    partition_dataset = Subset(full_dataset, indices)

    train_size = int(0.8 * len(partition_dataset))
    test_size = len(partition_dataset) - train_size
    train_subset, test_subset = random_split(partition_dataset, [train_size, test_size], generator=torch.Generator().manual_seed(42))

    trainloader = DataLoader(train_subset, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=pin_memory)
    testloader = DataLoader(test_subset, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=pin_memory)

    return trainloader, testloader


def train(net, trainloader, valloader, epochs, learning_rate, device):
    net.to(device)
    criterion = torch.nn.CrossEntropyLoss().to(device)
    optimizer = torch.optim.SGD(net.parameters(), lr=learning_rate, momentum=0.9)
    net.train()
    for epoch in range(epochs):
        epoch_start = time.time()
        logging.info(f"[train] Epoch {epoch+1}/{epochs} started")
        for batch in trainloader:
            images, labels = batch
            optimizer.zero_grad()
            criterion(net(images.to(device)), labels.to(device)).backward()
            optimizer.step()
        epoch_duration = time.time() - epoch_start
        logging.info(f"[train] Epoch {epoch+1}/{epochs} ended in {epoch_duration:.2f}s")

    val_loss, val_acc = test(net, valloader, device)

    results = {
        "val_loss": val_loss,
        "val_accuracy": val_acc,
    }
    return results


def test(net, testloader, device):
    net.to(device)
    criterion = torch.nn.CrossEntropyLoss()
    correct, loss = 0, 0.0
    with torch.no_grad():
        for batch in testloader:
            images, labels = batch
            images = images.to(device)
            labels = labels.to(device)
            outputs = net(images)
            loss += criterion(outputs, labels).item()
            correct += (torch.max(outputs.data, 1)[1] == labels).sum().item()
    accuracy = correct / len(testloader.dataset)
    loss = loss / len(testloader)
    return loss, accuracy