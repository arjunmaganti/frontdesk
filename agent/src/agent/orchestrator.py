import logging
import json
import re
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

import src.config as config_module
from src.agent.state import AgentState
import src.agent.prompt as prompts
import src.telegram_bot.session as session
from src.search.service import query_knowledge_base
from src.scheduling.cal_service import get_available_slots, create_booking

logger = logging.getLogger(__name__)

def get_llm(temperature=0.0):
    """Returns a ChatGoogleGenerativeAI model instance configured with the tenant's model name."""
    return ChatGoogleGenerativeAI(
        model=config_module.LLM_MODEL_NAME,
        temperature=temperature
    )

# Node 1: Classifier
def classify_intent_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.0)
    user_query = state["messages"][-1].content
    
    # Bypass intent classifier if we are actively in a booking flow
    if state.get("booking_date"):
        query_lower = user_query.lower()
        if any(w in query_lower for w in ["cancel", "nevermind", "stop", "abort", "human", "receptionist", "speak to a person"]):
            return {
                "intent": "handoff" if ("human" in query_lower or "person" in query_lower) else "chitchat",
                "booking_date": None,
                "booking_time": None,
                "client_name": None,
                "client_email": None,
                "client_phone": None
            }
        return {"intent": "booking"}
    
    # Run the classification prompt
    response = llm.invoke([
        SystemMessage(content=prompts.CLASSIFIER_PROMPT),
        HumanMessage(content=user_query)
    ])
    
    content_val = response.content
    if isinstance(content_val, list):
        resp_text = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val])
    else:
        resp_text = str(content_val)
        
    raw_intent = resp_text.strip().lower()
    
    if "handoff" in raw_intent:
        intent = "handoff"
    elif "chitchat" in raw_intent:
        intent = "chitchat"
    elif "booking" in raw_intent:
        intent = "booking"
    else:
        intent = "kb_query"
        
    return {"intent": intent}

# Node 2: Casual Reply
def casual_reply_node(state: AgentState, config: RunnableConfig) -> dict:
    llm = get_llm(temperature=0.5)
    
    business_id = config.get("configurable", {}).get("tenant_id")
    biz_config = session.get_business_config(business_id) if business_id else None
    
    # Fallbacks if business config cannot be loaded
    business_name = biz_config.get("business_name") if biz_config else getattr(config_module, "BUSINESS_NAME", "our business")
    agent_name = biz_config.get("agent_name") if biz_config else getattr(config_module, "AGENT_NAME", "Frontdesk")
    timezone_str = biz_config.get("business_timezone") if biz_config else "America/Los_Angeles"
    
    # Determine the time of day dynamically based on business timezone local time
    from zoneinfo import ZoneInfo
    from datetime import datetime
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles")
        
    hour = datetime.now(tz).hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"
        
    # Format the dynamic system prompt
    formatted_system_prompt = prompts.CHITCHAT_PROMPT.format(
        business_name=business_name,
        time_of_day=time_of_day,
        agent_name=agent_name
    )
    
    # We combine the system prompt with the messages history
    messages_payload = [SystemMessage(content=formatted_system_prompt)] + state["messages"]
    response = llm.invoke(messages_payload)
    return {"messages": [response]}

# Node 3: Search & Respond (RAG)
def search_respond_node(state: AgentState, config: RunnableConfig) -> dict:
    user_query = state["messages"][-1].content
    business_id = config.get("configurable", {}).get("tenant_id")
    
    # 1. Fetch relevant blocks from Supabase pgvector
    context = query_knowledge_base(user_query, business_id)
    
    # 2. Evaluate dynamic business timezone local time
    biz_config = session.get_business_config(business_id) if business_id else None
    timezone_str = biz_config.get("business_timezone") if biz_config else "America/Los_Angeles"
    
    # 3. Prepend deterministic contact profile details to context to prevent hallucinations
    if biz_config:
        profile_context = (
            "BUSINESS PROFILE DETAILS:\n"
            f"- Business Name: {biz_config.get('business_name') or 'Unknown'}\n"
            f"- Receptionist Name: {biz_config.get('agent_name') or 'Frontdesk'}\n"
            f"- Phone: {biz_config.get('business_phone') or 'Not provided'}\n"
            f"- Address: {biz_config.get('business_address') or 'Not provided'}\n"
            f"- Email: {biz_config.get('business_email') or 'Not provided'}\n"
            f"- Website: {biz_config.get('website_url') or 'Not provided'}\n\n"
        )
        context = profile_context + context

    from zoneinfo import ZoneInfo
    from datetime import datetime
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles") # fallback
        
    now = datetime.now(tz)
    current_day = now.strftime("%A")
    current_time = now.strftime("%I:%M %p")
    
    # 4. Formulate factual answer
    llm = get_llm(temperature=0.2)
    system_prompt = prompts.RESPONDER_PROMPT.format(
        context=context,
        current_day=current_day,
        current_time=current_time
    )
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ])
    
    return {"messages": [response]}

# Node 4: Handoff
def handoff_node(state: AgentState) -> dict:
    # Return placeholder. The bot middleware will catch this state and alert the admin.
    return {"messages": ["Transferring you to our front desk team. A receptionist will assist you directly!"]}

# Node 5: Disambiguate
def disambiguate_node(state: AgentState, config: RunnableConfig) -> dict:
    # The last message is the RAG fallback response, so user query is before it
    if len(state["messages"]) >= 2:
        user_query = state["messages"][-2].content
    else:
        user_query = state["messages"][-1].content
        
    business_id = config.get("configurable", {}).get("tenant_id")
    biz_config = session.get_business_config(business_id) if business_id else None
    timezone_str = biz_config.get("business_timezone") if biz_config else "America/Los_Angeles"
    
    from zoneinfo import ZoneInfo
    from datetime import datetime
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles")
        
    now = datetime.now(tz)
    current_day = now.strftime("%A")
    current_time = now.strftime("%I:%M %p")
    
    import os
    # Base dir is /app/agent (Docker) or frontdesk/agent (Local)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    assumptions_path = os.path.join(base_dir, "assumptions.md")
    
    assumptions_content = ""
    if os.path.exists(assumptions_path):
        try:
            with open(assumptions_path, "r", encoding="utf-8") as f:
                assumptions_content = f.read()
        except Exception as e:
            logger.error(f"Error reading assumptions file: {e}")
            
    llm = get_llm(temperature=0.2)
    
    prompt = f"""You are a receptionist assistant helper.
A visitor asked a question, but our main facts didn't have the answer.
Your task is to check if our standard corporate assumptions document contains a default rule or assumption that answers their question.

Visitor's Question: "{user_query}"

CURRENT TIME AT THE BUSINESS:
- Day of Week: {current_day}
- Current Local Time: {current_time}

Corporate Assumptions Document:
{assumptions_content}

Instructions:
1. If the visitor is asking whether the business is open right now, check the default operating hours listed in the Assumptions Document. Compare the current day and local time against the operating hours to determine if we are currently open:
   - If the current local time falls within the open hours, respond politely that we are open right now, and state our daily operating hours.
   - If the current local time falls outside the open hours, respond politely that we are currently closed, state our daily operating hours, and calculate the next day and time we open, returning a friendly note exactly like: "We'll be happy to assist you tomorrow [Next Day] at [Opening Time], looking forward seeing you.." (e.g. if today is Saturday and standard hours are 9:00 AM to 5:00 PM daily, calculate that tomorrow is Sunday opening at 9:00, and include: "We'll be happy to assist you tomorrow Sunday at 9:00, looking forward seeing you..").
2. If the Assumptions Document has another clear, matching default rule that answers the visitor's question, write a friendly, concise receptionist response using that assumption. Do not mention that you are using assumptions or an assumption document.
3. If the Assumptions Document does NOT contain a relevant assumption that answers the visitor's question, you must respond EXACTLY with the fallback message:
"I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."

Response:"""

    response = llm.invoke([
        HumanMessage(content=prompt)
    ])
    
    # Overwrite the fallback message in state instead of appending
    if state["messages"]:
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "id") and last_msg.id:
            response.id = last_msg.id
            
    return {"messages": [response]}

# Node 6: Booking Node (Cal.com integration)
def booking_node(state: AgentState, config: RunnableConfig) -> dict:
    user_query = state["messages"][-1].content
    
    # Retrieve business config for timezone
    business_id = config.get("configurable", {}).get("tenant_id")
    biz_config = session.get_business_config(business_id) if business_id else None
    timezone_str = biz_config.get("business_timezone") if biz_config else "America/Los_Angeles"
    
    from zoneinfo import ZoneInfo
    from datetime import datetime
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("America/Los_Angeles")
        
    current_date = datetime.now(tz).strftime("%Y-%m-%d")
    
    # 1. Run structured extraction to get booking variables from conversation history
    formatted_extract_prompt = prompts.BOOKING_EXTRACTOR_PROMPT.format(current_date=current_date)
    
    llm = get_llm(temperature=0.0)
    extract_response = llm.invoke([
        SystemMessage(content=formatted_extract_prompt)
    ] + state["messages"])
    
    extracted = {}
    try:
        raw_text = extract_response.content.strip()
        # Remove ```json ... ``` wrappers if LLM included them
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        extracted = json.loads(raw_text)
    except Exception as e:
        logger.error(f"Error parsing booking extraction JSON: {e}. Text: {extract_response.content}")
        
    # Merge extracted fields with existing state
    booking_date = extracted.get("booking_date") or state.get("booking_date")
    booking_time_local = extracted.get("booking_time_local") or state.get("booking_time_local")
    client_name = extracted.get("client_name") or state.get("client_name")
    client_email = extracted.get("client_email") or state.get("client_email")
    client_phone = state.get("client_phone")
    
    booking_time_utc = state.get("booking_time")
    slots_context = ""
    
    # 2. Flow routing based on missing details
    if not booking_date:
        slots_context = "Date is not selected yet. Please ask the user what day they'd like to book."
    else:
        # Fetch slots for the date
        slots = get_available_slots(booking_date)
        
        # If time chosen locally, try to match it to a UTC slot
        if booking_time_local and not booking_time_utc:
            matched_slot = None
            for slot in slots:
                user_t = booking_time_local.strip().upper()
                slot_t = slot["local"].strip().upper()
                if user_t in slot_t or slot_t in user_t:
                    matched_slot = slot
                    break
            
            if matched_slot:
                booking_time_utc = matched_slot["utc"]
                booking_time_local = matched_slot["local"] # normalize
            else:
                # Chosen time is invalid/not found in slots
                booking_time_local = None
                
        if not booking_time_local:
            if slots:
                slots_str = "\n".join([f"- {s['local']}" for s in slots])
                slots_context = f"Available time slots on {booking_date}:\n{slots_str}\n\nPlease ask the user to pick one of these specific times."
            else:
                slots_context = f"There are no available appointments on {booking_date}. Please tell the user that no slots are open on this date and ask them to select another day."
        else:
            slots_context = f"Selected date: {booking_date}, time slot: {booking_time_local}."
            
    # 3. Check if all required booking fields are complete. If so, book!
    if booking_date and booking_time_utc and client_name and client_email:
        res = create_booking(booking_time_utc, client_name, client_email)
        if res["status"] == "success":
            business_name = biz_config.get("business_name") if biz_config else getattr(config_module, "BUSINESS_NAME", "our business")
            reply_text = f"🎉 Success! Your appointment has been booked for **{booking_date}** at **{booking_time_local}**.\n\nI have sent a calendar confirmation to **{client_email}**. We look forward to seeing you at {business_name}! 😊"
            return {
                "messages": [AIMessage(content=reply_text)],
                "booking_date": None,
                "booking_time": None,
                "client_name": None,
                "client_email": None,
                "client_phone": None
            }
        else:
            error_msg = res.get("message", "Booking failed.")
            logger.error(f"Booking creation failed via Cal.com: {error_msg}")
            booking_time_local = None
            booking_time_utc = None
            slots_context = f"⚠️ The booking failed: {error_msg}. Please choose another time slot."
            
    # 4. If booking not ready, generate conversational response
    business_name = biz_config.get("business_name") if biz_config else getattr(config_module, "BUSINESS_NAME", "our business")
    agent_name = biz_config.get("agent_name") if biz_config else getattr(config_module, "AGENT_NAME", "Frontdesk")

    receptionist_sys_msg = prompts.BOOKING_RECEPTIONIST_PROMPT.format(
        agent_name=agent_name,
        business_name=business_name,
        booking_date=booking_date or "Not provided",
        booking_time_local=booking_time_local or "Not provided",
        client_name=client_name or "Not provided",
        client_email=client_email or "Not provided",
        slots_context=slots_context
    )
    
    receptionist_llm = get_llm(temperature=0.2)
    response = receptionist_llm.invoke([
        SystemMessage(content=receptionist_sys_msg)
    ] + state["messages"])
    
    return {
        "messages": [response],
        "booking_date": booking_date,
        "booking_time": booking_time_utc,
        "client_name": client_name,
        "client_email": client_email,
        "client_phone": client_phone
    }

# Routing decision logic
def route_by_intent(state: AgentState) -> Literal["chitchat", "kb_query", "handoff", "booking"]:
    return state["intent"]

def check_rag_result(state: AgentState) -> Literal["disambiguate", "end"]:
    if not state["messages"]:
        return "end"
    last_msg = state["messages"][-1].content
    fallback_msg = "I couldn't find the answer to that in our files. Let me escalate this to our staff to help you directly."
    if fallback_msg in last_msg:
        return "disambiguate"
    return "end"

# State Graph Construction
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("classifier", classify_intent_node)
workflow.add_node("chitchat", casual_reply_node)
workflow.add_node("kb_query", search_respond_node)
workflow.add_node("handoff", handoff_node)
workflow.add_node("disambiguate", disambiguate_node)
workflow.add_node("booking", booking_node)

# Link nodes with conditional routing edges
workflow.add_edge(START, "classifier")
workflow.add_conditional_edges(
    "classifier",
    route_by_intent,
    {
        "chitchat": "chitchat",
        "kb_query": "kb_query",
        "handoff": "handoff",
        "booking": "booking"
    }
)
workflow.add_conditional_edges(
    "kb_query",
    check_rag_result,
    {
        "disambiguate": "disambiguate",
        "end": END
    }
)
workflow.add_edge("chitchat", END)
workflow.add_edge("disambiguate", END)
workflow.add_edge("handoff", END)
workflow.add_edge("booking", END)

# Compile with in-memory checkpointer for session mapping
memory_saver = MemorySaver()
agent_app = workflow.compile(checkpointer=memory_saver)
