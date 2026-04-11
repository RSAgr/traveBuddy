from store.db import TRIPS

def execute_booking(trip_id, components):
    print(f"[BOOKED] Trip {trip_id} with components: {components}")
    if trip_id in TRIPS:
        TRIPS[trip_id]["status"] = "BOOKED"