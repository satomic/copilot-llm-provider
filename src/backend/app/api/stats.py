"""
Usage statistics endpoints.
"""

from fastapi import APIRouter, Depends

from backend.app.core.auth import AuthInfo, verify_api_key
from backend.app.services.usage_tracker import get_usage_tracker

router = APIRouter(prefix="/api/stats", tags=["Stats"])


@router.get("")
async def get_usage_stats(_auth: AuthInfo = Depends(verify_api_key)):
    """Get usage statistics per model and daily breakdown."""
    tracker = get_usage_tracker()
    return tracker.get_stats()
