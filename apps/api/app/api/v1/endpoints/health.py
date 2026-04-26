from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/",
    summary="Check API health",
    description="Returns a simple status payload when the API is running.",
)
async def health_check():
    """Return the API health status.

    Returns:
        A small JSON object indicating the API is available.
    """
    return {"status": "ok"}
