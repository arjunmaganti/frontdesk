from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

import core.src.config as config
from core.src.agent.state import AgentState
import core.src.agent.prompt as prompts
from core.src.search.service import query_knowledge_base

def get_llm(temperature=0.0):
    """Returns a ChatGoogleGenerativeAI model instance configured with the tenant's model name."""
    return ChatGoogleGenerativeAI(
        model=config.LLM_MODEL_NAME,
        temperature=temperature
    )

# Node 1: Classifier
def classify_intent_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.0)
    user_message = state["messages"][-1].content
    
    # Run classification
    response = llm.invoke([
        SystemMessage(content=prompts.CLASSIFIER_PROMPT),
        HumanMessage(content=user_message)
    ])
    
    content_str = response.content
    if isinstance(content_str, list):
        content_str = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content_str])
    raw_intent = content_str.strip().lower()
    
    # Guard against LLM formatting deviations
    if "chitchat" in raw_intent:
        intent = "chitchat"
    elif "handoff" in raw_intent:
        intent = "handoff"
    else:
        intent = "kb_query"
        
    return {"intent": intent}

# Node 2: Casual Reply
def casual_reply_node(state: AgentState) -> dict:
    llm = get_llm(temperature=0.5)
    
    # We combine the system prompt with the messages history
    messages_payload = [SystemMessage(content=prompts.CHITCHAT_PROMPT)] + state["messages"]
    response = llm.invoke(messages_payload)
    return {"messages": [response]}

# Node 3: Search & Respond (RAG)
def search_respond_node(state: AgentState) -> dict:
    user_query = state["messages"][-1].content
    
    # 1. Fetch relevant blocks from FAISS
    context = query_knowledge_base(user_query)
    
    # 2. Formulate factual answer
    llm = get_llm(temperature=0.2)
    system_prompt = prompts.RESPONDER_PROMPT.format(context=context)
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ])
    
    return {"messages": [response]}

# Node 4: Handoff
def handoff_node(state: AgentState) -> dict:
    # Return placeholder. The bot middleware will catch this state and alert the admin.
    return {"messages": ["Transferring you to our front desk team. A receptionist will assist you directly!"]}

# Routing decision logic
def route_by_intent(state: AgentState) -> Literal["chitchat", "kb_query", "handoff"]:
    return state["intent"]

# State Graph Construction
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("classifier", classify_intent_node)
workflow.add_node("chitchat", casual_reply_node)
workflow.add_node("kb_query", search_respond_node)
workflow.add_node("handoff", handoff_node)

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
workflow.add_edge("chitchat", END)
workflow.add_edge("kb_query", END)
workflow.add_edge("handoff", END)

# Compile with in-memory checkpointer for session mapping
memory_saver = MemorySaver()
agent_app = workflow.compile(checkpointer=memory_saver)
