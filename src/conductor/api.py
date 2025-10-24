"""API layer for Conductor with gRPC and REST endpoints."""

import asyncio
import grpc.aio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import json

# Import generated protobuf files
import conductor_pb2
import conductor_pb2_grpc

from conductor.errors import (
    ConductorError,
    ConsensusTimeoutError,
    InsufficientValidatorsError,
    InvalidSignatureError
)
from conductor.metrics import metrics
from conductor.logging_config import get_logger

logger = get_logger(__name__)

class ConductorServicer(conductor_pb2_grpc.ConductorServiceServicer):
    """gRPC service implementation for Conductor."""
    
    def __init__(self, validator_node):
        self.validator_node = validator_node
        self.logger = get_logger("ConductorServicer")
        
    async def GetDayProof(self, request: conductor_pb2.GetDayProofRequest, context) -> conductor_pb2.GetDayProofResponse:
        """Get canonical day proof for a given day."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info("GetDayProof request", day_number=request.day_number)
            
            # Get day proof from storage
            day_proof = await self.validator_node.storage.get_proof(request.day_number)
            
            if day_proof is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Day proof not found for day {request.day_number}")
                return conductor_pb2.GetDayProofResponse()
                
            # Record metrics
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("GetDayProof", "success", latency)
            
            return conductor_pb2.GetDayProofResponse(
                day_number=day_proof.day_number,
                vdf_output=day_proof.proof.hex(),
                validator_signatures=[sig.hex() for sig in getattr(day_proof, 'signatures', [])],
                timestamp=int(datetime.now().timestamp())
            )
            
        except Exception as e:
            self.logger.error("GetDayProof error", error=str(e), day_number=request.day_number)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("GetDayProof", "failure", latency)
            
            return conductor_pb2.GetDayProofResponse()

    async def SubmitEventBatch(self, request: conductor_pb2.SubmitEventBatchRequest, context) -> conductor_pb2.SubmitEventBatchResponse:
        """Submit event batch for consensus."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info("SubmitEventBatch request", epoch=request.epoch, event_count=len(request.events))
            
            # Validate request
            if not request.events:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Empty event batch")
                return conductor_pb2.SubmitEventBatchResponse()
                
            # Convert protobuf events to internal format
            events = []
            for event in request.events:
                # Convert protobuf event to internal Event object
                # This is a simplified conversion - in production, you'd have proper mapping
                from conductor.models import Event
                internal_event = Event(
                    creation_day=event.creation_day,
                    sig=event.signature
                )
                events.append(internal_event)
                
            # Submit to consensus
            batch_id = f"batch_{request.epoch}_{hash(str(events)) % 10000}"
            
            # Record metrics
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("SubmitEventBatch", "success", latency)
            
            return conductor_pb2.SubmitEventBatchResponse(
                batch_id=batch_id,
                status="pending"
            )
            
        except ConductorError as e:
            self.logger.error("SubmitEventBatch conductor error", error=str(e))
            context.set_code(grpc.StatusCode.ABORTED)
            context.set_details(str(e))
            
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("SubmitEventBatch", "failure", latency)
            
            return conductor_pb2.SubmitEventBatchResponse()
            
        except Exception as e:
            self.logger.error("SubmitEventBatch error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("SubmitEventBatch", "failure", latency)
            
            return conductor_pb2.SubmitEventBatchResponse()

    async def GetBlock(self, request: conductor_pb2.GetBlockRequest, context) -> conductor_pb2.GetBlockResponse:
        """Get finalized block for an epoch."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info("GetBlock request", epoch=request.epoch)
            
            # Get block from consensus
            block = self.validator_node.consensus.committed_blocks.get(request.epoch)
            
            if block is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Block for epoch {request.epoch} not found")
                return conductor_pb2.GetBlockResponse()
                
            # Record metrics
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("GetBlock", "success", latency)
            
            return conductor_pb2.GetBlockResponse(
                epoch=request.epoch,
                block_hash=block.get("block_digest", ""),
                merkle_root=block.get("merkle_root", ""),
                events=block.get("events", []),
                quorum_cert=block.get("quorum_cert", "")
            )
            
        except Exception as e:
            self.logger.error("GetBlock error", error=str(e), epoch=request.epoch)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("GetBlock", "failure", latency)
            
            return conductor_pb2.GetBlockResponse()

    async def GetConsensusStatus(self, request: conductor_pb2.GetConsensusStatusRequest, context) -> conductor_pb2.GetConsensusStatusResponse:
        """Get consensus status for a batch."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info("GetConsensusStatus request", batch_id=request.batch_id)
            
            # Check if batch is committed
            # This is a simplified implementation
            status = "pending"  # Default status
            
            # Record metrics
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("GetConsensusStatus", "success", latency)
            
            return conductor_pb2.GetConsensusStatusResponse(
                batch_id=request.batch_id,
                status=status
            )
            
        except Exception as e:
            self.logger.error("GetConsensusStatus error", error=str(e), batch_id=request.batch_id)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            
            latency = asyncio.get_event_loop().time() - start_time
            metrics.record_grpc_request("GetConsensusStatus", "failure", latency)
            
            return conductor_pb2.GetConsensusStatusResponse()


async def serve_grpc(validator_node, config, port: int = 50051):
    """Start gRPC server."""
    server = grpc.aio.server()
    
    # Add service
    conductor_pb2_grpc.add_ConductorServiceServicer_to_server(
        ConductorServicer(validator_node), server
    )
    
    # Configure server
    server.add_insecure_port(f'[::]:{port}')
    
    logger.info(f"Starting gRPC server on port {port}")
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down gRPC server")
        await server.stop(grace=5.0)
