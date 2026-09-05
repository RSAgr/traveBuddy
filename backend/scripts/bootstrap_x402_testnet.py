"""Create or prepare the two TestNet wallets needed by TraveBuddy x402.

Run once to create wallet secrets, then fund the printed addresses through the
TestNet faucets. Run again with the environment values set to opt both wallets
into TestNet USDC before starting the paid API.
"""

from __future__ import annotations

import os

from algosdk import account, mnemonic
from algosdk.transaction import AssetOptInTxn, wait_for_confirmation
from algosdk.v2client import algod
from dotenv import load_dotenv

USDC_TESTNET_ASA_ID = 10458941
ALGOD_URL = os.getenv("ALGOD_TESTNET_URL", "https://testnet-api.algonode.cloud")


def create_accounts():
    """Print two fresh accounts. Save both mnemonics privately before continuing."""
    agent_private_key, agent_address = account.generate_account()
    seller_private_key, seller_address = account.generate_account()
    print("\nAdd these to backend/.env (do not commit it):\n")
    print("X402_PRICE_API_ENABLED=true")
    print(f"X402_SELLER_ADDRESS={seller_address}")
    print(f'X402_AGENT_MNEMONIC="{mnemonic.from_private_key(agent_private_key)}"')
    print("X402_PRICE_USDC=$0.001")
    print("X402_FACILITATOR_URL=https://facilitator.goplausible.xyz")
    print(f"ALGOD_TESTNET_URL={ALGOD_URL}")
    print("PRICE_API_URL=http://127.0.0.1:4021")
    print("\nFund and opt in both addresses:")
    print(f"  agent/payer: {agent_address}")
    print(f"  seller/receiver: {seller_address}")
    print("\nKeep the seller mnemonic too if you want to use that wallet later:")
    print(mnemonic.from_private_key(seller_private_key))


def opt_in(client, private_key, address, label):
    account_info = client.account_info(address)
    already_opted_in = any(asset["asset-id"] == USDC_TESTNET_ASA_ID for asset in account_info.get("assets", []))
    if already_opted_in:
        print(f"{label} is already opted into TestNet USDC.")
        return

    txn = AssetOptInTxn(address, client.suggested_params(), USDC_TESTNET_ASA_ID)
    txid = client.send_transaction(txn.sign(private_key))
    wait_for_confirmation(client, txid, 4)
    print(f"{label} opted into TestNet USDC: {txid}")


def prepare_accounts():
    agent_mnemonic = os.getenv("X402_AGENT_MNEMONIC")
    seller_mnemonic = os.getenv("X402_SELLER_MNEMONIC")
    if not agent_mnemonic or not seller_mnemonic:
        raise SystemExit(
            "Set X402_AGENT_MNEMONIC and X402_SELLER_MNEMONIC in backend/.env "
            "after funding both accounts with TestNet ALGO."
        )

    client = algod.AlgodClient("", ALGOD_URL)
    agent_private_key = mnemonic.to_private_key(agent_mnemonic)
    seller_private_key = mnemonic.to_private_key(seller_mnemonic)
    opt_in(client, agent_private_key, account.address_from_private_key(agent_private_key), "Agent")
    opt_in(client, seller_private_key, account.address_from_private_key(seller_private_key), "Seller")


if __name__ == "__main__":
    load_dotenv()
    if os.getenv("X402_AGENT_MNEMONIC") and os.getenv("X402_SELLER_MNEMONIC"):
        prepare_accounts()
    else:
        create_accounts()
