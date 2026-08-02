from fastapi import APIRouter
from easyagents.api.models import ApprovalResponse

router = APIRouter()


@router.get("/{workflow_id}")
async def get_pending(workflow_id: str):
    """View pending approval for a workflow."""
    return {"workflow_id": workflow_id, "pending": []}


@router.post("/{workflow_id}")
async def submit_approval(workflow_id: str, response: ApprovalResponse):
    """Submit approval result to resume graph execution."""
    status = "resumed" if response.approved else "rejected"
    return {"status": status, "workflow_id": workflow_id}
