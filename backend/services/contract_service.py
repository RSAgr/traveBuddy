from algosdk import encoding, logic, mnemonic, transaction
from algosdk.transaction import ApplicationCreateTxn, ApplicationNoOpTxn, PaymentTxn
from services.algorand_client import algod_client
from services.contract_utils import approval_program, clear_program, compile_program
import os
import hashlib
import json
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file


APP_ACCOUNT_MIN_BALANCE = 100_000


def _get_private_key():
    private_key = os.getenv("USER_PRIVATE_KEY")
    if private_key:
        return private_key

    user_mnemonic = os.getenv("USER_MNEMONIC")
    if user_mnemonic:
        return mnemonic.to_private_key(user_mnemonic)

    raise ValueError("Missing USER_PRIVATE_KEY or USER_MNEMONIC in environment")


def _suggested_params(fee_multiplier=1):
    params = algod_client.suggested_params()
    params.flat_fee = True
    params.fee = params.min_fee * fee_multiplier
    return params


def _sign_transaction(txn):
    private_key = _get_private_key()
    return txn.sign(private_key)


def _submit_transaction(txn):
    signed_txn = _sign_transaction(txn)
    tx_id = algod_client.send_transaction(signed_txn)
    confirmation = transaction.wait_for_confirmation(algod_client, tx_id, 4)
    return tx_id, confirmation


def _submit_group(txns):
    signed_txns = [_sign_transaction(txn) for txn in txns]
    tx_id = algod_client.send_transactions(signed_txns)
    confirmation = transaction.wait_for_confirmation(algod_client, tx_id, 4)
    return tx_id, confirmation


def _encode_uint64(value):
    value = int(value)
    if value < 0:
        raise ValueError("uint64 value cannot be negative")
    return value.to_bytes(8, "big")


def _encode_address(address):
    if not encoding.is_valid_address(address):
        raise ValueError(f"Invalid Algorand address: {address}")
    return encoding.decode_address(address)


def call_app(app_id, sender, args, fee_multiplier=1):
    if not sender:
        raise ValueError("sender address is required")

    params = _suggested_params(fee_multiplier=fee_multiplier)

    app_args = []
    for arg in args or []:
        app_args.append(arg if isinstance(arg, bytes) else str(arg).encode("utf-8"))

    txn = ApplicationNoOpTxn(
        sender=sender,
        sp=params,
        index=app_id,
        app_args=app_args
    )

    tx_id, _ = _submit_transaction(txn)
    return tx_id


def lock_funds(app_id, sender, amount):
    if amount <= 0:
        raise ValueError("amount must be greater than zero")

    app_address = logic.get_application_address(app_id)
    params = _suggested_params()

    payment_txn = PaymentTxn(
        sender=sender,
        sp=params,
        receiver=app_address,
        amt=amount,
    )
    app_call_txn = ApplicationNoOpTxn(
        sender=sender,
        sp=params,
        index=app_id,
        app_args=[b"lock"],
    )

    group_id = transaction.calculate_group_id([payment_txn, app_call_txn])
    payment_txn.group = group_id
    app_call_txn.group = group_id

    tx_id, _ = _submit_group([payment_txn, app_call_txn])
    return {
        "lock_tx_id": tx_id,
        "app_address": app_address,
    }


def release_funds(app_id, sender):
    return call_app(app_id, sender, ["release"], fee_multiplier=1)


def refund_funds(app_id, sender):
    return call_app(app_id, sender, ["refund"], fee_multiplier=1)


def build_itinerary_hash(trip_id, constraints, components):
    payload = {
        "trip_id": str(trip_id),
        "constraints": constraints,
        "components": components,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def commit_itinerary(app_id, sender, itinerary_hash_hex):
    if not itinerary_hash_hex:
        raise ValueError("itinerary_hash_hex is required")

    hash_bytes = bytes.fromhex(itinerary_hash_hex)
    if len(hash_bytes) != 32:
        raise ValueError("itinerary_hash_hex must be a 32-byte sha256 hex string")

    return call_app(app_id, sender, ["commit_itinerary", hash_bytes], fee_multiplier=1)


def deploy_contract(user_address, budget, trip_id, receiver_address=None, deadline=None):
    if not user_address:
        raise ValueError("user_address is required to deploy contract")
    if budget is None:
        raise ValueError("budget is required to deploy contract")
    if not trip_id:
        raise ValueError("trip_id is required to deploy contract")

    receiver_address = receiver_address or user_address
    if not encoding.is_valid_address(receiver_address):
        raise ValueError("receiver_address must be a valid Algorand address")
    if deadline is None:
        raise ValueError("deadline is required to deploy contract")

    params = _suggested_params()

    approval = compile_program(approval_program())
    clear = compile_program(clear_program())

    txn = ApplicationCreateTxn(
        sender=user_address,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        app_args=[
            _encode_uint64(budget),
            _encode_address(receiver_address),
            str(trip_id).encode("utf-8"),
            _encode_uint64(deadline),
            _encode_uint64(APP_ACCOUNT_MIN_BALANCE),
        ],
        global_schema=transaction.StateSchema(6, 4),
        local_schema=transaction.StateSchema(0, 0)
    )

    create_tx_id, result = _submit_transaction(txn)

    app_id = result.get("application-index")
    if not app_id:
        raise RuntimeError("Contract deployed but no application-index returned")

    lock_amount = int(budget) + APP_ACCOUNT_MIN_BALANCE
    lock_result = lock_funds(app_id, user_address, lock_amount)
    app_address = lock_result["app_address"]

    print(f"Contract deployed with app_id: {app_id}, tx_id: {create_tx_id}")
    print(
        f"On-chain trip identifiers -> trip_id: {trip_id}, app_id: {app_id}, app_address: {app_address}"
    )
    return {
        "app_id": app_id,
        "app_address": app_address,
        "create_tx_id": create_tx_id,
        "lock_tx_id": lock_result["lock_tx_id"],
        "lock_amount": lock_amount,
        "receiver_address": receiver_address,
    }