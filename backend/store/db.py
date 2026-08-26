from collections import defaultdict
from copy import deepcopy


TRIPS = {}
PRICE_HISTORY = defaultdict(list)


class PriceRepository:
    def __init__(self, storage):
        self.storage = storage

    def save_snapshot(self, snapshot):
        trip_id = snapshot["trip_id"]
        self.storage[trip_id].append(deepcopy(snapshot))
        return snapshot

    def get_history(self, trip_id):
        return list(self.storage.get(trip_id, []))

    def clear_trip(self, trip_id):
        self.storage[trip_id] = []

    def all_snapshots(self):
        snapshots = []
        for trip_history in self.storage.values():
            snapshots.extend(trip_history)
        return snapshots


PRICE_REPOSITORY = PriceRepository(PRICE_HISTORY)
