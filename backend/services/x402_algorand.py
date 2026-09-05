"""x402 configuration and buyer helpers for Algorand TestNet."""

from __future__ import annotations

import base64
import os

from algosdk import account, encoding
from dotenv import load_dotenv

load_dotenv()

ALGORAND_TESTNET_CAIP2 = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
USDC_TESTNET_ASA_ID = 10458941


class AlgorandPrivateKeySigner:
    """Adapter from an Algorand private key to x402's AVM signer protocol."""

    def __init__(self, private_key: str):
        self._private_key = private_key
        self._address = account.address_from_private_key(private_key)

    @property
    def address(self) -> str:
        return self._address

    def sign_transactions(self, unsigned_txns: list[bytes], indexes_to_sign: list[int]):
        signed = []
        indexes = set(indexes_to_sign)
        for index, raw_txn in enumerate(unsigned_txns):
            if index not in indexes:
                signed.append(None)
                continue
            txn = encoding.msgpack_decode(base64.b64encode(raw_txn).decode("ascii"))
            signed_txn = txn.sign(self._private_key)
            signed.append(base64.b64decode(encoding.msgpack_encode(signed_txn)))
        return signed


def configure_price_payment(app):
    """Attach genuine x402 AVM middleware when the seller wallet is configured."""
    if os.getenv("X402_PRICE_API_ENABLED", "false").lower() != "true":
        return False

    pay_to = os.getenv("X402_SELLER_ADDRESS")
    if not pay_to:
        raise RuntimeError("X402_SELLER_ADDRESS is required when X402_PRICE_API_ENABLED=true")

    from x402 import x402ResourceServer
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
    from x402.http.middleware.fastapi import payment_middleware
    from x402.http.types import RouteConfig
    from x402.mechanisms.avm.exact import register_exact_avm_server

    facilitator = HTTPFacilitatorClient(FacilitatorConfig(
        url=os.getenv("X402_FACILITATOR_URL", "https://facilitator.goplausible.xyz"),
    ))
    server = register_exact_avm_server(x402ResourceServer(facilitator), ALGORAND_TESTNET_CAIP2)
    route = RouteConfig(
        accepts=PaymentOption(
            scheme="exact", network=ALGORAND_TESTNET_CAIP2, pay_to=pay_to,
            price=os.getenv("X402_PRICE_USDC", "$0.001"),
            extra={"asset": USDC_TESTNET_ASA_ID},
        ),
        description="Live travel-price quotes for one itinerary search",
        mime_type="application/json",
    )
    app.middleware("http")(payment_middleware(
        routes={"GET /api/prices": route}, server=server,
    ))
    return True
