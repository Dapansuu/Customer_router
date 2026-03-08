# 🎫 Customer Support Router

A Streamlit-based customer support application that automatically routes customer queries to the appropriate support workflow using intent detection powered by LangGraph.

---

## Features

- **Ticket Management** — Create new support tickets or resume existing ones via UUID
- **Intent Detection** — Automatically classifies incoming queries and routes them to the right handler
- **Persistent Chat History** — All conversations are stored in a local SQLite database
- **Session Management** — Customers log in with their ticket ID to continue previous conversations
- **Sidebar Session Info** — Quick view of customer name and active ticket ID

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io/) |
| Workflow / Routing | [LangGraph](https://github.com/langchain-ai/langgraph) (via `main.py`) |
| Database | SQLite (local, file-based) |
| Language | Python 3.9+ |

---

## Project Structure

```
.
├── streamlit_app.py   # Main Streamlit UI and database logic
├── main.py            # LangGraph workflow definition
├── tickets.db         # Auto-generated SQLite database (gitignored)
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/customer-support-router.git
cd customer-support-router

# Install dependencies
pip install -r requirements.txt
```

### Running the App

```bash
streamlit run streamlit_app.py
```

The app will be available at `http://localhost:8501`.

---

## Usage

1. **Create a new ticket** — Enter your name and click *Create New Ticket*. Save the generated Ticket ID for future access.
2. **Resume a ticket** — Paste your existing Ticket ID and click *Load Ticket*.
3. **Chat** — Describe your issue in the chat input. The system will detect your intent and route your query automatically.
4. **Logout** — Use the sidebar button to end your session.

---

## Database Schema

### `tickets`
| Column | Type | Description |
|---|---|---|
| `ticket_id` | TEXT (PK) | UUID for the support ticket |
| `customer_name` | TEXT | Customer's name |
| `created_at` | TEXT | ISO 8601 timestamp |

### `messages`
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER (PK) | Auto-incremented row ID |
| `ticket_id` | TEXT (FK) | References `tickets.ticket_id` |
| `role` | TEXT | `user` or `assistant` |
| `content` | TEXT | Message body |
| `intent` | TEXT | Detected intent (on assistant messages) |
| `created_at` | TEXT | ISO 8601 timestamp |

---

## Configuration

The workflow logic lives in `main.py` and exposes a `workflow` object (LangGraph `StateGraph`). To customise routing rules or add new intent handlers, edit `main.py`.

The SQLite database path defaults to `tickets.db` in the working directory. Change `DB_PATH` in `streamlit_app.py` to use a different location.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.