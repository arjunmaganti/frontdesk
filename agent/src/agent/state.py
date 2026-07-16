from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Annotating messages with add_messages ensures new messages append to the list rather than overwriting it
    messages: Annotated[list, add_messages]
    
    # Store the classified intent: "chitchat" | "kb_query" | "handoff" | "booking"
    intent: str
    
    # Store scheduling conversation variables
    booking_date: str     # YYYY-MM-DD
    booking_time: str     # ISO UTC timestamp
    client_name: str
    client_email: str
    client_phone: str
