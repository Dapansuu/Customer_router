from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal, TypedDict
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
import json
import os
from ddgs import DDGS


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
    streaming=True,
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

@tool
def recommendation(issue: str) -> str:
    """
    Search the web for recommendations based on the user's query.
    Use for recommendation/suggestion queries only.
    always give the latest information
    give prices in INR
    """
    try:
        results_text = []
        with DDGS() as ddgs:
            results = list(ddgs.text(issue, max_results=5))

        if not results:
            return "No web recommendations found."

        for i, item in enumerate(results, 1):
            title = item.get("title", "No title")
            body = item.get("body", "No description")
            href = item.get("href", "")
            results_text.append(
                f"{i}. {title}\nDescription: {body}\nLink: {href}"
            )

        return "\n\n".join(results_text)

    except Exception as e:
        return f"Recommendation search failed: {str(e)}"

tools = [troubleshoot, recommendation]


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
    llm_with_tool = llm.bind_tools([troubleshoot])

    messages = [
        HumanMessage(
            content=f"""
You are a technical support assistant for a pc company.
Resolve customer needs for tech support related to PCs and laptops.

Customer name: {state["customer_name"]}
User issue: {state["query"]}

Use the troubleshooting tool to get troubleshooting steps.
"""
        )
    ]

    ai_msg = llm_with_tool.invoke(messages)
    messages.append(ai_msg)

    if getattr(ai_msg, "tool_calls", None):
        for call in ai_msg.tool_calls:
            if call["name"] == "troubleshoot":
                tool_output = troubleshoot.invoke(call["args"])
                messages.append(
                    ToolMessage(
                        content=tool_output,
                        tool_call_id=call["id"],
                    )
                )

        final = llm_with_tool.invoke(messages)

    else:
        tool_output = troubleshoot.invoke({"issue": state["query"]})
        messages.append(
            ToolMessage(
                content=tool_output,
                tool_call_id="manual_troubleshoot_call",
            )
        )
        final = llm.invoke(
            f"""
You are a technical support specialist.

Customer name: {state["customer_name"]}
User issue: {state["query"]}

Tool output:
{tool_output}

Write a customer-facing response that:
- addresses the customer by their first name naturally
- acknowledges the issue
- clearly provides the troubleshooting steps
- ends with a polite escalation note if needed
- keep the response short and focused

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
You are a billing support specialist for a pc company.
resolve customer queries on billing related to pcs, laptops

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
    llm_with_tool = llm.bind_tools([recommendation])

    messages = [
        HumanMessage(
            content=f"""
You are a general support specialist for a pc company, with a focus on customer service.
Resolve customer queries related to pcs and laptops in general.

Customer name: {state["customer_name"]}
User query: {state["query"]}

Rules:
- Keep the response short and focused.
- If the user is asking for recommendations or suggestions, you MUST use the recommendation tool.
- Do not answer recommendation questions from memory.
- Address the customer by name naturally.

Do NOT include:
- email signatures
- placeholders like [Your Name]
- job titles
- sign-offs like "Best regards"

Just provide the response message.
"""
        )
    ]

    ai_msg = llm_with_tool.invoke(messages)
    messages.append(ai_msg)

    if getattr(ai_msg, "tool_calls", None):
        for call in ai_msg.tool_calls:
            if call["name"] == "recommendation":
                tool_output = recommendation.invoke(call["args"])
                messages.append(
                    ToolMessage(
                        content=tool_output,
                        tool_call_id=call["id"],
                    )
                )

        final = llm_with_tool.invoke(messages)
        return {"final_response": final.content}

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