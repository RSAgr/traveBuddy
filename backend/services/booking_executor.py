# The company needs to save the booking information on the blockchain (or for now let us store it locally), and then execute the booking by calling the contract. The contract will verify the booking information and release the funds to the company if the booking is successful.

def execute_booking(trip_id, components):
    print(f"[BOOKED] Trip {trip_id} with components: {components}")