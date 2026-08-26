from algosdk import transaction
from algosdk import mnemonic
from algosdk.transaction import ApplicationCreateTxn
from services.algorand_client import algod_client
from services.contract_utils import approval_program, clear_program, compile_program
import os
from dotenv import load_dotenv
from algosdk.transaction import ApplicationNoOpTxn
load_dotenv()  # Load environment variables from .env file


def _user_private_key():
    private_key = os.getenv("USER_PRIVATE_KEY")
    if private_key:
        return private_key

    user_mnemonic = os.getenv("USER_MNEMONIC")
    if user_mnemonic:
        return mnemonic.to_private_key(user_mnemonic)

    raise ValueError("Set USER_PRIVATE_KEY or USER_MNEMONIC in backend/.env")

def call_app(app_id, sender, args):
    params = algod_client.suggested_params()

    txn = ApplicationNoOpTxn(
        sender=sender,
        sp=params,
        index=app_id,
        app_args=args
    )

    signed_txn = txn.sign(_user_private_key())

    tx_id = algod_client.send_transaction(signed_txn)

    return tx_id

def deploy_contract(user_address):

    params = algod_client.suggested_params()

    approval = compile_program(approval_program())
    clear = compile_program(clear_program())

    txn = ApplicationCreateTxn(
        sender=user_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=transaction.StateSchema(6, 2),
        local_schema=transaction.StateSchema(0, 0)
    )

    signed_txn = txn.sign(_user_private_key())

    tx_id = algod_client.send_transaction(signed_txn)

    result = transaction.wait_for_confirmation(algod_client, tx_id, 4)

    app_id = result["application-index"]

    return {
        "app_id": app_id,
        "tx_id": tx_id
    }
