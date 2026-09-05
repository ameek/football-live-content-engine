import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings, ProviderType
from src.providers.live_feed_provider import LiveFeedProvider
from src.providers.mock_provider import MockFootballProvider
from src.engine.difference_engine import DifferenceEngine
from src.engine.post_generator import PostGenerator
from src.engine.websocket_manager import WebSocketNotificationManager
from src.engine.monitor import MatchMonitor
from src.api.routes import router

from src.publishers.telegram_bot_listener import TelegramBotListener

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("football_api")


class AppState:
    def __init__(self):
        self.ws_manager = WebSocketNotificationManager()
        self.diff_engine = DifferenceEngine()
        self.post_generator = PostGenerator(platform=settings.default_platform)

        if settings.provider_type == ProviderType.MOCK:
            self.provider = MockFootballProvider()
        else:
            self.provider = LiveFeedProvider(timeout_seconds=settings.request_timeout_seconds)

        self.monitor = MatchMonitor(
            provider=self.provider,
            diff_engine=self.diff_engine,
            post_generator=self.post_generator,
            ws_manager=self.ws_manager,
            poll_interval_seconds=settings.poll_interval_seconds
        )
        self.bot_listener = TelegramBotListener(monitor=self.monitor)


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Night-Shift Content Engine & Interactive Telegram Bot Listener...")
    await app_state.monitor.start()
    await app_state.bot_listener.start()
    yield
    logger.info("Shutting down monitor loop and bot listener...")
    await app_state.bot_listener.stop()
    await app_state.monitor.stop()


app = FastAPI(
    title="Football Night-Shift Newsroom Engine",
    description="Automated Overnight Football Monitoring & Bangla/English Sports Post Generator",
    version="0.3.2",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚽ Football Night-Shift Monitor & Post Desk</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', 'Hind Siliguri', sans-serif; }
        .bangla { font-family: 'Hind Siliguri', sans-serif; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #090d16; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 9999px; }
        ::-webkit-scrollbar-thumb:hover { background: #334155; }
    </style>
</head>
<body class="bg-[#070b12] text-slate-100 min-h-screen antialiased">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800/80 bg-[#0b1220]/90 backdrop-blur sticky top-0 z-50">
        <div class="max-w-[1700px] mx-auto px-6 py-3.5 flex flex-col md:flex-row justify-between items-center gap-4">
            <!-- Brand -->
            <div class="flex items-center gap-3 w-full md:w-auto">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-emerald-500/10">
                    ⚽
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h1 class="text-lg font-extrabold tracking-tight text-white">FOOTBALL DESK</h1>
                        <span class="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30">Remote Desk</span>
                    </div>
                    <p class="text-xs text-slate-400">অটোমেটেড ফুটবল মনিটরিং ও ব্রেকিং নিউজ পাবলিশার</p>
                </div>
            </div>

            <!-- Top Actions -->
            <div class="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end">
                <div id="ws-badge" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Live Socket</span>
                </div>

                <!-- Settings Button -->
                <button onclick="openSettingsModal()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5 shadow-sm">
                    <span>⚙️</span> <span>Coverage Settings</span>
                </button>

                <!-- Remote Desk Button -->
                <button id="nightshift-btn" onclick="toggleNightShift()" class="px-5 py-2 rounded-xl text-xs font-bold tracking-wide shadow-lg transition-all duration-200 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/25 border border-indigo-400/30">
                    <span class="text-sm">📡</span> <span id="nightshift-text">START REMOTE DESK</span>
                </button>
            </div>
        </div>
    </header>

    <!-- Remote Desk Armed Banner -->
    <div id="nightshift-banner" class="hidden bg-gradient-to-r from-indigo-950 via-[#0c1427] to-emerald-950 border-b border-indigo-500/30 px-6 py-2.5">
        <div class="max-w-[1700px] mx-auto flex flex-col sm:flex-row justify-between items-center gap-2 text-xs">
            <div class="flex items-center gap-2.5 text-indigo-200">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                <span>📡 <strong>Remote Desk Armed:</strong> Monitoring <span id="roster-count" class="font-bold text-white px-1.5 py-0.5 rounded bg-indigo-500/30">0</span> match(es). Automated streaming active!</span>
            </div>
            <span class="text-slate-400 text-[11px]">Telegram Direct Publishing active</span>
        </div>
    </div>

    <!-- Main Workspace Grid (3 Columns) -->
    <main class="max-w-[1700px] mx-auto px-6 py-6 space-y-8">
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

            <!-- ================= Column 1: Live Match Explorer (5 cols) ================= -->
            <div class="lg:col-span-5 bg-[#0b1322]/80 rounded-2xl border border-slate-800/80 p-5 flex flex-col h-[820px] shadow-xl">
                <!-- Header -->
                <div class="flex justify-between items-center pb-3 mb-3 border-b border-slate-800/80">
                    <div>
                        <h2 class="text-sm font-bold text-white flex items-center gap-2">
                            <span>🔥</span> Live Matches
                        </h2>
                        <p id="matches-count-label" class="text-xs text-slate-400 mt-0.5">Loading matches...</p>
                    </div>
                    <button onclick="fetchMatches()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition flex items-center gap-1.5">
                        <span>🔄</span> Refresh
                    </button>
                </div>

                <!-- Filters & Search Toolbar -->
                <div class="space-y-2.5 mb-3.5">
                    <!-- Search Input -->
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-slate-500 text-sm">🔍</span>
                        <input type="text" id="search-input" oninput="applyFilters()" placeholder="Search team (e.g. Real Madrid, Liverpool, Arsenal)..." class="w-full bg-[#070c16] border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl pl-9 pr-8 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none transition">
                        <button onclick="clearSearch()" id="clear-search-btn" class="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-500 hover:text-white text-xs hidden">✕</button>
                    </div>

                    <!-- Dropdowns Row -->
                    <div class="grid grid-cols-2 gap-2 relative">
                        <!-- Custom League Dropdown with Logos -->
                        <div class="relative" id="custom-league-dropdown-container">
                            <button type="button" onclick="toggleLeagueDropdownMenu(event)" id="league-dropdown-btn" class="w-full bg-[#070c16] border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-xl px-2.5 py-2 text-xs text-slate-200 focus:outline-none transition flex items-center justify-between gap-1.5 shadow-sm">
                                <div class="flex items-center gap-1.5 truncate min-w-0">
                                    <span id="league-btn-logo" class="w-4 h-4 flex items-center justify-center flex-shrink-0 text-xs">🏆</span>
                                    <span id="league-btn-text" class="truncate font-medium text-slate-200">All Leagues</span>
                                </div>
                                <span class="text-slate-500 text-[10px] flex-shrink-0">▼</span>
                            </button>
                            
                            <!-- Dropdown Menu Box -->
                            <div id="league-dropdown-menu" class="hidden absolute z-50 left-0 right-0 mt-1.5 bg-[#0b1322] border border-slate-700/90 rounded-xl shadow-2xl overflow-hidden flex flex-col backdrop-blur-xl">
                                <div class="p-2 border-b border-slate-800/80 bg-[#070c16]">
                                    <input type="text" id="league-dropdown-search" oninput="filterLeagueDropdownList()" placeholder="Search league..." class="w-full bg-[#0b1322] border border-slate-700 rounded-lg px-2.5 py-1 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
                                </div>
                                <div id="league-dropdown-items" class="overflow-y-auto max-h-64 p-1 space-y-0.5 scrollbar-thin">
                                    <!-- Items rendered dynamically with logos -->
                                </div>
                            </div>
                        </div>

                        <select id="coverage-filter" onchange="applyFilters()" class="w-full bg-[#070c16] border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none transition">
                            <option value="ALL">All Matches</option>
                            <option value="TRACKED">Tracked Only (Tonight)</option>
                        </select>
                    </div>

                    <!-- Featured Quick League Badges -->
                    <div class="flex items-center gap-1.5 overflow-x-auto pt-1 pb-1 scrollbar-none text-[11px]" id="featured-pills">
                        <button onclick="quickFilterLeague('All')" class="pill-btn active px-3 py-1 rounded-lg bg-indigo-600 text-white font-semibold whitespace-nowrap shadow-sm">All</button>
                        <button onclick="quickFilterLeague('Premier League')" class="pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800">🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League</button>
                        <button onclick="quickFilterLeague('LaLiga')" class="pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800">🇪🇸 LaLiga</button>
                        <button onclick="quickFilterLeague('Serie A')" class="pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800">🇮🇹 Serie A</button>
                        <button onclick="quickFilterLeague('Ligue 1')" class="pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800">🇫🇷 Ligue 1</button>
                    </div>
                </div>

                <!-- Matches Scroll List -->
                <div id="matches-container" class="space-y-3 overflow-y-auto flex-1 pr-1">
                    <p class="text-slate-500 text-xs py-12 text-center">Loading matches...</p>
                </div>
            </div>

            <!-- ================= Column 2: Live Pitch Ticker (3 cols) ================= -->
            <div class="lg:col-span-3 bg-[#0b1322]/80 rounded-2xl border border-slate-800/80 p-5 flex flex-col h-[820px] shadow-xl">
                <!-- Header with Sync Button -->
                <div class="flex justify-between items-center pb-3 mb-3 border-b border-slate-800/80">
                    <div>
                        <h2 class="text-sm font-bold text-white flex items-center gap-2">
                            <span>⚡</span> Pitch Ticker
                        </h2>
                        <p class="text-xs text-slate-400 mt-0.5">Real-time pitch stream</p>
                    </div>
                    <button onclick="forceSyncTicker()" id="sync-ticker-btn" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition flex items-center gap-1" title="Force sync and pull latest incidents">
                        <span>🔄</span> <span>Sync</span>
                    </button>
                </div>

                <!-- Ticker Events Stream -->
                <div id="events-container" class="space-y-2.5 overflow-y-auto flex-1 pr-1">
                    <div class="text-center py-16 px-4">
                        <div class="w-12 h-12 rounded-full bg-slate-800/60 mx-auto flex items-center justify-center text-xl mb-3">📡</div>
                        <p class="text-slate-300 text-xs font-semibold">No Events Yet</p>
                        <p class="text-slate-500 text-[11px] mt-1">Click <strong>+ Track</strong> on any match to start streaming live pitch incidents.</p>
                    </div>
                </div>
            </div>

            <!-- ================= Column 3: Post Section (4 cols) ================= -->
            <div class="lg:col-span-4 bg-[#0b1322]/80 rounded-2xl border border-slate-800/80 p-5 flex flex-col h-[820px] shadow-xl">
                <!-- Header with Refresh Button -->
                <div class="flex justify-between items-center pb-3 mb-3 border-b border-slate-800/80">
                    <div>
                        <h2 class="text-sm font-bold text-white flex items-center gap-2">
                            <span>📱</span> Post Section
                        </h2>
                        <p class="text-xs text-slate-400 mt-0.5">Bangla & English newsroom queue</p>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <button onclick="publishAllPendingPosts()" id="publish-all-btn" class="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1 shadow-sm" title="Publish all queued posts directly to Telegram">
                            <span>🚀</span> <span>Publish All</span>
                        </button>
                        <button onclick="forceSyncPosts()" id="sync-posts-btn" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition flex items-center gap-1" title="Re-evaluate and refresh posts">
                            <span>🔄</span> <span>Sync</span>
                        </button>
                        <span id="posts-count-badge" class="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">0 Posts</span>
                    </div>
                </div>

                <!-- Posts Scroll Queue -->
                <div id="posts-container" class="space-y-4 overflow-y-auto flex-1 pr-1">
                    <div class="text-center py-16 px-4">
                        <div class="w-12 h-12 rounded-full bg-slate-800/60 mx-auto flex items-center justify-center text-xl mb-3">📰</div>
                        <p class="text-slate-300 text-xs font-semibold">Post Queue Empty</p>
                        <p class="text-slate-500 text-[11px] mt-1">Generated social media posts will appear here for review and 1-click clipboard copy.</p>
                    </div>
                </div>
            </div>

        </div>

        <!-- ================= Calendar Section: Upcoming Games Schedule (Bottom) ================= -->
        <section class="bg-[#0b1322]/90 rounded-2xl border border-slate-800/90 p-6 shadow-2xl space-y-4">
            <!-- Calendar Header -->
            <div class="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 pb-4 border-b border-slate-800/80">
                <div class="flex items-center gap-3">
                    <div class="w-11 h-11 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-cyan-500/20 flex-shrink-0">
                        📅
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h2 class="text-base font-bold text-white">Upcoming Fixtures & Calendar Schedule</h2>
                            <span id="calendar-count-badge" class="px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 text-[10px] font-bold border border-indigo-500/30">Loading...</span>
                        </div>
                        <p class="text-xs text-slate-400">Search competitions, filter by date, and pre-schedule matches for tonight's night shift before kickoff</p>
                    </div>
                </div>

                <!-- Right Action: Refresh Fixtures -->
                <div class="flex items-center gap-2 self-end lg:self-center">
                    <button onclick="fetchCalendarMatches()" id="sync-cal-btn" class="px-3.5 py-2 rounded-xl bg-slate-800/90 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700/80 transition flex items-center gap-1.5 shadow-sm">
                        <span>🔄</span> <span>Refresh Fixtures</span>
                    </button>
                </div>
            </div>

            <!-- Calendar Search & Filter Controls Bar -->
            <div class="space-y-3 pt-1">
                <!-- Row 1: Search Input + Date Tabs + League Dropdown -->
                <div class="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
                    <!-- Search Input (Span 5) -->
                    <div class="md:col-span-5 relative">
                        <input type="text" id="calendar-search-input" oninput="filterCalendarMatches()" placeholder="🔍 Search leagues (e.g. Premier League, LaLiga) or teams..." class="w-full bg-[#070c16] border border-slate-700/80 focus:border-indigo-500 rounded-xl px-3.5 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none transition shadow-inner">
                        <button id="calendar-clear-search-btn" onclick="clearCalendarSearch()" class="hidden absolute right-3 top-2 text-slate-400 hover:text-white text-xs">✕</button>
                    </div>

                    <!-- Date Tabs (Span 4) -->
                    <div class="md:col-span-4 flex items-center justify-center sm:justify-start gap-1 bg-[#070c16] p-1 rounded-xl border border-slate-800 text-xs font-medium" id="calendar-date-tabs">
                        <button onclick="selectCalendarDate('today')" class="cal-tab active px-2.5 py-1.5 rounded-lg bg-indigo-600 text-white font-bold transition flex-1 text-center">Tonight / Today</button>
                        <button onclick="selectCalendarDate('tomorrow')" class="cal-tab px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex-1 text-center">Tomorrow</button>
                        <button onclick="selectCalendarDate('weekend')" class="cal-tab px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex-1 text-center">Next 3 Days</button>
                        <button onclick="selectCalendarDate('all')" class="cal-tab px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex-1 text-center">All</button>
                    </div>

                    <!-- League Dropdown & Status Filter (Span 3) -->
                    <div class="md:col-span-3 flex items-center gap-2 relative">
                        <!-- Custom Calendar League Dropdown with Logos -->
                        <div class="relative flex-1" id="custom-calendar-league-dropdown-container">
                            <button type="button" onclick="toggleCalendarLeagueDropdownMenu(event)" id="calendar-league-dropdown-btn" class="w-full bg-[#070c16] border border-slate-700/80 hover:border-slate-600 focus:border-indigo-500 rounded-xl px-2.5 py-2 text-xs text-slate-200 focus:outline-none transition flex items-center justify-between gap-1.5 shadow-sm">
                                <div class="flex items-center gap-1.5 truncate min-w-0">
                                    <span id="calendar-league-btn-logo" class="w-4 h-4 flex items-center justify-center flex-shrink-0 text-xs">🏆</span>
                                    <span id="calendar-league-btn-text" class="truncate font-medium text-slate-200">All Competitions</span>
                                </div>
                                <span class="text-slate-500 text-[10px] flex-shrink-0">▼</span>
                            </button>
                            
                            <!-- Calendar Dropdown Menu Box -->
                            <div id="calendar-league-dropdown-menu" class="hidden absolute z-50 left-0 right-0 mt-1.5 bg-[#0b1322] border border-slate-700/90 rounded-xl shadow-2xl overflow-hidden flex flex-col backdrop-blur-xl">
                                <div class="p-2 border-b border-slate-800/80 bg-[#070c16]">
                                    <input type="text" id="calendar-league-dropdown-search" oninput="filterCalendarLeagueDropdownList()" placeholder="Search competition..." class="w-full bg-[#0b1322] border border-slate-700 rounded-lg px-2.5 py-1 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
                                </div>
                                <div id="calendar-league-dropdown-items" class="overflow-y-auto max-h-64 p-1 space-y-0.5 scrollbar-thin">
                                    <!-- Items rendered dynamically with logos -->
                                </div>
                            </div>
                        </div>

                        <select id="calendar-status-filter" onchange="filterCalendarMatches()" class="bg-[#070c16] border border-slate-700/80 focus:border-indigo-500 rounded-xl px-2.5 py-2 text-xs text-slate-200 focus:outline-none whitespace-nowrap">
                            <option value="ALL">All Status</option>
                            <option value="SCHEDULED">⭐ Scheduled</option>
                            <option value="UNSCHEDULED">Unscheduled</option>
                        </select>
                    </div>
                </div>

                <!-- Row 2: Featured League Quick Filter Pills -->
                <div class="flex items-center gap-2 overflow-x-auto pb-1 text-xs no-scrollbar" id="calendar-featured-pills">
                    <span class="text-slate-500 text-[11px] font-semibold whitespace-nowrap mr-1">Quick Select:</span>
                    <button onclick="quickFilterCalendarLeague('All')" class="cal-pill-btn active px-3 py-1 rounded-lg bg-indigo-600 text-white font-semibold whitespace-nowrap shadow-sm text-xs">All Competitions</button>
                    <button onclick="quickFilterCalendarLeague('Premier League')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League</button>
                    <button onclick="quickFilterCalendarLeague('LaLiga')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">🇪🇸 LaLiga</button>
                    <button onclick="quickFilterCalendarLeague('UEFA Champions League')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">⭐ Champions League</button>
                    <button onclick="quickFilterCalendarLeague('Serie A')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">🇮🇹 Serie A</button>
                    <button onclick="quickFilterCalendarLeague('Bundesliga')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">🇩🇪 Bundesliga</button>
                    <button onclick="quickFilterCalendarLeague('Saudi Pro League')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">🇸🇦 Saudi League</button>
                    <button onclick="quickFilterCalendarLeague('Liga Portugal')" class="cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs">🇵🇹 Liga Portugal</button>
                </div>
            </div>

            <!-- Fixtures Count Banner -->
            <div class="flex justify-between items-center text-[11px] text-slate-400 px-1 pt-1">
                <span id="calendar-count-label">Loading fixtures...</span>
                <span class="text-slate-500">Configure coverage profile before scheduling</span>
            </div>

            <!-- Calendar Match Cards Grid -->
            <div id="calendar-matches-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-1">
                <p class="text-slate-500 text-xs col-span-3 py-12 text-center">Loading upcoming fixtures...</p>
            </div>
        </section>
    </main>

    <!-- ================= Coverage Settings Modal ================= -->
    <div id="settings-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-[#0b1322] border border-slate-800 w-full max-w-2xl rounded-2xl p-6 shadow-2xl flex flex-col max-h-[90vh]">
            <!-- Modal Header -->
            <div class="flex justify-between items-center pb-4 border-b border-slate-800">
                <div class="flex items-center gap-2.5">
                    <span class="text-xl">⚙️</span>
                    <div>
                        <h3 class="text-base font-bold text-white">Coverage Level Settings</h3>
                        <p class="text-xs text-slate-400">Configure which pitch events trigger posts for each coverage level</p>
                    </div>
                </div>
                <button onclick="closeSettingsModal()" class="text-slate-400 hover:text-white text-lg px-2">✕</button>
            </div>

            <!-- Modal Body (Scrollable) -->
            <div class="overflow-y-auto py-4 space-y-6 flex-1 pr-1 text-xs">
                <!-- Level 1: 🔴 Full Coverage -->
                <div class="p-4 rounded-xl bg-[#070c16] border border-red-500/30">
                    <div class="flex items-center justify-between mb-3">
                        <span class="font-bold text-red-400 text-sm flex items-center gap-1.5">
                            <span>🔴</span> Full Coverage (সবকিছু)
                        </span>
                        <span class="text-[11px] text-slate-400">For El Clásico, Cup Finals, Big Derbies</span>
                    </div>
                    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5" id="full-events-container">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- Level 2: 🟡 Standard Coverage -->
                <div class="p-4 rounded-xl bg-[#070c16] border border-amber-500/30">
                    <div class="flex items-center justify-between mb-3">
                        <span class="font-bold text-amber-400 text-sm flex items-center gap-1.5">
                            <span>🟡</span> Standard Coverage (গুরুত্বপূর্ণ ঘটনা)
                        </span>
                        <span class="text-[11px] text-slate-400">Default for major league fixtures</span>
                    </div>
                    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5" id="standard-events-container">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- Level 3: 🟢 Result Only -->
                <div class="p-4 rounded-xl bg-[#070c16] border border-emerald-500/30">
                    <div class="flex items-center justify-between mb-3">
                        <span class="font-bold text-emerald-400 text-sm flex items-center gap-1.5">
                            <span>🟢</span> Result Only (ফলাফল ও গোল)
                        </span>
                        <span class="text-[11px] text-slate-400">For secondary or low-tier matches</span>
                    </div>
                    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5" id="result-events-container">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- Default Preferences -->
                <div class="grid grid-cols-2 gap-4 p-4 rounded-xl bg-[#070c16] border border-slate-800">
                    <div>
                        <label class="block text-slate-300 font-semibold mb-1">Default Post Language</label>
                        <select id="setting-default-lang" class="w-full bg-[#0b1322] border border-slate-700 text-slate-200 rounded-lg p-2 text-xs focus:outline-none">
                            <option value="bn">🇧🇩 বাংলা (Bangla)</option>
                            <option value="en">🇬🇧 English</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-slate-300 font-semibold mb-1">Default Auto-Publish</label>
                        <select id="setting-default-autopub" class="w-full bg-[#0b1322] border border-slate-700 text-slate-200 rounded-lg p-2 text-xs focus:outline-none">
                            <option value="false">Review Queue (Manual Approval)</option>
                            <option value="true">Auto-Publish to Facebook Directly</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Modal Footer -->
            <div class="pt-4 border-t border-slate-800 flex justify-end gap-3">
                <button onclick="closeSettingsModal()" class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition">Cancel</button>
                <button onclick="saveCoverageSettings()" class="px-5 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition">Save Settings</button>
            </div>
        </div>
    </div>

    <!-- ================= Social Graphics Preview Modal ================= -->
    <div id="graphics-modal" class="fixed inset-0 bg-black/85 backdrop-blur-md z-50 hidden flex items-center justify-center p-4">
        <div class="bg-[#0b1322] border border-slate-700/80 w-full max-w-3xl rounded-2xl p-6 shadow-2xl flex flex-col max-h-[92vh]">
            <!-- Modal Header -->
            <div class="flex justify-between items-center pb-4 border-b border-slate-800">
                <div class="flex items-center gap-2.5">
                    <span class="text-2xl">🖼️</span>
                    <div>
                        <h3 id="graphics-modal-title" class="text-base font-bold text-white">Social Media Match Graphic</h3>
                        <p id="graphics-modal-subtitle" class="text-xs text-slate-400">High-resolution match visual for Facebook & Social Desk</p>
                    </div>
                </div>
                <button onclick="closeGraphicsModal()" class="text-slate-400 hover:text-white text-lg px-2">✕</button>
            </div>

            <!-- Visual Style / Type Tabs -->
            <div class="flex items-center gap-2 pt-3 pb-1" id="graphics-tab-bar">
                <button onclick="switchGraphicsTab('goal')" id="tab-btn-goal" class="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white transition flex items-center gap-1.5 shadow-sm">
                    <span>⚽</span> <span>Goal Card (1:1)</span>
                </button>
                <button onclick="switchGraphicsTab('lineup')" id="tab-btn-lineup" class="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1.5">
                    <span>📋</span> <span>Starting XI Pitch (4:5)</span>
                </button>
                <button onclick="switchGraphicsTab('fulltime')" id="tab-btn-fulltime" class="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1.5">
                    <span>🏁</span> <span>Full-Time Scorecard (1:1)</span>
                </button>
            </div>

            <!-- Graphic Image Preview Container -->
            <div class="flex-1 overflow-y-auto py-4 flex flex-col items-center justify-center min-h-[380px] relative bg-[#070c16]/90 rounded-xl border border-slate-800 my-2 shadow-inner">
                <div id="graphics-loading" class="flex flex-col items-center gap-2 text-slate-400 text-xs">
                    <span class="text-3xl animate-spin">⏳</span>
                    <span class="font-medium">Rendering HD Match Graphic...</span>
                </div>
                <img id="graphics-preview-img" src="" alt="Match Graphic" class="max-h-[500px] w-auto object-contain rounded-lg shadow-2xl hidden" onload="onGraphicLoaded()" onerror="onGraphicError()">
            </div>

            <!-- Modal Footer Actions -->
            <div class="pt-3 border-t border-slate-800 flex justify-between items-center gap-3">
                <span class="text-[11px] text-slate-500">Auto-formatted with crests & verified typography</span>
                <div class="flex items-center gap-3">
                    <button onclick="closeGraphicsModal()" class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition">Close</button>
                    <a id="graphics-download-btn" href="#" download="match-card.png" class="px-5 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20 transition flex items-center gap-1.5">
                        <span>⬇️</span> <span>Download PNG</span>
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- Floating Copy Toast -->
    <div id="copy-toast" class="fixed bottom-6 right-6 bg-emerald-600 text-white text-xs font-bold px-4 py-3 rounded-xl shadow-2xl shadow-emerald-950/80 border border-emerald-400/40 hidden transition duration-300 flex items-center gap-2 z-50">
        <span>✓</span> <span id="toast-text">Copied to clipboard!</span>
    </div>

    <!-- Script Logic -->
    <script>
        let allMatches = [];
        let calendarMatches = [];
        let currentLeague = "All";
        let calendarLeague = "All";
        let currentCalendarDate = "today";
        let nightShiftActive = false;
        let nightShiftActiveMatchIds = [];

        const AVAILABLE_EVENTS = [
            { id: "GOAL", label: "⚽ Goals" },
            { id: "PENALTY_GOAL", label: "🎯 Penalties Scored" },
            { id: "OWN_GOAL", label: "🤦 Own Goals" },
            { id: "RED_CARD", label: "🟥 Red Cards" },
            { id: "YELLOW_RED_CARD", label: "🟨🟥 2nd Yellows" },
            { id: "YELLOW_CARD", label: "🟨 Yellow Cards" },
            { id: "VAR_OVERTURN", label: "📺 VAR Overturns" },
            { id: "VAR_DECISION", label: "📺 VAR Reviews" },
            { id: "SUBSTITUTION", label: "🔄 Substitutions" },
            { id: "PERIOD_HALF_TIME", label: "⏸️ Half-Time" },
            { id: "PERIOD_FULL_TIME", label: "🏁 Full-Time" },
            { id: "PENALTY_MISSED", label: "❌ Missed Penalties" }
        ];

        let coverageConfig = {
            full_events: [],
            standard_events: [],
            result_only_events: [],
            default_language: "bn",
            default_auto_publish: false
        };

        async function init() {
            await loadCoverageSettings();
            await fetchNightShiftStatus();
            await fetchMatches();
            await fetchCalendarMatches();
            await fetchPosts();
            setupWebSocket();

            // Resilient auto-sync ticker & post queue for Vercel / serverless deployments
            setInterval(async () => {
                try {
                    await fetchMatches();
                    await fetchPosts();
                } catch (e) {
                    console.error('Auto-sync error:', e);
                }
            }, 10000);

            document.addEventListener('click', (e) => {
                const liveDrop = document.getElementById('custom-league-dropdown-container');
                const calDrop = document.getElementById('custom-calendar-league-dropdown-container');
                if (liveDrop && !liveDrop.contains(e.target)) {
                    const m = document.getElementById('league-dropdown-menu');
                    if (m) m.classList.add('hidden');
                }
                if (calDrop && !calDrop.contains(e.target)) {
                    const m = document.getElementById('calendar-league-dropdown-menu');
                    if (m) m.classList.add('hidden');
                }
            });
        }

        async function loadCoverageSettings() {
            try {
                const res = await fetch('/api/settings/coverage');
                coverageConfig = await res.json();
            } catch (e) {
                console.error(e);
            }
        }

        function openSettingsModal() {
            renderEventCheckboxes('full-events-container', 'full', coverageConfig.full_events);
            renderEventCheckboxes('standard-events-container', 'standard', coverageConfig.standard_events);
            renderEventCheckboxes('result-events-container', 'result', coverageConfig.result_only_events);
            document.getElementById('setting-default-lang').value = coverageConfig.default_language || 'bn';
            document.getElementById('setting-default-autopub').value = coverageConfig.default_auto_publish ? 'true' : 'false';
            document.getElementById('settings-modal').classList.remove('hidden');
        }

        function closeSettingsModal() {
            document.getElementById('settings-modal').classList.add('hidden');
        }

        function renderEventCheckboxes(containerId, prefix, selectedEvents) {
            const container = document.getElementById(containerId);
            const selectedSet = new Set(selectedEvents);
            container.innerHTML = AVAILABLE_EVENTS.map(ev => `
                <label class="flex items-center gap-2 p-2 rounded-lg bg-[#0b1322] border border-slate-800 hover:border-slate-700 cursor-pointer text-slate-300 text-xs">
                    <input type="checkbox" name="${prefix}_event" value="${ev.id}" ${selectedSet.has(ev.id) ? 'checked' : ''} class="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0">
                    <span class="truncate">${ev.label}</span>
                </label>
            `).join('');
        }

        async function saveCoverageSettings() {
            const getSelected = (prefix) => Array.from(document.querySelectorAll(`input[name="${prefix}_event"]:checked`)).map(cb => cb.value);

            const payload = {
                full_events: getSelected('full'),
                standard_events: getSelected('standard'),
                result_only_events: getSelected('result'),
                default_language: document.getElementById('setting-default-lang').value,
                default_auto_publish: document.getElementById('setting-default-autopub').value === 'true'
            };

            try {
                const res = await fetch('/api/settings/coverage', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                coverageConfig = await res.json();
                closeSettingsModal();
                showToast("✓ Coverage settings saved!");
            } catch (err) {
                console.error(err);
            }
        }

        async function fetchNightShiftStatus() {
            try {
                const res = await fetch('/api/nightshift/status');
                const data = await res.json();
                nightShiftActive = data.active;
                nightShiftActiveMatchIds = data.active_match_ids || [];
                updateNightShiftUI();
            } catch (e) {
                console.error(e);
            }
        }

        function updateNightShiftUI() {
            const btn = document.getElementById('nightshift-btn');
            const txt = document.getElementById('nightshift-text');
            const banner = document.getElementById('nightshift-banner');
            
            const liveTracked = allMatches.filter(m => m.auto_generate).length;
            const calTracked = calendarMatches.filter(m => m.auto_generate).length;
            const trackedCount = Math.max(liveTracked, calTracked, nightShiftActiveMatchIds.length);

            if (nightShiftActive) {
                btn.className = "px-5 py-2 rounded-xl text-xs font-bold tracking-wide shadow-lg transition-all duration-200 flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/25 border border-emerald-400/30";
                txt.innerText = "REMOTE DESK ARMED 📡";
                banner.classList.remove('hidden');
                const rosterCountEl = document.getElementById('roster-count');
                if (rosterCountEl) rosterCountEl.innerText = trackedCount;
            } else {
                btn.className = "px-5 py-2 rounded-xl text-xs font-bold tracking-wide shadow-lg transition-all duration-200 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/25 border border-indigo-400/30";
                txt.innerText = "START REMOTE DESK";
                banner.classList.add('hidden');
            }
        }

        async function toggleNightShift() {
            if (nightShiftActive) {
                await fetch('/api/nightshift/stop', { method: 'POST' });
                nightShiftActive = false;
            } else {
                await fetch('/api/nightshift/start', { method: 'POST' });
                nightShiftActive = true;
            }
            updateNightShiftUI();
            await fetchMatches();
        }

        async function fetchMatches() {
            try {
                const res = await fetch('/api/matches/live');
                allMatches = await res.json();
                populateLeagueDropdown(allMatches);
                updateNightShiftUI();
                applyFilters();
            } catch (e) {
                console.error(e);
            }
        }

        let cachedLeaguesList = [];

        function toggleLeagueDropdownMenu(e) {
            if (e) e.stopPropagation();
            const menu = document.getElementById('league-dropdown-menu');
            const calMenu = document.getElementById('calendar-league-dropdown-menu');
            if (calMenu) calMenu.classList.add('hidden');
            if (!menu) return;
            menu.classList.toggle('hidden');
            if (!menu.classList.contains('hidden')) {
                const search = document.getElementById('league-dropdown-search');
                if (search) {
                    search.value = '';
                    filterLeagueDropdownList();
                    setTimeout(() => search.focus(), 50);
                }
            }
        }

        function populateLeagueDropdown(matches) {
            const leagueMap = new Map();
            matches.forEach(m => {
                const name = m.tournament_name || "Other";
                if (!leagueMap.has(name)) {
                    leagueMap.set(name, { name: name, count: 0, logo: m.tournament_logo_url || null });
                }
                const entry = leagueMap.get(name);
                entry.count += 1;
                if (!entry.logo && m.tournament_logo_url) entry.logo = m.tournament_logo_url;
            });

            cachedLeaguesList = Array.from(leagueMap.values()).sort((a, b) => b.count - a.count);
            renderLeagueDropdownItems(cachedLeaguesList, matches.length);
        }

        function renderLeagueDropdownItems(leagues, totalMatches) {
            const container = document.getElementById('league-dropdown-items');
            if (!container) return;

            const total = totalMatches !== undefined ? totalMatches : allMatches.length;
            let html = `
                <button type="button" onclick="selectLeague('All', null)" class="w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition ${currentLeague === 'All' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-200 hover:bg-slate-800/80'}">
                    <div class="flex items-center gap-2 truncate">
                        <span class="w-4 h-4 flex items-center justify-center text-xs flex-shrink-0">🏆</span>
                        <span class="truncate font-medium">All Leagues</span>
                    </div>
                    <span class="text-[10px] font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${currentLeague === 'All' ? 'bg-indigo-700 text-white' : 'bg-slate-800 text-slate-400'}">${total}</span>
                </button>
            `;

            leagues.forEach(l => {
                const isSelected = currentLeague === l.name;
                const logoHtml = l.logo 
                    ? `<img src="${l.logo}" class="w-4 h-4 object-contain flex-shrink-0 rounded-sm" onerror="this.outerHTML='<span class=\\'w-4 h-4 flex items-center justify-center text-xs\\'>⚽</span>'">`
                    : `<span class="w-4 h-4 flex items-center justify-center text-xs">⚽</span>`;

                const safeName = l.name.replace(/'/g, "\\'");
                html += `
                    <button type="button" onclick="selectLeague('${safeName}', '${l.logo || ''}')" class="w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition ${isSelected ? 'bg-indigo-600 text-white font-bold' : 'text-slate-200 hover:bg-slate-800/80'}">
                        <div class="flex items-center gap-2 truncate min-w-0 pr-2">
                            ${logoHtml}
                            <span class="truncate" title="${l.name}">${l.name}</span>
                        </div>
                        <span class="text-[10px] font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${isSelected ? 'bg-indigo-700 text-white' : 'bg-slate-800 text-slate-400'}">${l.count}</span>
                    </button>
                `;
            });

            container.innerHTML = html;
        }

        function filterLeagueDropdownList() {
            const query = (document.getElementById('league-dropdown-search').value || '').toLowerCase().trim();
            const filtered = cachedLeaguesList.filter(l => l.name.toLowerCase().includes(query));
            renderLeagueDropdownItems(filtered, allMatches.length);
        }

        function selectLeague(val, logoUrl) {
            currentLeague = val;
            const btnText = document.getElementById('league-btn-text');
            const btnLogo = document.getElementById('league-btn-logo');
            
            if (btnText) btnText.innerText = val === 'All' ? 'All Leagues' : val;
            if (btnLogo) {
                if (val === 'All' || !logoUrl) {
                    btnLogo.innerHTML = '🏆';
                } else {
                    btnLogo.innerHTML = `<img src="${logoUrl}" class="w-4 h-4 object-contain" onerror="this.outerHTML='<span>🏆</span>'"/>`;
                }
            }

            const menu = document.getElementById('league-dropdown-menu');
            if (menu) menu.classList.add('hidden');

            updatePillHighlight();
            applyFilters();
        }

        function quickFilterLeague(val) {
            const entry = cachedLeaguesList.find(l => l.name.toLowerCase().includes(val.toLowerCase()));
            selectLeague(val, entry ? entry.logo : null);
        }

        function updatePillHighlight() {
            const pills = document.querySelectorAll('#featured-pills .pill-btn');
            pills.forEach(p => {
                if (p.innerText.includes(currentLeague) || (currentLeague === "All" && p.innerText === "All")) {
                    p.className = "pill-btn active px-3 py-1 rounded-lg bg-indigo-600 text-white font-semibold whitespace-nowrap shadow-sm";
                } else {
                    p.className = "pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800";
                }
            });
        }

        function applyFilters() {
            const query = document.getElementById('search-input').value.toLowerCase().trim();
            const coverageFilter = document.getElementById('coverage-filter').value;
            const clearBtn = document.getElementById('clear-search-btn');

            if (query) {
                clearBtn.classList.remove('hidden');
            } else {
                clearBtn.classList.add('hidden');
            }

            let filtered = allMatches.filter(m => {
                if (currentLeague !== "All" && !m.tournament_name.toLowerCase().includes(currentLeague.toLowerCase())) {
                    return false;
                }
                if (coverageFilter === "TRACKED" && !m.auto_generate) {
                    return false;
                }
                if (query) {
                    const matchText = `${m.home_team.name} ${m.away_team.name} ${m.tournament_name}`.toLowerCase();
                    if (!matchText.includes(query)) return false;
                }
                return true;
            });

            const trackedTotal = allMatches.filter(m => m.auto_generate).length;
            document.getElementById('matches-count-label').innerText = `${filtered.length} matches visible • ${trackedTotal} tracked tonight`;
            renderMatches(filtered);
        }

        function renderMatches(matches) {
            const container = document.getElementById('matches-container');

            if (matches.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-12 px-4 bg-[#070c16]/50 rounded-xl border border-slate-800/60 flex flex-col items-center">
                        <span class="text-2xl">🔍</span>
                        <p class="text-slate-300 text-xs mt-2 font-bold">No active live matches found</p>
                        <p class="text-slate-500 text-[11px] mt-1 max-w-xs">Major European leagues (Premier League, LaLiga, etc.) might not be playing live right now.</p>
                        <div class="flex gap-2 mt-3">
                            <button onclick="clearSearch()" class="px-3 py-1 rounded-lg bg-slate-800 text-xs text-indigo-400 hover:text-indigo-300 font-semibold border border-slate-700 transition">Clear Filters</button>
                            <a href="#calendar-matches-grid" onclick="document.getElementById('calendar-search-input').value = document.getElementById('search-input').value; filterCalendarMatches();" class="px-3 py-1 rounded-lg bg-indigo-600/30 text-xs text-indigo-300 hover:bg-indigo-600/50 font-semibold border border-indigo-500/30 transition">📅 Search in Upcoming Fixtures ↓</a>
                        </div>
                    </div>
                `;
                return;
            }

            container.innerHTML = matches.map(m => {
                const isTracked = m.auto_generate;
                const coverage = m.coverage || 'STANDARD';
                const autoPub = m.auto_publish || false;
                const lang = m.language || 'bn';

                return `
                    <div class="p-4 rounded-xl border ${isTracked ? 'border-emerald-500/60 bg-emerald-950/20 shadow-lg shadow-emerald-950/20' : 'border-slate-800 bg-[#070c16]/90 hover:border-slate-700/80'} transition flex flex-col gap-3">
                        <!-- Card Top Info -->
                        <div class="flex justify-between items-center text-[11px]">
                            <div class="flex items-center gap-1.5 truncate max-w-[230px]">
                                ${m.tournament_logo_url ? `<img src="${m.tournament_logo_url}" class="w-4 h-4 object-contain flex-shrink-0" onerror="this.style.display='none'">` : ''}
                                <span class="font-bold text-slate-300 truncate" title="${m.tournament_name}">${m.tournament_name}</span>
                            </div>
                            <div class="flex items-center gap-1.5 flex-shrink-0">
                                ${isTracked ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-extrabold border border-emerald-500/30">TRACKING</span>' : ''}
                                <span class="px-2 py-0.5 rounded-md bg-slate-800 text-emerald-400 font-mono font-bold">${m.status_detail} ${m.minute ? m.minute + "'" : ''}</span>
                            </div>
                        </div>

                        <!-- Teams & Score Header with Logos -->
                        <div class="flex justify-between items-center text-sm font-bold text-white py-1">
                            <div class="flex items-center gap-2 flex-1 min-w-0">
                                ${m.home_team.logo_url ? `<img src="${m.home_team.logo_url}" class="w-6 h-6 object-contain flex-shrink-0 rounded-full bg-slate-800/80 p-0.5" onerror="this.style.display='none'">` : ''}
                                <span class="truncate font-semibold text-slate-100">${m.home_team.name}</span>
                            </div>
                            <span class="px-3 py-1 rounded-lg bg-slate-800/90 font-mono text-emerald-400 text-base font-extrabold mx-2.5 border border-slate-700/50 flex-shrink-0">${m.score.home} - ${m.score.away}</span>
                            <div class="flex items-center justify-end gap-2 flex-1 min-w-0 text-right">
                                <span class="truncate font-semibold text-slate-100">${m.away_team.name}</span>
                                ${m.away_team.logo_url ? `<img src="${m.away_team.logo_url}" class="w-6 h-6 object-contain flex-shrink-0 rounded-full bg-slate-800/80 p-0.5" onerror="this.style.display='none'">` : ''}
                            </div>
                        </div>

                        <!-- Action Bar -->
                        <div class="pt-2.5 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs">
                            <!-- Left: Coverage & Language Selectors -->
                            <div class="flex items-center gap-2">
                                <select id="cov-${m.id}" onchange="onMatchOptionChange('${m.id}', ${isTracked})" class="bg-[#0b1322] border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 font-medium">
                                    <option value="FULL" ${coverage === 'FULL' ? 'selected' : ''}>🔴 Full</option>
                                    <option value="STANDARD" ${coverage === 'STANDARD' ? 'selected' : ''}>🟡 Standard</option>
                                    <option value="RESULT_ONLY" ${coverage === 'RESULT_ONLY' ? 'selected' : ''}>🟢 Result Only</option>
                                </select>

                                <select id="lang-${m.id}" onchange="onMatchOptionChange('${m.id}', ${isTracked})" class="bg-[#0b1322] border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-indigo-500 font-medium">
                                    <option value="bn" ${lang === 'bn' ? 'selected' : ''}>🇧🇩 বাংলা</option>
                                    <option value="en" ${lang === 'en' ? 'selected' : ''}>🇬🇧 EN</option>
                                </select>

                                <button onclick="openGraphicsModal('goal', '${m.id}', '${m.home_team.name} vs ${m.away_team.name}')" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold flex items-center gap-1 border border-slate-700 transition" title="Preview HD Social Media Graphics">
                                    <span>🖼️</span> <span>Card</span>
                                </button>
                            </div>

                            <!-- Right: Telegram Live Indicator & Track Button -->
                            <div class="flex items-center gap-2.5">
                                <span class="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                                    <span>✈️</span> <span>Telegram Live</span>
                                </span>
                                <button onclick="toggleMatchTracking('${m.id}', ${!isTracked})" class="px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all duration-150 ${isTracked ? 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/30' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20'}">
                                    ${isTracked ? '✕ Untrack' : '+ Track'}
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function clearSearch() {
            document.getElementById('search-input').value = '';
            selectLeague('All', null);
        }

        async function onMatchOptionChange(matchId, isTracked) {
            if (!isTracked) return;
            const covEl = document.getElementById(`cov-${matchId}`);
            const langEl = document.getElementById(`lang-${matchId}`);
            const coverage = covEl ? covEl.value : 'STANDARD';
            const lang = langEl ? langEl.value : 'bn';
            await updateMatchConfig(matchId, true, coverage, lang);
        }

        async function updateMatchConfig(matchId, tracked, coverage, lang) {
            await fetch('/api/matches/configure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    match_id: matchId,
                    tracked: tracked,
                    coverage: coverage,
                    auto_publish: true,
                    language: lang
                })
            });
            await fetchMatches();
        }

        async function toggleMatchTracking(matchId, shouldTrack) {
            const covEl = document.getElementById(`cov-${matchId}`);
            const langEl = document.getElementById(`lang-${matchId}`);
            const coverage = covEl ? covEl.value : 'STANDARD';
            const lang = langEl ? langEl.value : 'bn';

            await fetch('/api/matches/configure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    match_id: matchId,
                    tracked: shouldTrack,
                    coverage: coverage,
                    auto_publish: true,
                    language: lang
                })
            });
            await fetchMatches();
        }

        // ================= Force Sync Buttons for Ticker & Post Section =================
        async function forceSyncTicker() {
            const btn = document.getElementById('sync-ticker-btn');
            btn.innerHTML = '<span>⏳</span> <span>Syncing...</span>';
            try {
                const res = await fetch('/api/monitor/poll-now', { method: 'POST' });
                const data = await res.json();
                showToast(`✓ Pitch ticker synced! (${data.total_events_count} events total)`);
                await fetchMatches();
            } catch (err) {
                console.error(err);
            }
            btn.innerHTML = '<span>🔄</span> <span>Sync</span>';
        }

        async function forceSyncPosts() {
            const btn = document.getElementById('sync-posts-btn');
            btn.innerHTML = '<span>⏳</span> <span>Syncing...</span>';
            try {
                const res = await fetch('/api/monitor/poll-now', { method: 'POST' });
                const data = await res.json();
                await fetchPosts();
                showToast(`✓ Post queue refreshed! (${data.total_posts_count} posts)`);
            } catch (err) {
                console.error(err);
            }
            btn.innerHTML = '<span>🔄</span> <span>Sync</span>';
        }

        async function fetchPosts() {
            try {
                const res = await fetch('/api/posts');
                const posts = await res.json();
                document.getElementById('posts-count-badge').innerText = `${posts.length} Posts`;
                const container = document.getElementById('posts-container');

                if (posts.length === 0) {
                    container.innerHTML = `
                        <div class="text-center py-16 px-4">
                            <div class="w-12 h-12 rounded-full bg-slate-800/60 mx-auto flex items-center justify-center text-xl mb-3">📰</div>
                            <p class="text-slate-300 text-xs font-semibold">Post Queue Empty</p>
                            <p class="text-slate-500 text-[11px] mt-1">Generated social media posts will appear here for review and 1-click clipboard copy.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = posts.slice().reverse().map(p => `
                    <div class="p-4 rounded-xl bg-[#070c16] border ${p.status === 'PUBLISHED' ? 'border-emerald-500/50 bg-emerald-950/10' : 'border-slate-800'} flex flex-col gap-3 shadow-lg">
                        <!-- Card Header -->
                        <div class="flex justify-between items-center">
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">FACEBOOK</span>
                                <span class="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-800 text-slate-300">${p.language === 'bn' ? '🇧🇩 বাংলা' : '🇬🇧 EN'}</span>
                                ${(p.team_logo_url || p.image_url) ? `<img src="${p.team_logo_url || p.image_url}" class="w-5 h-5 object-contain rounded-full bg-slate-800/80 p-0.5 border border-slate-700/50" onerror="this.style.display='none'">` : ''}
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="openGraphicsModalForPost('${p.post_id}', '${p.match_id}', '${p.event_id}', '${(p.headline || '').replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/30 flex items-center gap-1 transition" title="Preview HD Social Graphic">
                                    <span>🖼️</span> <span>Card</span>
                                </button>
                                <button onclick="copyPostToClipboard('${p.post_id}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 flex items-center gap-1.5 transition" title="Copy text to clipboard">
                                    <span>📋</span> <span>Copy</span>
                                </button>
                                <span class="text-[11px] font-bold px-2 py-0.5 rounded-md ${p.status === 'PUBLISHED' ? 'bg-emerald-500/20 text-emerald-400' : p.status === 'APPROVED' ? 'bg-cyan-500/20 text-cyan-400' : 'bg-amber-500/20 text-amber-400'}">${p.status}</span>
                            </div>
                        </div>

                        <!-- Headline -->
                        <h4 class="text-xs font-bold text-white leading-snug">${p.headline}</h4>

                        <!-- Editable Content Textarea -->
                        <textarea id="content-${p.post_id}" rows="5" class="w-full bg-[#0b1322] border border-slate-800 focus:border-indigo-500 rounded-lg p-3 text-xs text-slate-200 focus:outline-none transition leading-relaxed font-sans">${p.content}</textarea>

                        <!-- Action Buttons -->
                        <div class="flex gap-2 pt-1 border-t border-slate-800/80">
                            <button onclick="approvePost('${p.post_id}', 'PUBLISHED')" class="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1 shadow-sm">
                                <span>🚀</span> Publish
                            </button>
                            <button onclick="approvePost('${p.post_id}', 'APPROVED')" class="flex-1 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition">
                                👍 Approve
                            </button>
                            <button onclick="approvePost('${p.post_id}', 'REJECTED')" class="px-3 py-1.5 bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 text-xs font-bold rounded-lg border border-rose-500/20 transition">
                                ✕
                            </button>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error(e);
            }
        }

        async function copyPostToClipboard(postId) {
            const content = document.getElementById(`content-${postId}`).value;
            try {
                await navigator.clipboard.writeText(content);
                showToast("✓ Copied post to clipboard!");
            } catch (err) {
                const textarea = document.getElementById(`content-${postId}`);
                textarea.select();
                document.execCommand('copy');
                showToast("✓ Copied post to clipboard!");
            }
        }

        function showToast(msg) {
            const toast = document.getElementById('copy-toast');
            document.getElementById('toast-text').innerText = msg;
            toast.classList.remove('hidden');
            setTimeout(() => {
                toast.classList.add('hidden');
            }, 2500);
        }

        async function approvePost(postId, status) {
            const content = document.getElementById(`content-${postId}`).value;
            await fetch(`/api/posts/${postId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: status, content: content })
            });
            if (status === 'PUBLISHED') {
                showToast("✓ Post published to Telegram channel!");
            }
            await fetchPosts();
        }

        async function publishAllPendingPosts() {
            const btn = document.getElementById('publish-all-btn');
            if (btn) btn.innerHTML = '<span>⏳</span> <span>Publishing...</span>';
            try {
                const res = await fetch('/api/posts');
                const posts = await res.json();
                const queued = posts.filter(p => p.status !== 'PUBLISHED');

                if (queued.length === 0) {
                    showToast("All posts are already published.");
                } else {
                    for (const p of queued) {
                        const contentEl = document.getElementById(`content-${p.post_id}`);
                        const content = contentEl ? contentEl.value : p.content;
                        await fetch(`/api/posts/${p.post_id}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: 'PUBLISHED', content: content })
                        });
                    }
                    showToast(`✓ Dispatched ${queued.length} posts to Telegram!`);
                    await fetchPosts();
                }
            } catch (err) {
                console.error(err);
            }
            if (btn) btn.innerHTML = '<span>🚀</span> <span>Publish All</span>';
        }

        // ================= Calendar Section Logic =================
        async function fetchCalendarMatches() {
            const btn = document.getElementById('sync-cal-btn');
            if (btn) btn.innerHTML = '<span>⏳</span> <span>Syncing...</span>';
            try {
                const res = await fetch('/api/matches/scheduled');
                calendarMatches = await res.json();
                populateCalendarLeagues(calendarMatches);
                filterCalendarMatches();
                updateNightShiftUI();
            } catch (e) {
                console.error(e);
            }
            if (btn) btn.innerHTML = '<span>🔄</span> <span>Refresh Fixtures</span>';
        }

        let cachedCalendarLeaguesList = [];

        function toggleCalendarLeagueDropdownMenu(e) {
            if (e) e.stopPropagation();
            const menu = document.getElementById('calendar-league-dropdown-menu');
            const liveMenu = document.getElementById('league-dropdown-menu');
            if (liveMenu) liveMenu.classList.add('hidden');
            if (!menu) return;
            menu.classList.toggle('hidden');
            if (!menu.classList.contains('hidden')) {
                const search = document.getElementById('calendar-league-dropdown-search');
                if (search) {
                    search.value = '';
                    filterCalendarLeagueDropdownList();
                    setTimeout(() => search.focus(), 50);
                }
            }
        }

        function populateCalendarLeagues(matches) {
            const leagueMap = new Map();
            matches.forEach(m => {
                const name = m.tournament_name || "Other";
                if (!leagueMap.has(name)) {
                    leagueMap.set(name, { name: name, count: 0, logo: m.tournament_logo_url || null });
                }
                const entry = leagueMap.get(name);
                entry.count += 1;
                if (!entry.logo && m.tournament_logo_url) entry.logo = m.tournament_logo_url;
            });

            cachedCalendarLeaguesList = Array.from(leagueMap.values()).sort((a, b) => b.count - a.count);
            renderCalendarLeagueDropdownItems(cachedCalendarLeaguesList, matches.length);
        }

        function renderCalendarLeagueDropdownItems(leagues, totalMatches) {
            const container = document.getElementById('calendar-league-dropdown-items');
            if (!container) return;

            const total = totalMatches !== undefined ? totalMatches : calendarMatches.length;
            let html = `
                <button type="button" onclick="selectCalendarLeague('All', null)" class="w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition ${calendarLeague === 'All' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-200 hover:bg-slate-800/80'}">
                    <div class="flex items-center gap-2 truncate">
                        <span class="w-4 h-4 flex items-center justify-center text-xs flex-shrink-0">🏆</span>
                        <span class="truncate font-medium">All Competitions</span>
                    </div>
                    <span class="text-[10px] font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${calendarLeague === 'All' ? 'bg-indigo-700 text-white' : 'bg-slate-800 text-slate-400'}">${total}</span>
                </button>
            `;

            leagues.forEach(l => {
                const isSelected = calendarLeague === l.name;
                const logoHtml = l.logo 
                    ? `<img src="${l.logo}" class="w-4 h-4 object-contain flex-shrink-0 rounded-sm" onerror="this.outerHTML='<span class=\\'w-4 h-4 flex items-center justify-center text-xs\\'>⚽</span>'">`
                    : `<span class="w-4 h-4 flex items-center justify-center text-xs">⚽</span>`;

                const safeName = l.name.replace(/'/g, "\\'");
                html += `
                    <button type="button" onclick="selectCalendarLeague('${safeName}', '${l.logo || ''}')" class="w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition ${isSelected ? 'bg-indigo-600 text-white font-bold' : 'text-slate-200 hover:bg-slate-800/80'}">
                        <div class="flex items-center gap-2 truncate min-w-0 pr-2">
                            ${logoHtml}
                            <span class="truncate" title="${l.name}">${l.name}</span>
                        </div>
                        <span class="text-[10px] font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${isSelected ? 'bg-indigo-700 text-white' : 'bg-slate-800 text-slate-400'}">${l.count}</span>
                    </button>
                `;
            });

            container.innerHTML = html;
        }

        function filterCalendarLeagueDropdownList() {
            const query = (document.getElementById('calendar-league-dropdown-search').value || '').toLowerCase().trim();
            const filtered = cachedCalendarLeaguesList.filter(l => l.name.toLowerCase().includes(query));
            renderCalendarLeagueDropdownItems(filtered, calendarMatches.length);
        }

        function selectCalendarLeague(val, logoUrl) {
            calendarLeague = val;
            const btnText = document.getElementById('calendar-league-btn-text');
            const btnLogo = document.getElementById('calendar-league-btn-logo');
            
            if (btnText) btnText.innerText = val === 'All' ? 'All Competitions' : val;
            if (btnLogo) {
                if (val === 'All' || !logoUrl) {
                    btnLogo.innerHTML = '🏆';
                } else {
                    btnLogo.innerHTML = `<img src="${logoUrl}" class="w-4 h-4 object-contain" onerror="this.outerHTML='<span>🏆</span>'"/>`;
                }
            }

            const menu = document.getElementById('calendar-league-dropdown-menu');
            if (menu) menu.classList.add('hidden');

            updateCalendarPillHighlight();
            filterCalendarMatches();
        }

        function quickFilterCalendarLeague(val) {
            const entry = cachedCalendarLeaguesList.find(l => l.name.toLowerCase().includes(val.toLowerCase()));
            selectCalendarLeague(val, entry ? entry.logo : null);
        }

        function updateCalendarPillHighlight() {
            const pills = document.querySelectorAll('#calendar-featured-pills .cal-pill-btn');
            pills.forEach(p => {
                if (p.innerText.toLowerCase().includes(calendarLeague.toLowerCase()) || (calendarLeague === "All" && p.innerText.includes("All"))) {
                    p.className = "cal-pill-btn active px-3 py-1 rounded-lg bg-indigo-600 text-white font-semibold whitespace-nowrap shadow-sm text-xs";
                } else {
                    p.className = "cal-pill-btn px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 font-medium whitespace-nowrap border border-slate-800 text-xs";
                }
            });
        }

        function clearCalendarSearch() {
            document.getElementById('calendar-search-input').value = '';
            document.getElementById('calendar-status-filter').value = 'ALL';
            quickFilterCalendarLeague('All');
        }

        function filterCalendarMatches() {
            const query = (document.getElementById('calendar-search-input').value || '').toLowerCase().trim();
            const statusFilter = document.getElementById('calendar-status-filter').value;
            const clearBtn = document.getElementById('calendar-clear-search-btn');

            if (query) {
                clearBtn.classList.remove('hidden');
            } else {
                clearBtn.classList.add('hidden');
            }

            const now = new Date();
            const todayStr = now.toISOString().split('T')[0];
            const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
            const tomorrowStr = tomorrow.toISOString().split('T')[0];

            let filtered = calendarMatches.filter(m => {
                // 1. Search Query filter (checks league, tournament, home, away)
                if (query) {
                    const matchText = `${m.tournament_name} ${m.tournament_category || ''} ${m.home_team.name} ${m.away_team.name}`.toLowerCase();
                    if (!matchText.includes(query)) return false;
                }

                // 2. League filter
                if (calendarLeague !== "All" && !m.tournament_name.toLowerCase().includes(calendarLeague.toLowerCase())) {
                    return false;
                }

                // 3. Status filter
                if (statusFilter === "SCHEDULED" && !m.auto_generate) return false;
                if (statusFilter === "UNSCHEDULED" && m.auto_generate) return false;

                // 4. Date filter
                if (currentCalendarDate !== 'all') {
                    const detail = (m.status_detail || '').toLowerCase();
                    const startTime = m.start_time ? m.start_time.split('T')[0] : null;

                    if (currentCalendarDate === 'today') {
                        const isToday = detail.includes('tonight') || detail.includes('live') || detail.includes('1h') || detail.includes('2h') || detail.includes('ht') || detail.includes("'") || startTime === todayStr;
                        if (!isToday && (detail.includes('tomorrow') || (startTime && startTime > todayStr))) return false;
                    } else if (currentCalendarDate === 'tomorrow') {
                        const isTomorrow = detail.includes('tomorrow') || startTime === tomorrowStr;
                        if (!isTomorrow) return false;
                    } else if (currentCalendarDate === 'weekend') {
                        // Next 3 days includes tomorrow and day after
                        const isNext3Days = detail.includes('tomorrow') || detail.includes('tonight') || (startTime && startTime >= todayStr);
                        if (!isNext3Days) return false;
                    }
                }

                return true;
            });

            const scheduledCount = calendarMatches.filter(m => m.auto_generate).length;
            const countBadge = document.getElementById('calendar-count-badge');
            const countLabel = document.getElementById('calendar-count-label');

            if (countBadge) countBadge.innerText = `${filtered.length} Matches`;
            if (countLabel) countLabel.innerText = `Showing ${filtered.length} fixtures • ${scheduledCount} pre-scheduled for Remote Desk`;

            renderCalendarGrid(filtered);
        }

        function renderCalendarGrid(matches) {
            const container = document.getElementById('calendar-matches-grid');

            if (matches.length === 0) {
                container.innerHTML = `
                    <div class="col-span-1 md:col-span-2 lg:col-span-3 text-center py-16 px-4 bg-[#070c16]/60 rounded-2xl border border-slate-800">
                        <span class="text-3xl">🔍</span>
                        <p class="text-slate-200 text-sm mt-3 font-bold">No matching fixtures found</p>
                        <p class="text-slate-500 text-xs mt-1">Try a different league search, switch date tabs, or clear filters.</p>
                        <button onclick="clearCalendarSearch()" class="mt-4 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-indigo-400 font-semibold border border-slate-700 transition shadow-sm">
                            ✕ Clear All Fixture Filters
                        </button>
                    </div>
                `;
                return;
            }

            container.innerHTML = matches.map(m => {
                const isTracked = m.auto_generate;
                const coverage = m.coverage || 'STANDARD';

                return `
                    <div class="p-4 rounded-xl bg-[#070c16] border ${isTracked ? 'border-emerald-500/60 bg-emerald-950/20 shadow-xl shadow-emerald-950/20' : 'border-slate-800 hover:border-slate-700/80'} flex flex-col justify-between gap-3 transition">
                        <!-- Top Metadata -->
                        <div class="flex justify-between items-center text-[11px] text-slate-400">
                            <div class="flex items-center gap-1.5 truncate max-w-[200px]">
                                ${m.tournament_logo_url ? `<img src="${m.tournament_logo_url}" class="w-4 h-4 object-contain flex-shrink-0" onerror="this.style.display='none'">` : ''}
                                <span class="font-bold text-slate-300 truncate" title="${m.tournament_name}">${m.tournament_name}</span>
                            </div>
                            <div class="flex items-center gap-1.5 flex-shrink-0">
                                ${isTracked ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-extrabold border border-emerald-500/30">ARMED</span>' : ''}
                                <span class="px-2 py-0.5 rounded-md bg-slate-800 text-emerald-400 font-mono font-bold">${m.status_detail}</span>
                            </div>
                        </div>

                        <!-- Teams with Logos -->
                        <div class="flex justify-between items-center text-sm font-bold text-white py-1">
                            <div class="flex items-center gap-2 flex-1 min-w-0">
                                ${m.home_team && m.home_team.logo_url ? `<img src="${m.home_team.logo_url}" class="w-6 h-6 object-contain flex-shrink-0 rounded-full bg-slate-800/80 p-0.5" onerror="this.style.display='none'">` : ''}
                                <span class="truncate font-semibold text-slate-100">${m.home_team.name}</span>
                            </div>
                            <span class="px-2.5 py-0.5 rounded-md bg-slate-800 text-xs font-mono text-slate-400 mx-2 flex-shrink-0">vs</span>
                            <div class="flex items-center justify-end gap-2 flex-1 min-w-0 text-right">
                                <span class="truncate font-semibold text-slate-100">${m.away_team.name}</span>
                                ${m.away_team && m.away_team.logo_url ? `<img src="${m.away_team.logo_url}" class="w-6 h-6 object-contain flex-shrink-0 rounded-full bg-slate-800/80 p-0.5" onerror="this.style.display='none'">` : ''}
                            </div>
                        </div>

                        <!-- Action Bar -->
                        <div class="pt-2.5 border-t border-slate-800/80 flex items-center justify-between gap-2 text-xs">
                            <div class="flex items-center gap-1.5">
                                <span class="text-[11px] text-slate-400">Coverage:</span>
                                <select id="cal-cov-${m.id}" onchange="onCalendarOptionChange('${m.id}', ${isTracked})" class="bg-[#0b1322] border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none font-medium">
                                    <option value="FULL" ${coverage === 'FULL' ? 'selected' : ''}>🔴 Full</option>
                                    <option value="STANDARD" ${coverage === 'STANDARD' ? 'selected' : ''}>🟡 Standard</option>
                                    <option value="RESULT_ONLY" ${coverage === 'RESULT_ONLY' ? 'selected' : ''}>🟢 Result Only</option>
                                </select>
                                <button onclick="openGraphicsModal('lineup', '${m.id}', '${m.home_team.name} vs ${m.away_team.name}')" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold flex items-center gap-1 border border-slate-700 transition" title="Preview Starting XI Pitch Board">
                                    <span>📋</span> <span>XI</span>
                                </button>
                            </div>

                            <button onclick="preScheduleMatch('${m.id}', ${!isTracked})" class="px-3 py-1.5 text-xs font-bold rounded-lg transition-all duration-150 ${isTracked ? 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/30' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20'}">
                                ${isTracked ? '✕ Remove' : '+ Pre-Schedule'}
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        async function onCalendarOptionChange(matchId, isTracked) {
            if (!isTracked) return;
            await preScheduleMatch(matchId, true);
        }

        async function preScheduleMatch(matchId, shouldTrack = true) {
            const covEl = document.getElementById(`cal-cov-${matchId}`);
            const coverage = covEl ? covEl.value : 'STANDARD';

            await fetch('/api/matches/configure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    match_id: matchId,
                    tracked: shouldTrack,
                    coverage: coverage,
                    auto_publish: true,
                    language: 'bn'
                })
            });

            showToast(shouldTrack ? "✓ Fixture pre-scheduled for Remote Desk!" : "✕ Fixture removed from Remote Desk");
            await fetchMatches();
            await fetchCalendarMatches();
        }

        // ================= Social Graphics Modal Logic =================
        let activeModalMatchId = null;
        let activeModalTab = "goal";

        function openGraphicsModal(type, matchId, title) {
            activeModalMatchId = matchId;
            activeModalTab = type || 'goal';
            
            const modal = document.getElementById('graphics-modal');
            const titleEl = document.getElementById('graphics-modal-title');
            const subEl = document.getElementById('graphics-modal-subtitle');
            
            if (title) titleEl.innerText = title;
            if (subEl) subEl.innerText = `High-resolution social visual for ${title || 'match'}`;
            
            modal.classList.remove('hidden');
            switchGraphicsTab(activeModalTab);
        }

        function openGraphicsModalForPost(postId, matchId, eventId, headline) {
            let initialType = 'goal';
            if (headline && (headline.includes('একাদশ') || headline.includes('Lineup') || headline.includes('Starting XI'))) {
                initialType = 'lineup';
            } else if (headline && (headline.includes('পূর্ণ সময়') || headline.includes('Full-Time') || headline.includes('ম্যাচ শেষ'))) {
                initialType = 'fulltime';
            }
            openGraphicsModal(initialType, matchId, headline);
        }

        function closeGraphicsModal() {
            const modal = document.getElementById('graphics-modal');
            modal.classList.add('hidden');
        }

        function switchGraphicsTab(tab) {
            activeModalTab = tab;
            
            // Highlight active tab
            ['goal', 'lineup', 'fulltime'].forEach(t => {
                const btn = document.getElementById(`tab-btn-${t}`);
                if (btn) {
                    if (t === tab) {
                        btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white transition flex items-center gap-1.5 shadow-sm";
                    } else {
                        btn.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1.5";
                    }
                }
            });

            // Show loading spinner
            const loading = document.getElementById('graphics-loading');
            const img = document.getElementById('graphics-preview-img');
            const dlBtn = document.getElementById('graphics-download-btn');
            
            loading.classList.remove('hidden');
            loading.innerHTML = '<span class="text-3xl animate-spin">⏳</span><span class="font-medium">Rendering HD Match Graphic...</span>';
            img.classList.add('hidden');

            const url = `/api/graphics/${tab}/${activeModalMatchId}?t=${Date.now()}`;
            img.src = url;
            dlBtn.href = url;
            dlBtn.download = `${activeModalMatchId}-${tab}-card.png`;
        }

        function onGraphicLoaded() {
            document.getElementById('graphics-loading').classList.add('hidden');
            document.getElementById('graphics-preview-img').classList.remove('hidden');
        }

        function onGraphicError() {
            const loading = document.getElementById('graphics-loading');
            loading.innerHTML = '<span class="text-rose-400 font-semibold">⚠️ Failed to generate image preview. Check match ID or logs.</span>';
        }

        function setupWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/live-events`);
            const badge = document.getElementById('ws-badge');

            ws.onopen = () => {
                badge.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2";
                badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-400"></span> <span>Live Socket</span>';
            };

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.topic === 'match_event') {
                        addEventToStream(msg.data);
                        fetchMatches();
                    } else if (msg.topic === 'post_created') {
                        fetchPosts();
                    }
                } catch (err) {
                    console.error('WS error:', err);
                }
            };

            ws.onclose = () => {
                badge.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center gap-2";
                badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-400"></span> <span>Reconnecting...</span>';
                setTimeout(setupWebSocket, 3000);
            };
        }

        function addEventToStream(data) {
            const container = document.getElementById('events-container');
            const ev = data.event;
            const match = data.match;

            if (container.querySelector('div.text-center')) {
                container.innerHTML = '';
            }

            const item = document.createElement('div');
            item.className = "p-3.5 rounded-xl bg-[#070c16] border border-cyan-500/30 text-xs flex flex-col gap-1.5 shadow-md";
            item.innerHTML = `
                <div class="flex justify-between items-center font-bold text-cyan-300">
                    <span class="truncate">${match.home_team.name} vs ${match.away_team.name}</span>
                    <span class="font-mono text-emerald-400 text-xs px-1.5 py-0.5 rounded bg-slate-800">${ev.minute}'</span>
                </div>
                <div class="text-white font-medium leading-relaxed">${ev.description}</div>
                <div class="text-slate-400 text-[10px] flex justify-between pt-1 border-t border-slate-800/80">
                    <span>Score: <strong>${ev.home_score} - ${ev.away_score}</strong></span>
                    <span class="font-mono text-slate-500">${ev.event_type}</span>
                </div>
            `;
            container.prepend(item);
        }

        window.onload = init;
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Night-Shift Interactive Dashboard."""
    return DASHBOARD_HTML
