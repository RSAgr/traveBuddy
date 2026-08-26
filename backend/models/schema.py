from pydantic import BaseModel
from typing import List, Optional

class UserQuery(BaseModel):
    user_id: str
    query: str

class Constraint(BaseModel):
    trip_id: str
    user_id: str
    budget: int
    deadline: int
    transport_modes: List[str]

class Component(BaseModel):
    type: str
    mode: str
    price: int

class TripState(BaseModel):
    trip_id: str
    constraints: Constraint
    status: str  # PENDING, ACTIVE, EXECUTED