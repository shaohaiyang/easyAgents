from fastapi import APIRouter
from easyagents.api.models import RollbackRequest
from easyagents import CheckpointManager

router = APIRouter()
_checkpoint_mgr = CheckpointManager()


@router.get("/{workflow_id}")
async def list_checkpoints(workflow_id: str):
    ids = await _checkpoint_mgr.list_checkpoints(workflow_id)
    return {"checkpoints": ids}


@router.post("/rollback")
async def rollback(req: RollbackRequest):
    cp = await _checkpoint_mgr.load(req.checkpoint_id)
    if not cp:
        return {"status": "not_found"}
    return {"status": "rolled_back", "node_name": cp.node_name}
