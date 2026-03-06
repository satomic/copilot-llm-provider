"""
OpenAI-compatible models listing endpoint.

Implements GET /v1/models following the OpenAI API specification.
Returns the list of available models in OpenAI format.
"""

import logging
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.backend.app.core.auth import AuthInfo, verify_api_key
from src.backend.app.core.dependencies import get_provider
from src.backend.app.providers.base import Provider
from src.backend.app.schemas.openai import (
    ErrorDetail,
    ErrorResponse,
    ModelList,
    ModelObject,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/v1/models",
    response_model=ModelList,
    summary="List available models",
    description="Lists the currently available models. "
    "Compatible with the OpenAI Models API.",
)
async def list_models(
    provider: Provider = Depends(get_provider),
    _auth: AuthInfo = Depends(verify_api_key),
):
    """List available models in OpenAI format.

    Queries the provider for available models and converts them
    to the OpenAI model list format.

    Args:
        provider: The LLM provider (injected).
        _api_key: Verified API key (injected, unused directly).

    Returns:
        OpenAI-format model list response.
    """
    logger.info("Listing available models")

    try:
        models = await provider.list_models()
    except Exception as exc:
        logger.exception("Failed to list models")
        error_resp = ErrorResponse(
            error=ErrorDetail(
                message=str(exc),
                type="server_error",
                code="500",
            )
        )
        return JSONResponse(
            status_code=500,
            content=error_resp.model_dump(),
        )

    created = int(time.time())
    model_objects = [
        ModelObject(
            id=model.id,
            created=created,
            owned_by=model.provider,
            billing_multiplier=model.billing_multiplier,
        )
        for model in models
    ]

    result = ModelList(data=model_objects)
    logger.debug("Returning %d models", len(model_objects))
    return result
