import yaml
import json
import urllib.request
import csv
import os
import torch
import flwr as fl
from task import Net, get_weights, load_data, set_weights, test, train, load_model, save_model, post_training_metrics
import logging
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

local_round = 0
local_eval_round = 0


class FlowerClient(fl.client.NumPyClient):
    def __init__(self, trainloader, valloader, local_epochs, learning_rate, partition_id, model_file, metrics_server_url):
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        logging.info(f"[__init__, client {partition_id}] Using device: {self.device}")

        self.trainloader = trainloader
        self.valloader = valloader
        self.local_epochs = local_epochs
        self.lr = learning_rate
        self.partition_id = partition_id
        self.model_file = model_file
        self.metrics_server_url = metrics_server_url
        self.net = load_model(self.model_file, self.device)
        self.rounds_log_file = f"/home/model/client_rounds_log_p{self.partition_id}.csv"

        with open(self.rounds_log_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "round", "phase", "start_ts_ms", "end_ts_ms", "duration_s",
                "train_samples", "eval_samples", "loss", "accuracy"
            ])
            writer.writeheader()

    def _append_round_log(self, round_no, phase, start_ts_ms, end_ts_ms, duration_s, train_samples, eval_samples, loss, accuracy):
        with open(self.rounds_log_file, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "round", "phase", "start_ts_ms", "end_ts_ms", "duration_s",
                "train_samples", "eval_samples", "loss", "accuracy"
            ])
            writer.writerow({
                "round": round_no,
                "phase": phase,
                "start_ts_ms": int(start_ts_ms),
                "end_ts_ms": int(end_ts_ms),
                "duration_s": round(duration_s, 3),
                "train_samples": train_samples,
                "eval_samples": eval_samples,
                "loss": "" if loss is None else round(float(loss), 6),
                "accuracy": "" if accuracy is None else round(float(accuracy), 6),
            })


    def get_properties(self, config):
        try:
            req = urllib.request.Request(self.metrics_server_url + "/proxyMetrics")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read()).get("data", {})
            value = float(data.get("inflight_60s_avg", 0.0))
            logging.info(f"[get_properties, client {self.partition_id}] proxyMetrics raw={data} -> inflight_60s_avg={value}")
            return {"inflight_60s_avg": value}
        except Exception as e:
            logging.warning(f"[get_properties, client {self.partition_id}] Failed to fetch proxy metrics: {type(e).__name__}: {e}")
            return {"inflight_60s_avg": 0.0}


    def fit(self, parameters, config):
        global local_round
        local_round += 1
        post_training_metrics(self.metrics_server_url, is_training=True)
        logging.info(f"[fit, client {self.partition_id}] Global round {local_round} started")
        set_weights(self.net, parameters)

        try:
            round_start = time.time()
            start_ts_ms = int(round_start * 1000)
            results = train(
                self.net,
                self.trainloader,
                self.valloader,
                self.local_epochs,
                self.lr,
                self.device,
            )
            round_duration = time.time() - round_start

            save_model(self.net, self.model_file)
            post_training_metrics(
                self.metrics_server_url,
                is_training=False,
                loss=results.get("val_loss"),
                accuracy=results.get("val_accuracy"),
            )
            logging.info(f"[fit, client {self.partition_id}] Global round {local_round} ended in {round_duration:.2f}s")
            self._append_round_log(
                round_no=local_round,
                phase="fit",
                start_ts_ms=start_ts_ms,
                end_ts_ms=int(time.time() * 1000),
                duration_s=round_duration,
                train_samples=len(self.trainloader.dataset),
                eval_samples=len(self.valloader.dataset),
                loss=results.get("val_loss"),
                accuracy=results.get("val_accuracy"),
            )

            return get_weights(self.net), len(self.trainloader.dataset), results
        except Exception:
            post_training_metrics(self.metrics_server_url, is_training=False)
            raise


    def evaluate(self, parameters, config):
        global local_eval_round
        local_eval_round += 1
        eval_start = time.time()
        set_weights(self.net, parameters)
        loss, accuracy = test(self.net, self.valloader, self.device)
        logging.info(f"[evaluate, client {self.partition_id}] Test loss: {loss}, test accuracy: {accuracy}")
        self._append_round_log(
            round_no=local_eval_round,
            phase="evaluate",
            start_ts_ms=int(eval_start * 1000),
            end_ts_ms=int(time.time() * 1000),
            duration_s=time.time() - eval_start,
            train_samples=len(self.trainloader.dataset),
            eval_samples=len(self.valloader.dataset),
            loss=loss,
            accuracy=accuracy,
        )
        #post_training_metrics(self.metrics_server_url, is_training=False, loss=loss, accuracy=accuracy)
        return loss, len(self.valloader.dataset), {"accuracy": accuracy,"loss":loss}
    
    
if __name__ == "__main__":
    start = time.time()

    with open("config.yaml", 'r') as file:
        config = yaml.safe_load(file)

    partition_id = config["node_config"]["partition-id"]
    num_partitions = config["node_config"]["num-partitions"]
    batch_size = config["run_config"]["batch-size"]
    local_epochs = config["run_config"]["local-epochs"]
    learning_rate = config["run_config"]["learning-rate"]
    dataset_dir = config["paths"]["dataset-dir"]
    model_file = config["paths"]["model-file"]
    server_address = config["server"]["address"]
    metrics_server_url = config["urls"]["metric-server-url"]

    logging.info("Parameters:")
    logging.info(f"Partition ID: {partition_id}")
    logging.info(f"Number of partitions: {num_partitions}")
    logging.info(f"Batch size: {batch_size}")
    logging.info(f"Local epochs: {local_epochs}")
    logging.info(f"Learning rate: {learning_rate}")
    logging.info(f"Dataset path: {dataset_dir}")
    logging.info(f"Model path: {model_file}")
    logging.info(f"Server address: {server_address}")
    logging.info(f"Metrics server URL: {metrics_server_url}")
    post_training_metrics(metrics_server_url, is_training=False)

    start = time.time()
    trainloader, valloader = load_data(dataset_dir, partition_id, num_partitions, batch_size)
    logging.info(f"Loaded partition in {time.time() - start:.2f}s")

    client = FlowerClient(
        trainloader,
        valloader,
        local_epochs,
        learning_rate,
        partition_id,
        model_file,
        metrics_server_url,
    ).to_client()
    fl.client.start_numpy_client(server_address=server_address, client=client)