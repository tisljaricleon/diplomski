import yaml
import argparse
import concurrent.futures
import threading
import flwr as fl
from flwr.common import parameters_to_ndarrays, ndarrays_to_parameters, Scalar, Metrics, EvaluateRes, FitRes
from flwr.server.client_proxy import ClientProxy
from typing import List, Tuple, Optional, Union, Dict
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.info("Training started")
logging.warning("This is a warning")

# --- Shared State ---
class SharedState:
    def __init__(self):
        self.server_lock = threading.Lock()
        self.client_lock = threading.Lock()
        self.current_parameters = None
        self.local_round = 0
        self.waiting_to_sync = False
        self.has_initialized = False
        # training:
        self.num_examples = 0
        self.avg_acc = 0.0
        self.avg_loss = 0.0
        # evaluation:
        self.test_num_examples = 0
        self.test_avg_acc = 0.0
        self.test_avg_loss = 0.0

# --- Strategy ---
class FedAvgWithCheckpoint(fl.server.strategy.FedAvg):
    def __init__(self,
            shared_state: SharedState,
            local_rounds: int,
            fraction_fit: float = 1.0,
            fraction_evaluate: float = 1.0,
            min_fit_clients: int = 2,
            min_evaluate_clients: int = 2,
            min_available_clients: int = 2,
        ):
        super().__init__(
            fraction_fit=fraction_fit,
            fraction_evaluate=fraction_evaluate,
            min_fit_clients=min_fit_clients,
            min_evaluate_clients=min_evaluate_clients,
            min_available_clients=min_available_clients,
        )
        self.shared_state = shared_state
        self.local_rounds = local_rounds

    def initialize_parameters(self, client_manager):
        logging.info("[Local Aggregator] Waiting to initialize with global parameters.")
        while self.shared_state.current_parameters is None:
            pass
        logging.info("[Local Aggregator] Initialized with global parameters.")
        return self.shared_state.current_parameters

    def aggregate_fit(self, rnd, results, failures):
        aggregated_result = super().aggregate_fit(rnd, results, failures)
        self.shared_state.local_round += 1
        self.shared_state.current_parameters = aggregated_result[0]

        for _, fit_res in results:
            self.shared_state.num_examples += fit_res.num_examples

        if self.shared_state.local_round % self.local_rounds == 0:
            logging.info("[Aggregator] Completed local rounds. Syncing with global server...")
            self.shared_state.waiting_to_sync = True
            # Removed server_lock acquisition before server starts
            logging.info("[Local Aggregator] Releasing lock to let global client continue...")
            self.shared_state.client_lock.release()
            self.shared_state.server_lock.acquire()

        return self.shared_state.current_parameters, {}

    def aggregate_evaluate(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, EvaluateRes]],
        failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]],
    ) -> Tuple[Optional[float], Dict[str, Scalar]]:


        if not results:
            return None, {}

        # Call aggregate_evaluate from base class (FedAvg) to aggregate loss and metrics
        aggregated_loss, aggregated_metrics = super().aggregate_evaluate(
            server_round, results, failures
        )

        # Weigh accuracy of each client by number of examples used
        accuracies = [r.metrics["accuracy"] * r.num_examples for _, r in results]
        examples = [r.num_examples for _, r in results]

        # Aggregate and print custom metric
        aggregated_accuracy = sum(accuracies) / sum(examples)
        logging.info(
            f"[Aggregator] Round {server_round} accuracy aggregated from client results: {aggregated_accuracy}"
        )
        self.shared_state.test_num_examples = sum(examples)
        self.shared_state.test_avg_loss = float(aggregated_loss)
        self.shared_state.test_avg_acc = float(aggregated_accuracy)

        return float(aggregated_loss), {"accuracy": float(aggregated_accuracy)}

# --- Parent Connection ---
class AggregatorParentConnection(fl.client.NumPyClient):
    def __init__(self, shared_state: SharedState, global_address: str):
        self.shared_state = shared_state
        self.global_address = global_address

    def get_parameters(self, config):
        return parameters_to_ndarrays(self.shared_state.current_parameters)

    def fit(self, parameters, config):
        round_num = config.get("server_round", 0)

        if round_num == 0 and not self.shared_state.has_initialized:
            logging.info("[Global Client] Initializing from global server.")
            self.shared_state.current_parameters = ndarrays_to_parameters(parameters)
            self.shared_state.has_initialized = True
            logging.info("[Global Client] Releasing lock to allow local server to start.")
            logging.info("[Global Client] Releasing server lock to resume local training.")
            self.shared_state.server_lock.release()  # Let local server start
            logging.info("[Global Client] Waiting for local training to finish after initialization...")
            logging.info("[Global Client] Blocking until local training completes...")
            self.shared_state.client_lock.acquire()  # Wait until local training is done
            logging.info("[Global Client] Acquired lock. Local training finished.")
            logging.info("[Global Client] Local training complete after initialization.")
            return self.get_parameters(config), self.shared_state.num_examples, {}

        logging.info(f"[Global Client] Received global update for round {round_num}.")
        self.shared_state.current_parameters = ndarrays_to_parameters(parameters)

        if self.shared_state.waiting_to_sync:
            logging.info("[Global Client] Waiting for local server to complete training...")
            self.shared_state.server_lock.release()
            self.shared_state.client_lock.acquire()
            logging.info("[Global Client] Local training complete. Sending update to global.")

        return self.get_parameters(config), self.shared_state.num_examples, {}

    def evaluate(self, parameters, config):
        return 0.0, 1, {"loss": 0.0, "accuracy": 0.0}

    def start(self):
        fl.client.start_numpy_client(server_address=self.global_address, client=self)


# --- Aggregator ---
class Aggregator:
    def __init__(self, server_cfg, strategy_cfg):
        self.shared_state = SharedState()
        logging.info("[Server Thread] Waiting for global parameters...")
        self.shared_state.server_lock.acquire()
        logging.info("[Server Thread] Received signal to start. Launching local Flower server...")
        self.shared_state.client_lock.acquire()  # Pre-lock client so it can block on first acquire
        self.local_address = server_cfg["local_address"]
        self.global_address = server_cfg["global_address"]
        self.local_rounds = server_cfg["local_rounds"]
        self.global_rounds = server_cfg["global_rounds"]

    def start(self):
        strategy = FedAvgWithCheckpoint(self.shared_state, self.local_rounds, strategy_cfg["fraction_fit"],
                strategy_cfg["fraction_evaluate"], strategy_cfg["min_fit_clients"], strategy_cfg["min_evaluate_clients"], strategy_cfg["min_available_clients"])

        def run_client():
            AggregatorParentConnection(self.shared_state, self.global_address).start()

        def run_server():
            self.shared_state.server_lock.acquire()  # Wait until client has received global params
            fl.server.start_server(
                server_address=self.local_address,
                config=fl.server.ServerConfig(num_rounds=self.local_rounds * self.global_rounds),
                strategy=strategy,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(run_client)
            executor.submit(run_server)


# --- Main ---
if __name__ == "__main__":

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    server_cfg = config["server"]
    strategy_cfg = config["strategy"]

    aggregator = Aggregator(server_cfg,
            strategy_cfg
    )
    aggregator.start()