import re
import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from typing import List, Tuple, Optional

from main import workflow


st.set_page_config(
    page_title="Customer Support Router",
    page_icon="🎫",
    layout="wide",
)

DB_PATH = "tickets.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute("PRAGMA table_info(tickets)")
    cols = [row[1] for row in cur.fetchall()]

    if "customer_name" not in cols:
        cur.execute(
            "ALTER TABLE tickets ADD COLUMN customer_name TEXT NOT NULL DEFAULT 'Customer'"
        )

    if "phone_number" not in cols:
        cur.execute(
            "ALTER TABLE tickets ADD COLUMN phone_number TEXT NOT NULL DEFAULT ''"
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            intent TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


def create_ticket(customer_name: str, phone_number: str) -> str:
    ticket_id = str(uuid.uuid4())
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tickets (ticket_id, customer_name, phone_number, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            ticket_id,
            customer_name,
            phone_number,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()
    return ticket_id


def ticket_exists(ticket_id: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM tickets WHERE ticket_id = ?", (ticket_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_ticket_details(ticket_id: str) -> Tuple[Optional[str], Optional[str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT customer_name, phone_number FROM tickets WHERE ticket_id = ?",
        (ticket_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        return row[0], row[1]
    return None, None


def save_message(ticket_id: str, role: str, content: str, intent: Optional[str] = None) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (ticket_id, role, content, intent, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ticket_id,
            role,
            content,
            intent,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def load_messages(ticket_id: str) -> List[Tuple[str, str, Optional[str], str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT role, content, intent, created_at
        FROM messages
        WHERE ticket_id = ?
        ORDER BY id ASC
        """,
        (ticket_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def is_valid_phone(phone_number: str) -> bool:
    pattern = r"^\+?[0-9\s\-()]{7,20}$"
    return bool(re.match(pattern, phone_number))


def init_session() -> None:
    defaults = {
        "logged_in": False,
        "current_ticket_id": None,
        "customer_name": None,
        "phone_number": None,
        "chat_history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def login_with_ticket(ticket_id: str) -> None:
    customer_name, phone_number = get_ticket_details(ticket_id)

    st.session_state.logged_in = True
    st.session_state.current_ticket_id = ticket_id
    st.session_state.customer_name = customer_name or "Customer"
    st.session_state.phone_number = phone_number or ""
    st.session_state.chat_history = []

    rows = load_messages(ticket_id)
    for role, content, intent, created_at in rows:
        st.session_state.chat_history.append(
            {
                "role": role,
                "content": content,
                "intent": intent,
                "created_at": created_at,
            }
        )


def logout() -> None:
    st.session_state.logged_in = False
    st.session_state.current_ticket_id = None
    st.session_state.customer_name = None
    st.session_state.phone_number = None
    st.session_state.chat_history = []


init_db()
init_session()


if not st.session_state.logged_in:
    st.title("🎫 Customer Support Router")
    st.caption("Create a new ticket or load an existing one.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Create New Ticket")

        form_col1, form_col2 = st.columns(2)
        with form_col1:
            new_customer_name = st.text_input(
                "Customer Name",
                placeholder="Enter your name",
                key="new_customer_name",
            )
        with form_col2:
            new_phone_number = st.text_input(
                "Phone Number",
                placeholder="+91 9876543210",
                key="new_phone_number",
            )

        if st.button("Create New Ticket", use_container_width=True):
            customer_name = new_customer_name.strip()
            phone_number = new_phone_number.strip()

            if not customer_name:
                st.warning("Please enter your name.")
            elif not phone_number:
                st.warning("Please enter your phone number.")
            elif not is_valid_phone(phone_number):
                st.warning("Please enter a valid phone number.")
            else:
                new_ticket = create_ticket(customer_name, phone_number)
                login_with_ticket(new_ticket)
                st.success("New ticket created.")
                st.rerun()

    with col2:
        st.subheader("Load Existing Ticket")
        existing_ticket_id = st.text_input(
            "Ticket ID",
            placeholder="Enter your UUID ticket ID",
        )

        if st.button("Load Ticket", use_container_width=True):
            ticket_id = existing_ticket_id.strip()

            if not ticket_id:
                st.warning("Please enter a ticket ID.")
            elif not ticket_exists(ticket_id):
                st.error("Ticket not found.")
            else:
                login_with_ticket(ticket_id)
                st.success("Ticket loaded successfully.")
                st.rerun()

    st.stop()


with st.sidebar:
    st.title("Session")

    st.markdown("### Customer")
    st.write(st.session_state.customer_name)

    st.markdown("### Phone")
    st.write(st.session_state.phone_number or "Not available")

    st.markdown("### Ticket")
    st.code(st.session_state.current_ticket_id, language=None)

    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()


st.title("Customer Support Router")
st.caption(f"Welcome, {st.session_state.customer_name}.")

st.info(
    f"Customer: `{st.session_state.customer_name}`  \n"
    f"Phone: `{st.session_state.phone_number}`  \n"
    f"Ticket ID: `{st.session_state.current_ticket_id}`"
)

for msg in st.session_state.chat_history:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["content"])


user_query = st.chat_input("Describe your issue...")

if user_query:
    ticket_id = st.session_state.current_ticket_id

    with st.chat_message("user"):
        st.markdown(user_query)

    save_message(ticket_id, "user", user_query)

    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": user_query,
            "intent": None,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        intent_placeholder = st.empty()

        try:
            initial_state = {
                "query": user_query,
                "customer_name": st.session_state.customer_name,
                "intent": "general",
                "final_response": "",
            }

            streamed_text = ""
            detected_intent = "general"

            for chunk in workflow.stream(initial_state, stream_mode="messages"):
                message, metadata = chunk

                # collect token/content chunks from AI messages
                if hasattr(message, "content") and message.content:
                    if isinstance(message.content, str):
                        streamed_text += message.content
                    elif isinstance(message.content, list):
                        for item in message.content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                streamed_text += item.get("text", "")
                            elif isinstance(item, str):
                                streamed_text += item

                    response_placeholder.markdown(streamed_text)

                # try to capture intent from metadata if available
                if isinstance(metadata, dict):
                    if "intent" in metadata:
                        detected_intent = metadata["intent"]

            # final fallback in case stream did not expose full state
            final_result = workflow.invoke(initial_state)
            final_text = final_result.get("final_response", streamed_text).strip()
            detected_intent = final_result.get("intent", detected_intent)

            response_placeholder.markdown(final_text)
            intent_placeholder.caption(f"Intent: {detected_intent}")

            save_message(ticket_id, "assistant", final_text, detected_intent)

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": final_text,
                    "intent": detected_intent,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

        except Exception as e:
            error_msg = f"Error: {e}"
            st.error(error_msg)

            save_message(ticket_id, "assistant", error_msg, "general")

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": error_msg,
                    "intent": "general",
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
