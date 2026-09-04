# ⚽ Football Live Content Engine & Event Monitor

A high-throughput, real-time football event monitoring and AI social media content generation system built according to Domain-Driven Design (DDD) principles.

---

## 🏛️ System Architecture

```text
               ┌── Live Global Football Feed (100+ Live Matches)
               │
 Live Matches ─┼── Fast Difference & Deduplication Engine
               │
               └── Event Normalizer (Goals, Cards, Subs, VAR)
                      ↓
               Match State Aggregates (DDD)
                      ↓
               Content Rules Engine (Configurable Filters)
                      ↓
               AI Social Post Generator (Facebook / X / Telegram)
                      ↓
        ┌─────────────┴─────────────┐
        ↓                           ↓
WebSocket Real-Time Feed     Human Review & Approval Queue
(Instant Push to Web/UI)     (Approve / Edit / Publish)
```

---

## 🚀 Quickstart & Setup

### 1. Activate Environment

```bash
cd /home/yameek/temp_ai/football-live-content-engine
source .venv/bin/activate
```

---

## 💻 CLI Commands

The engine provides an interactive, colorized terminal CLI:

### 1. View Live Matches Worldwide (100+ Live Fixtures)
```bash
python -m src.cli live
```

### 2. Live Monitor a Match with Real-Time Event Feed & Post Generation
```bash
python -m src.cli monitor <MATCH_ID>
```

### 3. Run Deterministic Match Simulation (Arsenal vs Chelsea)
```bash
python -m src.cli simulate
```

### 4. Launch Web Server & Interactive Real-Time Dashboard
```bash
python -m src.cli serve
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser for the real-time HTML5 Dashboard, live score feeds, WebSocket event stream, and post approval queue!

---

## 🌐 REST & WebSocket API

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `GET /` | `HTML` | Real-Time Live Dashboard with WebSockets & Approval Queue |
| `GET /api/matches/live` | `GET` | List all currently active live football matches |
| `GET /api/matches/scheduled` | `GET` | Get scheduled fixtures for a date |
| `POST /api/matches/monitor` | `POST` | Add a match to the live background poller |
| `GET /api/matches/{id}/events`| `GET` | Fetch chronological normalized domain events (Goals, Cards, VAR) |
| `GET /api/posts` | `GET` | List generated social media posts |
| `PATCH /api/posts/{id}` | `PATCH`| Approve, reject, or publish a post |
| `WS /api/ws/live-events` | `WS` | Real-Time WebSocket stream broadcasting match events & created posts |

---

## 🤖 FastMCP AI Agent Integration

An MCP server is included for seamless integration with AI coding assistants (AGY / Claude / Cursor / Gemini):

```bash
python -m src.mcp_server
```

**Exposed MCP Tools:**
* `list_live_matches()`: Retrieve real-time match scores and status worldwide.
* `get_match_events(match_id)`: Inspect goals, cards, substitutions, and VAR reviews.
* `generate_post_for_event(match_id, event_id, platform)`: Generate social media post for any match incident.

---

## 🧪 Running Automated Tests

```bash
pytest -v
```
