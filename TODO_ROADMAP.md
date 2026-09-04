# 📋 Implementation Roadmap: Social Graphics Engine & Interactive Telegram Bot

This document outlines the architecture, data flows, and technical implementation plan for **Automated Social Match Graphics** and **Full Telegram Bot Interactive Control**.

---

## 🎨 Phase 1: Automated Social Media Graphics Engine

We will build a dedicated `GraphicsEngine` service in `src/engine/graphics_generator.py` (using `Pillow` or headless SVG/HTML rendering) to generate high-resolution, branded visual cards.

### 1. ⚽ Live Goal Card (1080 × 1080 px / 1:1)
* **Design Spec:**
  * Dark sports glassmorphism background with subtle stadium blur & team accent color glow.
  * Home Crest (Left) vs Away Crest (Right) with prominent scoreline badge (`1 - 0`).
  * Scorer player badge (Player headshot / cutout or typography badge) with minute pill (`34'`).
  * Assist pill (`👟 Assist: Nathan Richmond`).
  * Competition crest & match timer badge at the top header.
  * Official newsroom branding watermark footer (`PAVILION SPORTS DESK`).

### 2. 📋 Starting XI Lineup Board (1080 × 1350 px / 4:5 or 1080 × 1080 px)
* **Trigger:** Auto-generated **60 minutes before kickoff** when Sofascore/API publishes official `/event/{id}/lineups`.
* **Design Spec:**
  * Isometric / Top-down green pitch layout with tactical grid lines.
  * Formation layout visualization (e.g., *4-3-3*, *4-2-3-1*, *3-5-2*, *4-4-2*).
  * Player jersey circles containing squad number, player name, and captain `(C)` badge.
  * Substitutes bench roster listed cleanly at the bottom.
  * Manager name, match venue, and referee badge.

### 3. 🏁 Full-Time Result Scorecard (1080 × 1080 px)
* **Trigger:** Generated at final whistle (`PERIOD_FULL_TIME`).
* **Design Spec:**
  * Final score display with winner highlight glow or "POINTS SHARED" banner.
  * Chronological goalscorers list with goal minutes for both teams.
  * Red card badges if applicable.
  * Match Stats Comparison Bars (Possession %, Total Shots, Shots on Target, xG).
  * Player of the Match (POTM) badge with highest Sofascore rating.

---

## 🤖 Phase 2: Full Interactive Telegram Bot Control

### How the Bot Listener Works:
Yes, our backend can take complete bidirectional control of `@Football_post_bot`!
Instead of only sending outbound messages, we run an **Async Telegram Bot Polling Listener** (or webhook) using `httpx` long-polling (`getUpdates`) or `python-telegram-bot` / `aiogram`.

### 1. Interactive Inline Keyboard Buttons on Every Post
Below every goal or match post, the bot will attach interactive buttons:
```text
┌─────────────────────────┬─────────────────────────┐
│  🔁 বাংলা / English      │  📊 লাইভ ম্যাচ স্ট্যাটস    │
├─────────────────────────┼─────────────────────────┤
│  🖼️ জেনারেট স্কোরকার্ড     │  ❌ ডিলিট পোস্ট           │
└─────────────────────────┴─────────────────────────┘
```

* **`[ 🔁 বাংলা / English ]`:** Instantly toggles the caption between Bengali and English without leaving Telegram.
* **`[ 📊 লাইভ ম্যাচ স্ট্যাটস ]`:** Fetches real-time possession, shots, and passes directly into the chat.
* **`[ 🖼️ জেনারেট স্কোরকার্ড ]`:** Renders and sends the HD Goal Card / Scorecard image on demand.
* **`[ ❌ ডিলিট পোস্ট ]`:** Allows editorial desks to remove accidental test posts with one tap.

### 2. Direct Bot Commands in Telegram Chat:
Desk editors can control the remote monitoring directly from Telegram chat:
* `/track <match_id or team_name>` — Search and arm a live match without opening the web UI.
* `/untrack <match_id>` — Remove a match from active monitoring.
* `/status` — View active night shift status, CPU health, and list of tracked games.
* `/live` — List all top worldwide live fixtures and current scorelines.
* `/lineup <match_id>` — Fetch and render the Starting XI graphic on demand.
* `/stats <match_id>` — Pull full match momentum & analytics card.
* `/nightshift on|off` — Start or stop overnight automated desk mode.

---

## 🗓️ Implementation Phases

| Phase | Milestone | Deliverables |
| :--- | :--- | :--- |
| **Phase 1** | **Graphics Template Engine** | Build `Pillow` visual renderer for Goal Cards, Lineup Pitch Boards, and FT Result Cards. |
| **Phase 2** | **Lineups Ingestion Pipeline** | Add `/event/{id}/lineups` polling with 60-min pre-match alert triggers. |
| **Phase 3** | **Interactive Telegram Bot Listener** | Implement `TelegramBotListener` long-polling `getUpdates` for button callbacks & commands. |
| **Phase 4** | **Desk UI Image Previews** | Display rendered social cards in the Web UI dashboard with one-click download & copy. |
