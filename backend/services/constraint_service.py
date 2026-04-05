import uuid

def create_constraints(user_id, parsed):
    trip_id = str(uuid.uuid4())

    return {
        "trip_id": trip_id,
        "user_id": user_id,
        "budget": parsed["budget"],
        "deadline": parsed["deadline"],
        "transport_modes": parsed["transport_modes"]
    }