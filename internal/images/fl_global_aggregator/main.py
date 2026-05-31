import torch
import flwr as fl
import logging
import csv
import json
import os
import time
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays, Metrics, FitIns, GetPropertiesIns
from flwr.server.strategy import FedAvg
import yaml
from typing import Tuple, Optional
from task import get_weights, load_data, test, set_weights, load_model, save_model, post_training_metrics, Net

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class LogAccuracyStrategy(FedAvg):
    def __init__(self, model_file, dataset_dir, metrics_server_url,
                 aom_threshold_rounds, aom_selection_enabled, inflight_threshold,
                 global_rounds, server_eval_every_rounds, server_eval_max_batches,
                 **kwargs):
        super().__init__(**kwargs)
        _, self.testloader = load_data(
            dataset_dir=dataset_dir,
            partition_id=0,
            num_partitions=1,
            batch_size=32,
        )
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        logging.info(f"[__init__] Using device: {self.device}")

        self.model_file = model_file
        self.metrics_server_url = metrics_server_url
        self.aom_threshold_rounds = aom_threshold_rounds
        self.aom_selection_enabled = aom_selection_enabled
        self.inflight_threshold = inflight_threshold
        self.global_rounds = global_rounds
        self.server_eval_every_rounds = max(1, int(server_eval_every_rounds))
        self.server_eval_max_batches = None if server_eval_max_batches is None else int(server_eval_max_batches)
        self.net = load_model(model_file, self.device)

        self.last_client_participation: dict[str, int] = {}

        # LOG PART START
        self.rounds_log_file = "/home/model/rounds_log.csv"
        self._round_start_times: dict[int, float] = {}
        if not os.path.exists(self.rounds_log_file):
            with open(self.rounds_log_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "round", "start_ts_ms", "end_ts_ms", "duration_s",
                    "num_clients_selected", "selected_client_ids", "loss", "accuracy"
                ])
                writer.writeheader()
        # LOG PART END

    def configure_fit(self, server_round, parameters, client_manager):
        config = {}
        if self.on_fit_config_fn is not None:
            config = self.on_fit_config_fn(server_round)

        fit_ins = FitIns(parameters, config)

        all_clients = list(client_manager.all().values())
        client_names = [client.cid for client in all_clients]
        logging.info(f"[configure_fit] Round {server_round}, clients available: {client_names}")

        # LOG PART START
        self._round_start_times[server_round] = time.time()
        # LOG PART END

        if not self.aom_selection_enabled:
            sampled = client_manager.sample(num_clients=self.min_fit_clients, min_num_clients=self.min_available_clients)
            return [(client, fit_ins) for client in sampled]
        
        always_selected = []
        eligible = []
        excluded = []
        for client_proxy in all_clients:
            last_round = self.last_client_participation.get(client_proxy.cid, 0)
            aom = server_round - last_round

            try:
                props = client_proxy.get_properties(GetPropertiesIns(config={}), timeout=2.0)
                logging.info(f"[configure_fit] Client {client_proxy.cid}: raw properties={dict(props.properties)}")
                inflight = float(props.properties.get("inflight_60s_avg", 0.0))
            except Exception as e:
                logging.warning(f"[configure_fit] get_properties FAILED for {client_proxy.cid}: {type(e).__name__}: {e}")
                inflight = 0.0
            logging.info(f"[configure_fit] Client {client_proxy.cid}: AoM={aom}, inflight={inflight}, threshold={self.inflight_threshold}")

            if aom > self.aom_threshold_rounds:
                always_selected.append((client_proxy, inflight))
            elif inflight < self.inflight_threshold:
                eligible.append((client_proxy, inflight))
            else:
                excluded.append((client_proxy, inflight))

        selected_clients = always_selected + eligible

        if len(selected_clients) < self.min_fit_clients:
            needed_clients = self.min_fit_clients - len(selected_clients)
            excluded.sort(key=lambda x: x[1])
            selected_clients.extend(excluded[:needed_clients])

        logging.info(
            f"[configure_fit] Round {server_round}, selected {len(selected_clients)}/{len(all_clients)} clients:"
            f" {[client.cid for client, _ in selected_clients]}"
        )
        return [(proxy, fit_ins) for proxy, _ in selected_clients]


    def aggregate_fit(self, server_round, results, failures):
        for client_proxy, fit_results in results:
            self.last_client_participation[client_proxy.cid] = server_round

        post_training_metrics(self.metrics_server_url, is_training=True)
        aggregated = super().aggregate_fit(server_round, results, failures)
        post_training_metrics(self.metrics_server_url, is_training=False)

        # LOG PART START
        end_time = time.time()
        start_time = self._round_start_times.get(server_round, end_time)
        duration = end_time - start_time
        selected_client_ids = json.dumps([client_proxy.cid for client_proxy, _ in results])
        with open(self.rounds_log_file, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "round", "start_ts_ms", "end_ts_ms", "duration_s",
                "num_clients_selected", "selected_client_ids", "loss", "accuracy"
            ])
            writer.writerow({
                "round": server_round,
                "start_ts_ms": int(start_time * 1000),
                "end_ts_ms": int(end_time * 1000),
                "duration_s": round(duration, 3),
                "num_clients_selected": len(results),
                "selected_client_ids": selected_client_ids,
                "loss": "",
                "accuracy": "",
            })
        # LOG PART END
        
        logging.info(f"[aggregate_fit] Round {server_round}: duration={duration:.1f}s, clients={len(results)}")
        return aggregated


    def aggregate_evaluate(self, server_round, results, failures):
        return super().aggregate_evaluate(server_round, results, failures)


    def evaluate(
        self,
        rnd: int,
        parameters,
    ) -> Optional[Tuple[float, Metrics]]:
        # Speed up round tail latency: run lightweight eval on intermediate rounds,
        # and full eval only on final round.
        if rnd != self.global_rounds and (rnd % self.server_eval_every_rounds != 0):
            logging.info(f"[evaluate] Round {rnd}: skipped (server_eval_every_rounds={self.server_eval_every_rounds})")
            return None

        ndarrays = parameters_to_ndarrays(parameters)
        set_weights(self.net, ndarrays)
        max_batches = None if rnd == self.global_rounds else self.server_eval_max_batches
        loss, accuracy = test(self.net, self.testloader, self.device, max_batches=max_batches)
        save_model(self.net, self.model_file)
        post_training_metrics(self.metrics_server_url, is_training=False, loss=loss, accuracy=accuracy)
        logging.info(
            f"[evaluate] Round {rnd}: loss: {loss:.4f}, accuracy: {accuracy:.4f}, "
            f"max_batches={'full' if max_batches is None else max_batches}"
        )

        # LOG PART START
        try:
            rows = []
            with open(self.rounds_log_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["round"] == str(rnd):
                        row["loss"] = round(loss, 6)
                        row["accuracy"] = round(accuracy, 6)
                    rows.append(row)
            with open(self.rounds_log_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "round", "start_ts_ms", "end_ts_ms", "duration_s",
                    "num_clients_selected", "selected_client_ids", "loss", "accuracy"
                ])
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            logging.warning(f"[evaluate] Failed to update rounds_log CSV: {e}")
        # LOG PART END

        return loss, {"accuracy": accuracy, "loss": loss}


if __name__ == "__main__":

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    fraction_fit = config["strategy"]["fraction-fit"]
    fraction_evaluate = config["strategy"]["fraction-evaluate"]
    min_fit_clients = config["strategy"]["min-fit-clients"]
    min_evaluate_clients = config["strategy"]["min-evaluate-clients"]
    min_available_clients = config["strategy"]["min-available-clients"]
    aom_threshold_rounds = int(config["strategy"].get("aom-rounds-treshold", 3))
    aom_selection_enabled = bool(config["strategy"].get("aom-selection-enabled", True))
    inflight_threshold = float(config["strategy"].get("inflight-threshold", 9999999.0))
    server_eval_every_rounds = int(config["strategy"].get("server-eval-every-rounds", 1))
    _max_batches_raw = config["strategy"].get("server-eval-max-batches", 50)
    server_eval_max_batches = None if _max_batches_raw in (None, "none", "None", 0) else int(_max_batches_raw)
    server_address = config["server"]["address"]
    global_rounds = config["server"]["global-rounds"]
    model_file = config["paths"]["model-file"]
    dataset_dir = config["paths"]["dataset-dir"]
    metrics_server_url = config["urls"]["metric-server-url"]

    logging.info("Parameters:")
    logging.info(f"Fraction fit: {fraction_fit}")
    logging.info(f"Fraction evaluate: {fraction_evaluate}")
    logging.info(f"Min. fit clients: {min_fit_clients}")
    logging.info(f"Min. evaluate clients: {min_evaluate_clients}")
    logging.info(f"Min. available clients: {min_available_clients}")
    logging.info(f"AoM threshold rounds: {aom_threshold_rounds}")
    logging.info(f"AoM selection enabled: {aom_selection_enabled}")
    logging.info(f"Inflight threshold: {inflight_threshold}")
    logging.info(f"Server eval every rounds: {server_eval_every_rounds}")
    logging.info(f"Server eval max batches: {server_eval_max_batches}")
    logging.info(f"Server address: {server_address}")
    logging.info(f"Global rounds: {global_rounds}")
    logging.info(f"Model path: {model_file}")
    logging.info(f"Dataset path: {dataset_dir}")
    logging.info(f"Metrics server URL: {metrics_server_url}")
    post_training_metrics(metrics_server_url, is_training=False)

    # ===== EXPERIMENT INIT START (delete this block after experiments) =====
    # Seeds a fresh ResNet-18 with fixed weights and saves it as the initial
    # checkpoint so every experiment run starts from exactly the same model,
    # regardless of whatever was previously saved at model_file.
    import numpy as np
    _init_seed = 42
    torch.manual_seed(_init_seed)
    np.random.seed(_init_seed)
    _init_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    _fresh_model = Net()
    save_model(_fresh_model, model_file)
    logging.info(f"[EXPERIMENT INIT] Saved fixed-seed (seed={_init_seed}) initial model to {model_file}")
    # ===== EXPERIMENT INIT END =====

    pretrained_model = load_model(model_file, torch.device("cuda:0" if torch.cuda.is_available() else "cpu"))
    ndarrays = get_weights(pretrained_model)
    parameters = ndarrays_to_parameters(ndarrays)

    strategy = LogAccuracyStrategy(
        model_file=model_file,
        dataset_dir=dataset_dir,
        metrics_server_url=metrics_server_url,
        aom_threshold_rounds=aom_threshold_rounds,
        aom_selection_enabled=aom_selection_enabled,
        inflight_threshold=inflight_threshold,
        global_rounds=global_rounds,
        server_eval_every_rounds=server_eval_every_rounds,
        server_eval_max_batches=server_eval_max_batches,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
        min_fit_clients=min_fit_clients,
        min_evaluate_clients=min_evaluate_clients,
        min_available_clients=min_available_clients,
        initial_parameters=parameters,
    )

    try:
        fl.server.start_server(
            server_address=server_address,
            config=fl.server.ServerConfig(num_rounds=global_rounds),
            strategy=strategy,
        )
    except Exception as e:
        logging.error(f"Global aggregator failed to start: {e}")
