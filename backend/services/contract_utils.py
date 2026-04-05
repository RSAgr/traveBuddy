from pyteal import *
from services.algorand_client import algod_client


def approval_program():
    return compileTeal(Approve(), mode=Mode.Application)


def clear_program():
    return compileTeal(Approve(), mode=Mode.Application)


def compile_program(source_code):
    compile_response = algod_client.compile(source_code)
    return bytes.fromhex(compile_response["result"])