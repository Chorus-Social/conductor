"""Main entry point for Conductor."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from conductor.config import load_config
from conductor.logging_config import configure_logging, get_logger
from conductor.node import ValidatorNode
from conductor.api import serve_grpc
from conductor.rest_api import app, set_validator_node
from conductor.metrics import metrics
from conductor.network import NetworkManager
import uvicorn

logger = get_logger(__name__)

class ConductorApplication:
    """Main Conductor application."""
    
    def __init__(self, config_path: str = None):
        """Initialize Conductor application."""
        self.config = load_config(config_path)
        self.validator_node = None
        self.network_manager = None
        self.grpc_server = None
        self.rest_server = None
        self.running = False
        
    async def start(self):
        """Start the Conductor application."""
        try:
            logger.info("Starting Conductor application")
            
            # Configure logging
            configure_logging(
                log_level=self.config.validator.monitoring.log_level,
                enable_json=True
            )
            
            # Generate keypair if not exists
            keypair = await self._get_or_generate_keypair()
            
            # Get validator IDs (in production, this would come from configuration)
            validator_ids = self._get_validator_ids()
            
            # Initialize validator node
            self.validator_node = ValidatorNode(
                config=self.config,
                validator_keypair=keypair,
                all_validator_ids=validator_ids
            )
            
            # Set validator node for REST API
            set_validator_node(self.validator_node)
            
            # Initialize network manager
            self.network_manager = NetworkManager(self.config, keypair[1].hex())
            await self.network_manager.initialize()
            
            # Start validator node
            await self.validator_node.start()
            
            # Start gRPC server
            self.grpc_server = asyncio.create_task(
                serve_grpc(
                    self.validator_node,
                    self.config,
                    port=50051
                )
            )
            
            # Start REST server
            self.rest_server = asyncio.create_task(
                uvicorn.Server(
                    uvicorn.Config(
                        app,
                        host="0.0.0.0",
                        port=8080,
                        log_level="info"
                    )
                ).serve()
            )
            
            # Start metrics server
            metrics._start_server()
            
            self.running = True
            logger.info("Conductor application started successfully")
            
        except Exception as e:
            logger.error("Failed to start Conductor application", error=str(e))
            raise
            
    async def stop(self):
        """Stop the Conductor application."""
        if not self.running:
            return
            
        logger.info("Stopping Conductor application")
        
        try:
            # Stop REST server
            if self.rest_server:
                self.rest_server.cancel()
                
            # Stop gRPC server
            if self.grpc_server:
                self.grpc_server.cancel()
                
            # Stop network manager
            if self.network_manager:
                await self.network_manager.network.stop()
                
            # Stop validator node
            if self.validator_node:
                # In a real implementation, you'd have a proper shutdown method
                pass
                
            self.running = False
            logger.info("Conductor application stopped")
            
        except Exception as e:
            logger.error("Error stopping Conductor application", error=str(e))
            
    async def _get_or_generate_keypair(self):
        """Get existing keypair or generate new one."""
        from conductor.crypto import ThresholdCrypto
        
        keypair_path = Path(self.config.validator.keypair_path)
        
        if keypair_path.exists():
            # Load existing keypair
            with open(keypair_path, 'rb') as f:
                private_key = f.read()
            # In a real implementation, you'd also load the public key
            public_key = b"loaded_public_key"  # Placeholder
            return (private_key, public_key)
        else:
            # Generate new keypair
            crypto = ThresholdCrypto(n=3, t=2)
            private_key, public_key = crypto.generate_keypair()
            
            # Save keypair
            keypair_path.parent.mkdir(parents=True, exist_ok=True)
            with open(keypair_path, 'wb') as f:
                f.write(private_key)
                
            logger.info("Generated new validator keypair")
            return (private_key, public_key)
            
    def _get_validator_ids(self):
        """Get validator IDs from configuration."""
        # In a real implementation, this would come from configuration
        # For now, return a default set
        return ["validator1", "validator2", "validator3"]


async def main():
    """Main entry point."""
    # Parse command line arguments
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        
    # Create application
    app = ConductorApplication(config_path)
    
    # Set up signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(app.stop())
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start application
        await app.start()
        
        # Keep running until stopped
        while app.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error("Fatal error in main", error=str(e))
        sys.exit(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
