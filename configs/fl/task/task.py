import os
import logging
import time
from collections import OrderedDict
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.utils.data import DataLoader, Subset, random_split
from torchvision.transforms import Compose, Normalize, ToTensor
from torchvision.datasets import CIFAR10


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


def get_weights(net):
    return [val.cpu().numpy() for _, val in net.state_dict().items()]


def set_weights(net, parameters):
    params_dict = zip(net.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
    net.load_state_dict(state_dict, strict=True)


def load_model(model_path, device):
    net = Net()
    if os.path.exists(model_path):
        try:
            net.load_state_dict(torch.load(model_path, map_location=device))
            logging.info(f"[LOAD OR INIT] Loaded model weights from: {model_path}")
        except Exception as e:
            logging.warning(f"[LOAD OR INIT] Failed to load model from {model_path}: {e}")
            logging.info("[LOAD OR INIT] Initializing new model")
    else:
        logging.info(f"[LOAD OR INIT] No model found at {model_path}"
                     f"\n[LOAD OR INIT] Initializing new model")
    return net

def save_model(net, model_path):
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    torch.save(net.state_dict(), model_path)
    logging.info(f"[SAVE MODEL] Model saved to {model_path}")
    

def load_data(partition_id: int, num_partitions: int, batch_size: int, num_workers: int = 4, pin_memory: bool = True):
    transform = Compose([
        ToTensor(),
        Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])

    full_dataset = CIFAR10(root="./dataset", train=True, download=True, transform=transform)
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

    trainloader = DataLoader(train_subset, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=pin_memory)
    testloader = DataLoader(test_subset, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=pin_memory)

    return trainloader, testloader




def train(net, trainloader, valloader, epochs, learning_rate, device, global_round=None, log_fn=None):
    """Train the model on the training set."""
    net.to(device)  # move model to GPU if available
    criterion = torch.nn.CrossEntropyLoss().to(device)
    optimizer = torch.optim.SGD(net.parameters(), lr=learning_rate, momentum=0.9)
    net.train()
    for epoch in range(epochs):
        epoch_start = time.time()
        logging.info(f"[Local Training] Epoch {epoch+1}/{epochs} started")
        if log_fn:
            log_fn("EPOCH_START", global_round=global_round, local_epoch=epoch+1)
        for batch in trainloader:
            images, labels = batch
            optimizer.zero_grad()
            criterion(net(images.to(device)), labels.to(device)).backward()
            optimizer.step()
        epoch_duration = time.time() - epoch_start
        logging.info(f"[Local Training] Epoch {epoch+1}/{epochs} ended in {epoch_duration:.2f}s")
        if log_fn:
            log_fn("EPOCH_END", global_round=global_round, local_epoch=epoch+1, duration=round(epoch_duration, 2))

    val_loss, val_acc = test(net, valloader, device)

    results = {
        "val_loss": val_loss,
        "val_accuracy": val_acc,
    }
    return results


def test(net, testloader, device):
    """Validate the model on the test set."""
    net.to(device)  # move model to GPU if available
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