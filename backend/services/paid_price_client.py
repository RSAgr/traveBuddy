"""Buyer-side x402 client used by the travel agent for paid price searches."""

from __future__ import annotations

import json
import os

from services.x402_algorand import AlgorandPrivateKeySigner, ALGORAND_TESTNET_CAIP2


def fetch_paid_prices(constraints: dict, poll_cycle: int = 0) -> list[dict]:
    resource_url = os.getenv("PRICE_API_URL")
    private_key = os.getenv("X402_AGENT_PRIVATE_KEY")
    mnemonic = os.getenv("X402_AGENT_MNEMONIC")
    if not resource_url or not (private_key or mnemonic):
        raise RuntimeError(
            "Paid price search requires PRICE_API_URL and X402_AGENT_MNEMONIC "
            "(or X402_AGENT_PRIVATE_KEY)."
        )

    import requests
    from algosdk import mnemonic as algo_mnemonic
    from x402 import x402ClientSync
    from x402.http.clients.requests import wrapRequestsWithPayment
    from x402.mechanisms.avm.exact import register_exact_avm_client

    buyer = x402ClientSync()
    register_exact_avm_client(
        buyer, AlgorandPrivateKeySigner(private_key or algo_mnemonic.to_private_key(mnemonic)),
        algod_url=os.getenv("ALGOD_TESTNET_URL", "https://testnet-api.algonode.cloud"),
    )
    session = wrapRequestsWithPayment(requests.Session(), buyer)
    response = session.get(
        resource_url.rstrip("/") + "/api/prices",
        params={"constraints": json.dumps(constraints), "poll_cycle": poll_cycle},
        timeout=float(os.getenv("X402_PRICE_TIMEOUT_SECONDS", "30")),
    )
    response.raise_for_status()
    return response.json()["components"]
