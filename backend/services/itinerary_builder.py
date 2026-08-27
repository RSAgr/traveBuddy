from datetime import datetime, timedelta, timezone


def _date_from_deadline(constraints):
    deadline = constraints.get("deadline")
    try:
        deadline_timestamp = int(deadline)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).date()

    if deadline_timestamp > 10_000_000:
        return datetime.fromtimestamp(deadline_timestamp, timezone.utc).date()

    return (datetime.now(timezone.utc) + timedelta(days=deadline_timestamp)).date()


def _component_label(component):
    return component.get("name") or component.get("operator") or component.get("mode", "Option")


def build_booking_itinerary(constraints, selected_components, all_components):
    transport = next((component for component in selected_components if component["type"] == "transport"), None)
    hotel = next((component for component in selected_components if component["type"] == "stay"), None)
    restaurants = [component for component in all_components if component["type"] == "restaurant"][:2]
    activities = [component for component in all_components if component["type"] == "activity"][:3]
    start_date = _date_from_deadline(constraints)
    nights = int(constraints.get("nights") or max(1, int(constraints.get("trip_days", 2)) - 1))
    checkout_date = start_date + timedelta(days=nights)

    timeline = []
    if transport:
        timeline.append({
            "title": f"Board {transport['mode']}: {_component_label(transport)}",
            "date": start_date.isoformat(),
            "time": transport.get("reporting_time") or transport.get("departure_time"),
            "details": [
                f"Boarding point: {transport.get('boarding_point', 'Ranchi')}",
                f"Departure: {transport.get('departure_time', 'TBD')}",
                f"Arrival: {transport.get('arrival_time', 'TBD')}",
                f"Drop point: {transport.get('drop_point', 'Puri')}",
                f"Duration: {transport.get('duration', 'TBD')}",
            ],
            "booking_required": True,
        })

    if hotel:
        timeline.append({
            "title": f"Check in: {_component_label(hotel)}",
            "date": start_date.isoformat(),
            "time": hotel.get("check_in_time", "12:00"),
            "details": [
                f"Room: {hotel.get('room_type', 'Standard room')}",
                f"Area: {hotel.get('area', 'Puri')}",
                f"Check-out: {checkout_date.isoformat()} at {hotel.get('check_out_time', '11:00')}",
                f"Policy: {hotel.get('booking_policy', hotel.get('cancellation', 'Standard policy'))}",
            ],
            "booking_required": True,
        })

    for index, activity in enumerate(activities):
        timeline.append({
            "title": f"Public place: {activity['name']}",
            "date": (start_date + timedelta(days=min(index, nights))).isoformat(),
            "time": activity.get("best_time", "TBD"),
            "details": [
                f"Category: {activity.get('category', 'Sightseeing')}",
                f"Duration: {activity.get('duration', 'TBD')}",
                f"Booking option: {activity.get('booking_option', 'Walk-in')}",
            ],
            "booking_required": activity.get("booking_required", False),
        })

    for index, restaurant in enumerate(restaurants):
        timeline.append({
            "title": f"Meal reservation: {restaurant['name']}",
            "date": (start_date + timedelta(days=min(index, nights))).isoformat(),
            "time": restaurant.get("booking_slot", "Flexible"),
            "details": [
                f"Cuisine: {restaurant.get('cuisine', 'Local')}",
                f"Area: {restaurant.get('area', 'Puri')}",
                f"Must try: {', '.join(restaurant.get('must_try', []))}",
            ],
            "booking_required": restaurant.get("booking_required", False),
        })

    return {
        "route": f"{constraints.get('source', 'Ranchi')} to {constraints.get('destination', 'Puri')}",
        "start_date": start_date.isoformat(),
        "checkout_date": checkout_date.isoformat(),
        "nights": nights,
        "travelers": constraints.get("travelers") or constraints.get("adults") or "as requested",
        "timeline": timeline,
        "bookable_public_places": [
            activity
            for activity in activities
            if activity.get("booking_required")
        ],
        "estimated_total": sum(component["price"] for component in selected_components),
    }
