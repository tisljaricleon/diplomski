import torch
import flwr as fl
import logging
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays, Metrics
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
    def __init__(self, model_file, dataset_dir, metrics_server_url, **kwargs):
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
        self.net = load_model(model_file, self.device)
        
    def aggregate_fit(self, server_round, results, failures):
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

    fraction_fit = config["strategy"]["fraction_fit"]
    fraction_evaluate = config["strategy"]["fraction_evaluate"]
    min_fit_clients = config["strategy"]["min_fit_clients"]
    min_evaluate_clients = config["strategy"]["min_evaluate_clients"]
    min_available_clients = config["strategy"]["min_available_clients"]
    server_address = config["server"]["address"]
    global_rounds = config["server"]["global_rounds"]
    model_file = config["paths"]["model-file"]
    dataset_dir = config["paths"]["dataset-dir"]
    metrics_server_url = config["urls"]["metric-server-url"]

    logging.info("Parameters:")
    logging.info(f"Fraction fit: {fraction_fit}")
    logging.info(f"Fraction evaluate: {fraction_evaluate}")
    logging.info(f"Min. fit clients: {min_fit_clients}")
    logging.info(f"Min. evaluate clients: {min_evaluate_clients}")
    logging.info(f"Min. available clients: {min_available_clients}")
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
