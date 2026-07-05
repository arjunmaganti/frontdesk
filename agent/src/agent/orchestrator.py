from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

import src.config as config_module
from src.agent.state import AgentState
import src.agent.prompt as prompts
import src.telegram_bot.session as session
from src.search.service import query_knowledge_base

def get_llm(temperature=0.0):
    """Returns a ChatGoogleGenerativeAI model instance configured with the tenant's model name."""
    return ChatGoogleGenerativeAI(
        model=config_module.LLM_MODEL_NAME,
        temperature=temperature
    )

# Node 1: Classifier
def classify_intent_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.0)
    
    # Run the classification prompt
    user_query = state["messages"][-1].content
    
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
   - If the current local time falls outside the open hours, respond politely that we are currently closed, state our daily operating hours, and offer to help them when we reopen.
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

# Routing decision logic
def route_by_intent(state: AgentState) -> Literal["chitchat", "kb_query", "handoff"]:
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

# Link nodes with conditional routing edges
workflow.add_edge(START, "classifier")
workflow.add_conditional_edges(
    "classifier",
    route_by_intent,
    {
        "chitchat": "chitchat",
        "kb_query": "kb_query",
        "handoff": "handoff"
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

# Compile with in-memory checkpointer for session mapping
memory_saver = MemorySaver()
agent_app = workflow.compile(checkpointer=memory_saver)
