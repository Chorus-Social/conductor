import asyncio
import nacl.signing
import nacl.encoding
import os
import logging
import json # Added for JSON logging

from .node import ValidatorNode
from .config import load_config

# Custom JSON Formatter
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "process": record.process,
            "thread": record.thread,
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

async def main():
    # Load configuration
    config = load_config(config_path="validator.yaml")

    # Configure logging with JSON formatter
    log_level = getattr(logging, config.validator.monitoring.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to prevent duplicate logs from basicConfig in node.py
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)
    logger.info("Starting Chorus Validator Node...")

    # Load validator keypair
    keypair_path = config.validator.keypair_path
    if not os.path.exists(keypair_path):
        logger.error(f"Validator keypair file not found at {keypair_path}")
        logger.error("Please generate a keypair using 'poetry run python generate_keys.py' first.")
        return

    with open(keypair_path, 'rb') as f:
        private_key_hex = f.read().strip()
    
    private_key = nacl.signing.SigningKey(private_key_hex, encoder=nacl.encoding.HexEncoder)
    public_key = private_key.verify_key
    keypair = (private_key.encode(), public_key.encode())

    # Ensure storage path exists
    storage_path = config.validator.storage.path
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)
        logger.info(f"Created storage path: {storage_path}")

    # For single-process simulation, define multiple validator nodes and link their DHTs.
    num_simulated_validators = 3 # Example: 3 validators
    simulated_validator_nodes: List[ValidatorNode] = []
    simulated_keypairs: List[tuple] = []
    all_validator_ids: List[str] = []

    # Generate keypairs for simulated validators
    for i in range(num_simulated_validators):
        # For simplicity, generate new keypairs. In a real scenario, these would be loaded.
        sim_private_key = nacl.signing.SigningKey.generate()
        sim_public_key = sim_private_key.verify_key
        simulated_keypairs.append((sim_private_key.encode(), sim_public_key.encode()))
        all_validator_ids.append(sim_public_key.hex())

    logger.info(f"Simulating a network of {num_simulated_validators} validators.")

    # Create ValidatorNode instances without peers initially
    for i in range(num_simulated_validators):
        node_config = load_config(config_path="validator.yaml") # Load config for each node
        # Adjust storage path for each simulated node
        node_config.validator.storage.path = f"{config.validator.storage.path}_node{i}"
        if not os.path.exists(node_config.validator.storage.path):
            os.makedirs(node_config.validator.storage.path)

        validator_node = ValidatorNode(
            config=node_config,
            validator_keypair=simulated_keypairs[i],
            all_validator_ids=all_validator_ids
        )
        simulated_validator_nodes.append(validator_node)

    # Link DHTNetwork instances as peers
    for i, node in enumerate(simulated_validator_nodes):
        other_peers = [p.dht for j, p in enumerate(simulated_validator_nodes) if i != j]
        node.dht.peers = other_peers
        logger.info(f"ValidatorNode {node.public_key.hex()} has {len(node.dht.peers)} peers.")

    # Start all validator nodes concurrently
    await asyncio.gather(*[node.start() for node in simulated_validator_nodes])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Validator node stopped by user.")