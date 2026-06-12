# agent.py

import os
from typing import TypedDict
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from gmail_tool import fetch_relevant_emails, extract_bill_details

load_dotenv()


# ── 1. STATE ─────────────────────────────────────────────────────────────────

class EmailState(TypedDict):
    raw_email:      str
    email_id:       str
    subject:        str
    company:        str
    amount:         str
    due_date:       str
    category:       str
    urgency:        str
    confidence:     str
    human_approved: bool
    action_taken:   str


# ── 2. NODES ──────────────────────────────────────────────────────────────────

def read_email(state: EmailState) -> EmailState:
    """
    Email is already loaded into state before graph runs.
    This node just confirms and prints what it received.
    """
    print(f"\n[NODE] read_email")
    print(f"  Subject : {state['subject']}")
    print(f"  Preview : {state['raw_email'][:80]}...")
    return state


def classify_email(state: EmailState) -> EmailState:
    print(f"\n[NODE] classify_email")

    if not state.get("raw_email"):
        state["category"] = "other"
        return state

    details = extract_bill_details(state["raw_email"])

    state["company"]    = details.get("company")   or "Unknown"
    state["amount"]     = details.get("amount")    or "Unknown"
    state["due_date"]   = details.get("due_date")  or "Unknown"
    state["category"]   = details.get("category")  or "other"
    state["urgency"]    = details.get("urgency")   or "medium"
    state["confidence"] = details.get("confidence") or "low"

    print(f"  Company    : {state['company']}")
    print(f"  Amount     : {state['amount']}")
    print(f"  Due date   : {state['due_date']}")
    print(f"  Category   : {state['category']}")
    print(f"  Urgency    : {state['urgency']}")
    print(f"  Confidence : {state['confidence']}")
    return state


def send_subscription_reminder(state: EmailState) -> EmailState:
    print(f"\n[NODE] send_subscription_reminder")
    print()
    print("=" * 50)
    print("  SUBSCRIPTION REMINDER")
    print("=" * 50)
    print(f"  Company      : {state['company']}")
    print(f"  Amount       : {state['amount']}")
    print(f"  Renewal date : {state['due_date']}")
    print("-" * 50)
    print("  Action: Review if you still need this.")
    print("=" * 50)

    state["action_taken"] = f"subscription_reminder_shown: {state['company']}"
    return state


def send_bill_notification(state: EmailState) -> EmailState:
    print(f"\n[NODE] send_bill_notification")
    print()
    print("=" * 50)
    print("  BILL REMINDER")
    print("=" * 50)
    print(f"  Company      : {state['company']}")
    print(f"  Amount due   : {state['amount']}")
    print(f"  Due date     : {state['due_date']}")
    print(f"  Urgency      : {state['urgency'].upper()}")
    print("-" * 50)
    print("  Action: Payment coming up — plan accordingly.")
    print("=" * 50)

    state["action_taken"] = f"bill_notification_shown: {state['company']} {state['amount']}"
    return state


def human_approval(state: EmailState) -> EmailState:
    print(f"\n[NODE] human_approval — waiting for input...")
    print(f"  URGENT: {state['company']} — {state['amount']} due {state['due_date']}")
    state["action_taken"] = f"Recieved Human Action: {state['company']} {state['amount']}"
    return state




# ── 3. ROUTING ────────────────────────────────────────────────────────────────

def route_by_category(state: EmailState) -> str:
    category = state.get("category", "other")
    print(f"\n[ROUTE] category = {category}")

    if category == "bill":
        return "route_urgency"
    elif category == "subscription":
        return "send_subscription_reminder"
    else:
        return END


def route_by_urgency(state: EmailState) -> str:
    urgency = state.get("urgency", "medium")
    print(f"[ROUTE] urgency = {urgency}")

    if urgency == "urgent":
        return "human_approval"
    else:
        return "send_bill_notification"


def route_urgency(state: EmailState) -> EmailState:
    return state


# ── 4. BUILD GRAPH ────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(EmailState)

    builder.add_node("read_email",                 read_email)
    builder.add_node("classify_email",             classify_email)
    builder.add_node("route_urgency",              route_urgency)
    builder.add_node("send_subscription_reminder", send_subscription_reminder)
    builder.add_node("send_bill_notification",     send_bill_notification)
    builder.add_node("human_approval",             human_approval)
   

    builder.set_entry_point("read_email")

    builder.add_edge("read_email", "classify_email")

    builder.add_conditional_edges(
        "classify_email",
        route_by_category,
        {
            "route_urgency":               "route_urgency",
            "send_subscription_reminder":  "send_subscription_reminder",
            END:                           END,
        }
    )

    builder.add_conditional_edges(
        "route_urgency",
        route_by_urgency,
        {
            "human_approval":          "human_approval",
            "send_bill_notification":  "send_bill_notification",
        }
    )

    builder.add_edge("send_subscription_reminder", END)
    builder.add_edge("send_bill_notification",      END)
    builder.add_edge("human_approval",              END)
    

    memory = MemorySaver()
    graph  = builder.compile(
        checkpointer=memory,
        interrupt_before=["human_approval"]
    )


    mermaid_png = graph.get_graph().draw_mermaid_png()
    with open("agent_diagram.png", "wb") as f:
        f.write(mermaid_png)
    
    print("\n✅ Diagram saved to: agent_diagram.png  (open it manually)")

    return graph

def process_email(graph, email: dict, thread_id: str):

    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "raw_email":      f"From: {email['sender']}\nSubject: {email['subject']}\nDate: {email['date']}\n\n{email['body']}",
        "email_id":       email["id"],
        "subject":        email["subject"],
        "company":        "",
        "amount":         "",
        "due_date":       "",
        "category":       "",
        "urgency":        "",
        "confidence":     "",
        "human_approved": False,
        "action_taken":   "",
    }

    for event in graph.invoke(initial_state, config):
     pass  

    snapshot = graph.get_state(config)

    if snapshot.next == ("human_approval",):
        state_vals = snapshot.values
        print(f"\n{'=' * 50}")
        print(f"  URGENT BILL — approval needed")
        print(f"  Company : {state_vals.get('company')}")
        print(f"  Amount  : {state_vals.get('amount')}")
        print(f"  Due     : {state_vals.get('due_date')}")
        print(f"{'=' * 50}")
        print(f"  Action taken? (y/n): ", end="")

        answer = input().strip().lower()
        graph.update_state(config, {"human_approved": answer == "y"})

        for event in graph.stream(None, config):
            pass

    # mark_as_read(email["id"])  ← removed

    final = graph.get_state(config).values
    return final.get("action_taken", "")


# ── 6. MAIN — loop through all emails ────────────────────────────────────────

if __name__ == "__main__":
    import time

    print("=" * 50)
    print("  Email Agent Starting")
    print("=" * 50)

    # fetch all relevant emails at once
    t0     = time.time()
    emails = fetch_relevant_emails(max_scan=50)
    t1     = time.time()

    if not emails:
        print("\n  No bills or subscriptions found. All clear!")
        exit()

    print(f"\n  Found {len(emails)} relevant email(s) in {t1 - t0:.2f}s")
    print(f"  Processing each one...\n")

    graph   = build_graph()
    results = []

    # process each email with its own thread_id so states don't mix
    for i, email in enumerate(emails):
        thread_id = f"email-thread-{i+1}"

        print(f"\n{'#' * 50}")
        print(f"  EMAIL {i+1} of {len(emails)}")
        print(f"{'#' * 50}")

        action = process_email(graph, email, thread_id)
        results.append({
            "subject": email["subject"],
            "action":  action
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 50}")
    print(f"  SUMMARY — {len(results)} email(s) processed")
    print(f"{'=' * 50}")

    for i, r in enumerate(results):
        print(f"  {i+1}. {r['subject'][:45]:<45} → {r['action']}")

    print(f"\n  Total time: {time.time() - t0:.2f}s")
    print("=" * 50)