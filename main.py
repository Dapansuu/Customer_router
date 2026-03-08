from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal, TypedDict
from langchain_core.tools import tool
import os


load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found in environment.")


llm = ChatOpenAI(
    model="openai/gpt-4o-mini",
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
    max_tokens=400,
)


@tool
def troubleshoot(issue: str) -> str:
    """Return fake troubleshooting steps for a technical issue."""
    return (
        f"Troubleshooting steps for: {issue}\n"
        "1. Restart the application.\n"
        "2. Clear cache / temporary files.\n"
        "3. Check your internet connection.\n"
        "4. Update the software to the latest version.\n"
        "5. Reinstall the app if the issue persists.\n"
        "6. Escalate to Tier-2 support if unresolved."
    )


tools = [troubleshoot]


class ChatMessage(TypedDict):
    query: str
    customer_name: str
    intent: Literal["billing", "techsupport", "general"]
    final_response: str


class RouteDecision(BaseModel):
    intent: Literal["Billing", "Tech Support", "General"] = Field(
        description="The best category for the user's query."
    )


def router_node(state: ChatMessage) -> dict:
    query = state["query"]

    structured_llm = llm.with_structured_output(RouteDecision)

    decision = structured_llm.invoke(
        f"""
You are a support triage router.

Classify the user query into exactly one category:
- Billing: payments, refunds, invoices, subscriptions, charges
- Tech Support: bugs, crashes, errors, login problems, installation, performance
- General: anything else

Return only one of:
- Billing
- Tech Support
- General

User query: {query}
"""
    )

    label_map = {
        "Billing": "billing",
        "Tech Support": "techsupport",
        "General": "general",
    }

    return {"intent": label_map[decision.intent]}


def techsupport_node(state: ChatMessage) -> dict:
    llm_with_tool = llm.bind_tools(tools)

    ai_msg = llm_with_tool.invoke(
        f"""
You are a technical support assistant.

Customer name: {state["customer_name"]}
The user issue: {state["query"]}

Use the troubleshooting tool to get troubleshooting steps.
"""
    )

    tool_result_text = ""

    if getattr(ai_msg, "tool_calls", None):
        for call in ai_msg.tool_calls:
            if call["name"] == "troubleshoot":
                tool_result_text = troubleshoot.invoke(call["args"])

    if not tool_result_text:
        tool_result_text = troubleshoot.invoke({"issue": state["query"]})

    final = llm.invoke(
        f"""
You are a technical support specialist.

Customer name: {state["customer_name"]}
User issue: {state["query"]}

Tool output:
{tool_result_text}

Write a customer-facing response that:
- addresses the customer by their first name naturally
- acknowledges the issue
- clearly provides the troubleshooting steps
- ends with a polite escalation note if needed
- keep the response short and focused.

Do NOT include:
- email signatures
- placeholders like [Your Name]
- job titles
- sign-offs like "Best regards"

Just provide the response message.
"""
    )

    return {"final_response": final.content}


def billing_node(state: ChatMessage) -> dict:
    ai_msg = llm.invoke(
        f"""
You are a billing support specialist.

Customer name: {state["customer_name"]}
User query: {state["query"]}

Write a concise customer-facing response that:
- addresses the customer by name naturally
- acknowledges the billing issue
- explains likely next steps
- asks for any needed billing details politely
- keep the response short and focused.

Do NOT include:
- email signatures
- placeholders like [Your Name]
- job titles
- sign-offs like "Best regards"

Just provide the response message.
"""
    )
    return {"final_response": ai_msg.content}


def general_node(state: ChatMessage) -> dict:
    ai_msg = llm.invoke(
        f"""
You are a general support specialist.

Customer name: {state["customer_name"]}
User query: {state["query"]}

Write a clear and helpful customer-facing response that addresses the customer by name naturally.
- keep the response short and focused.

Do NOT include:
- email signatures
- placeholders like [Your Name]
- job titles
- sign-offs like "Best regards"

Just provide the response message.
"""
    )
    return {"final_response": ai_msg.content}


def check_intent(state: ChatMessage) -> str:
    return state["intent"]


graph = StateGraph(ChatMessage)

graph.add_node("router", router_node)
graph.add_node("techsupport", techsupport_node)
graph.add_node("billing", billing_node)
graph.add_node("general", general_node)

graph.add_edge(START, "router")

graph.add_conditional_edges(
    "router",
    check_intent,
    {
        "billing": "billing",
        "techsupport": "techsupport",
        "general": "general",
    },
)

graph.add_edge("billing", END)
graph.add_edge("techsupport", END)
graph.add_edge("general", END)

workflow = graph.compile()