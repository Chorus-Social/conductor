"""REST API wrapper for Conductor."""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from conductor.errors import ConductorError
from conductor.metrics import metrics
from conductor.logging_config import get_logger

logger = get_logger(__name__)

# Pydantic models for REST API
class DayProofResponse(BaseModel):
    day_number: int
    vdf_output: str
    validator_signatures: List[str]
    timestamp: int

class EventBatchRequest(BaseModel):
    epoch: int
    events: List[Dict[str, Any]]

class EventBatchResponse(BaseModel):
    batch_id: str
    status: str

class BlockResponse(BaseModel):
    epoch: int
    block_hash: str
    merkle_root: str
    events: List[str]
    quorum_cert: str

class ConsensusStatusResponse(BaseModel):
    batch_id: str
    status: str

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: int
    uptime_seconds: float

class MetricsResponse(BaseModel):
    metrics: Dict[str, Any]

# Global validator node reference
validator_node = None

def set_validator_node(node):
    """Set the validator node instance."""
    global validator_node
    validator_node = node

def get_validator_node():
    """Get the validator node instance."""
    if validator_node is None:
        raise HTTPException(status_code=503, detail="Validator node not available")
    return validator_node

# Create FastAPI app
app = FastAPI(
    title="Conductor API",
    version="1.0.0",
    description="REST API for Chorus Conductor",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = asyncio.get_event_loop().time()
    response = await call_next(request)
    process_time = asyncio.get_event_loop().time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        node = get_validator_node()
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=int(datetime.now().timestamp()),
            uptime_seconds=0.0  # Would track actual uptime in production
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.get("/health/ready")
async def readiness_check():
    """Readiness probe for Kubernetes."""
    try:
        node = get_validator_node()
        # Check if node is ready (has peers, storage accessible, etc.)
        if node.network and node.network.get_peer_count() > 0:
            return {"status": "ready"}
        else:
            raise HTTPException(status_code=503, detail="Not ready")
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Not ready")

@app.get("/day-proof/{day_number}", response_model=DayProofResponse)
async def get_day_proof(day_number: int):
    """Get canonical day proof for a given day."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        logger.info("REST GetDayProof request", day_number=day_number)
        
        node = get_validator_node()
        day_proof = await node.storage.get_proof(day_number)
        
        if day_proof is None:
            raise HTTPException(status_code=404, detail=f"Day proof not found for day {day_number}")
            
        # Record metrics
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("day-proof", "GET", "success", latency)
        
        return DayProofResponse(
            day_number=day_proof.day_number,
            vdf_output=day_proof.proof.hex(),
            validator_signatures=[sig.hex() for sig in getattr(day_proof, 'signatures', [])],
            timestamp=int(datetime.now().timestamp())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("REST GetDayProof error", error=str(e), day_number=day_number)
        
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("day-proof", "GET", "failure", latency)
        
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/events/batch", response_model=EventBatchResponse)
async def submit_event_batch(request: EventBatchRequest):
    """Submit event batch for consensus."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        logger.info("REST SubmitEventBatch request", epoch=request.epoch, event_count=len(request.events))
        
        node = get_validator_node()
        
        # Validate request
        if not request.events:
            raise HTTPException(status_code=400, detail="Empty event batch")
            
        # Convert to internal format
        from conductor.models import Event, EventBatch
        events = []
        for event_data in request.events:
            event = Event(
                creation_day=event_data.get('creation_day', 0),
                sig=event_data.get('signature', '')
            )
            events.append(event)
            
        batch = EventBatch(events=events)
        
        # Submit to consensus (simplified)
        batch_id = f"batch_{request.epoch}_{hash(str(events)) % 10000}"
        
        # Record metrics
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("events/batch", "POST", "success", latency)
        
        return EventBatchResponse(
            batch_id=batch_id,
            status="pending"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("REST SubmitEventBatch error", error=str(e))
        
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("events/batch", "POST", "failure", latency)
        
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/block/{epoch}", response_model=BlockResponse)
async def get_block(epoch: int):
    """Get finalized block for an epoch."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        logger.info("REST GetBlock request", epoch=epoch)
        
        node = get_validator_node()
        block = node.consensus.committed_blocks.get(epoch)
        
        if block is None:
            raise HTTPException(status_code=404, detail=f"Block for epoch {epoch} not found")
            
        # Record metrics
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("block", "GET", "success", latency)
        
        return BlockResponse(
            epoch=epoch,
            block_hash=block.get("block_digest", ""),
            merkle_root=block.get("merkle_root", ""),
            events=block.get("events", []),
            quorum_cert=block.get("quorum_cert", "")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("REST GetBlock error", error=str(e), epoch=epoch)
        
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("block", "GET", "failure", latency)
        
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/consensus/status/{batch_id}", response_model=ConsensusStatusResponse)
async def get_consensus_status(batch_id: str):
    """Get consensus status for a batch."""
    start_time = asyncio.get_event_loop().time()
    
    try:
        logger.info("REST GetConsensusStatus request", batch_id=batch_id)
        
        # Simplified status check
        status = "pending"  # Would check actual status in production
        
        # Record metrics
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("consensus/status", "GET", "success", latency)
        
        return ConsensusStatusResponse(
            batch_id=batch_id,
            status=status
        )
        
    except Exception as e:
        logger.error("REST GetConsensusStatus error", error=str(e), batch_id=batch_id)
        
        latency = asyncio.get_event_loop().time() - start_time
        metrics.record_rest_request("consensus/status", "GET", "failure", latency)
        
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    """Get Prometheus metrics."""
    try:
        # In a real implementation, you'd return actual Prometheus metrics
        # For now, return a simple JSON response
        return {
            "metrics": {
                "conductor_consensus_rounds_total": 0,
                "conductor_vdf_computation_duration_seconds": 0,
                "conductor_peer_connections": 0
            }
        }
    except Exception as e:
        logger.error("Metrics endpoint error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Conductor API",
        "version": "1.0.0",
        "description": "REST API for Chorus Conductor",
        "endpoints": {
            "health": "/health",
            "day_proof": "/day-proof/{day_number}",
            "submit_batch": "/events/batch",
            "get_block": "/block/{epoch}",
            "consensus_status": "/consensus/status/{batch_id}",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }

# Error handlers
@app.exception_handler(ConductorError)
async def conductor_error_handler(request: Request, exc: ConductorError):
    """Handle Conductor-specific errors."""
    logger.error("Conductor error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": "ConductorError"}
    )

@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """Handle general errors."""
    logger.error("Unhandled error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": "InternalError"}
    )
