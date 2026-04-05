import os
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

ALGOD_ADDRESS = os.getenv("ALGOD_ADDRESS")
ALGOD_TOKEN = os.getenv("ALGOD_TOKEN")

algod_client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS)