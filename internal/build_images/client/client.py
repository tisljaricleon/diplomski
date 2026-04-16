import yaml
import os
import csv
import torch
import flwr as fl
from datetime import datetime
from task import Net, get_weights, load_data, set_weights, test, train, load_model, save_model
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

CSV_PATH = "/home/model/fl_data.csv"

def log_to_csv(event, global_round=None, local_epoch=None, val_loss=None, val_accuracy=None, duration=None):
    file_exists = os.path.exists(CSV_PATH)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "event", "global_round", "local_epoch", "val_loss", "val_accuracy", "duration_s"])
        writer.writerow([datetime.now().isoformat(), event, global_round, local_epoch, val_loss, val_accuracy, duration])

local_round = 1
class FlowerClient(fl.client.NumPyClient):
    def __init__(self, trainloader, valloader, local_epochs, learning_rate, partition_id):
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        print(f"[INIT] Using device: {self.device}")
        self.trainloader = trainloader
        self.valloader = valloader
        self.local_epochs = local_epochs
        self.lr = learning_rate
        self.partition_id = partition_id

        model_path = "/home/model/model_resnet18.pt"
        self.net = load_model(model_path, self.device)


    def fit(self, parameters, config):
        global local_round
        logging.info(f"[Client {self.partition_id}] Global round {local_round} started")
        log_to_csv("GLOBAL_ROUND_START", global_round=local_round)
        set_weights(self.net, parameters)

        round_start = time.time()
        results = train(
            self.net,
            self.trainloader,
            self.valloader,
            self.local_epochs,
            self.lr,
            self.device,
            global_round=local_round,
            log_fn=log_to_csv,
        )
        round_duration = time.time() - round_start

        model_path = "/home/model/model_resnet18.pt"
        
        save_model(self.net, model_path)

        logging.info(f"[Client {self.partition_id}] Global round {local_round} ended in {round_duration:.2f}s")
        log_to_csv("GLOBAL_ROUND_END", global_round=local_round,
                   val_loss=results["val_loss"], val_accuracy=results["val_accuracy"],
                   duration=round(round_duration, 2))

        local_round += 1
        return get_weights(self.net), len(self.trainloader.dataset), results


    def evaluate(self, parameters, config):
        set_weights(self.net, parameters)
        loss, accuracy = test(self.net, self.valloader, self.device)
        logging.info(f"[Client {self.partition_id}] test loss: {loss} , test accuracy: {accuracy} ")
        return loss, len(self.valloader.dataset), {"accuracy": accuracy,"loss":loss}
    
    
if __name__ == "__main__":
    start = time.time()

    with open("client_config.yaml", 'r') as file:
        config = yaml.safe_load(file)

    partition_id = config["node_config"]["partition-id"]
    num_partitions = config["node_config"]["num-partitions"]

    batch_size = config["run_config"]["batch-size"]
    local_epochs = config["run_config"]["local-epochs"]
    learning_rate = config["run_config"]["learning-rate"]

    server_address = config["server"]["address"]

    print("Parameters:")
    print(f"Partition ID: {partition_id}")
    print(f"Number of partitions: {num_partitions}")
    print(f"Batch size: {batch_size}")
    print(f"Local epochs: {local_epochs}")
    print(f"Learning rate: {learning_rate}")
    print(f"Server address: {server_address}")

    print(f"Before loading partition in {time.time() - start:.2f} sec")

    start = time.time()
    trainloader, valloader = load_data(partition_id, num_partitions, batch_size)
    print(f"Loaded partition in {time.time() - start:.2f} sec")

    logging.info("[FL] Federated learning started")
    log_to_csv("FL_START")

    client = FlowerClient(trainloader, valloader, local_epochs, learning_rate, partition_id).to_client()
    fl.client.start_numpy_client(server_address=server_address, client=client)



