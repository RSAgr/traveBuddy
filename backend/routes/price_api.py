import json

from fastapi import APIRouter, HTTPException, Query

from services.api_fetcher import fetch_prices

router = APIRouter()


@router.get("/api/prices")
def paid_price_quote(constraints: str = Query(...), poll_cycle: int = Query(0, ge=0)):
    """Return provider-normalized prices after x402 middleware authorizes it."""
    try:
        parsed = json.loads(constraints)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="constraints must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="constraints must be a JSON object")
    # The resource server is the seller; it must call its local provider rather
    # than recursively attempting to buy its own response.
    return {"components": fetch_prices(parsed, poll_cycle=poll_cycle, use_paid_api=False)}
