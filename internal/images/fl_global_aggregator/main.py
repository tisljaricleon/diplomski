import torch
import flwr as fl
import logging
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays, Metrics, FitIns, GetPropertiesIns
from flwr.server.strategy import FedAvg
import yaml
from typing import Tuple, Optional
from task import get_weights, load_data, test, set_weights, load_model, save_model, post_training_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class LogAccuracyStrategy(FedAvg):
    def __init__(self, model_file, dataset_dir, metrics_server_url,
                 aom_threshold_rounds,
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
        self.net = load_model(model_file, self.device)

        self.last_client_participation: dict[str, int] = {}


    def configure_fit(self, server_round, parameters, client_manager):
        config = {}
        if self.on_fit_config_fn is not None:
            config = self.on_fit_config_fn(server_round)

        fit_ins = FitIns(parameters, config)

        all_clients = list(client_manager.all().values())
        client_names = [client.cid for client in all_clients]
        logging.info(f"[configure_fit] Round {server_round}, clients available: {client_names}")

        selected_clients = []
        remaining_clients = []
        for client_proxy in all_clients:
            last_round = self.last_client_participation.get(client_proxy.cid, 0)
            aom = server_round - last_round

            try:
                props = client_proxy.get_properties(GetPropertiesIns(config={}), timeout=2.0, group_id=None)
                inflight = float(props.properties.get("inflight_60s_avg", 0.0))
            except Exception:
                inflight = 0.0
            logging.info(f"[configure_fit] Client {client_proxy.cid}: AoM={aom}, inflight={inflight}")

            if aom > self.aom_threshold_rounds:
                selected_clients.append((client_proxy, inflight))
            else:
                remaining_clients.append((client_proxy, inflight))

        if len(selected_clients) < self.min_fit_clients:
            needed_clients = self.min_fit_clients - len(selected_clients)
            remaining_clients.sort(key=lambda x: x[1])
            selected_clients.extend(remaining_clients[:needed_clients])

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
        return aggregated


    def aggregate_evaluate(self, server_round, results, failures):
        return super().aggregate_evaluate(server_round, results, failures)


    def evaluate(
        self,
        rnd: int,
        parameters,
    ) -> Optional[Tuple[float, Metrics]]:
        ndarrays = parameters_to_ndarrays(parameters)
        set_weights(self.net, ndarrays)
        loss, accuracy = test(self.net, self.testloader, self.device)
        save_model(self.net, self.model_file)
        post_training_metrics(self.metrics_server_url, is_training=False, loss=loss, accuracy=accuracy)
        logging.info(f"[evaluate] Round {rnd}: loss: {loss:.4f}, accuracy: {accuracy:.4f}")
        return loss, {"accuracy": accuracy, "loss": loss}


if __name__ == "__main__":

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    fraction_fit = config["strategy"]["fraction-fit"]
    fraction_evaluate = config["strategy"]["fraction-evaluate"]
    min_fit_clients = config["strategy"]["min-fit-clients"]
    min_evaluate_clients = config["strategy"]["min-evaluate-clients"]
    min_available_clients = config["strategy"]["min-available-clients"]
    aom_threshold_rounds = config["strategy"]["aom-rounds-treshold"]
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
    logging.info(f"Server address: {server_address}")
    logging.info(f"Global rounds: {global_rounds}")
    logging.info(f"Model path: {model_file}")
    logging.info(f"Dataset path: {dataset_dir}")
    logging.info(f"Metrics server URL: {metrics_server_url}")
    post_training_metrics(metrics_server_url, is_training=False)

    pretrained_model = load_model(model_file, torch.device("cuda:0" if torch.cuda.is_available() else "cpu"))
    ndarrays = get_weights(pretrained_model)
    parameters = ndarrays_to_parameters(ndarrays)

    strategy = LogAccuracyStrategy(
        model_file=model_file,
        dataset_dir=dataset_dir,
        metrics_server_url=metrics_server_url,
        aom_threshold_rounds=aom_threshold_rounds,
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
