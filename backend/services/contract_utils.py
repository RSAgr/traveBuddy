import base64

from pyteal import *
from services.algorand_client import algod_client

# There need to be a contract to lock the funds, and to release the fund...should we verify the booking?

def approval_program():
    return compileTeal(Approve(), mode=Mode.Application)


def clear_program():
    return compileTeal(Approve(), mode=Mode.Application)


def compile_program(source_code):
    try:
        compile_response = algod_client.compile(source_code)
        # Algod returns base64-encoded program bytes.
        return base64.b64decode(compile_response["result"])
    except Exception as exc:
        raise RuntimeError(f"Failed to compile TEAL program: {exc}") from exc