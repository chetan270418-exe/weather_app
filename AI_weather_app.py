#!/usr/bin/env python3
"""
Advanced Weather App
---------------------
A single desktop GUI app (built with tkinter) that you launch once and
keep using to look up weather for any city, see a short forecast trend
chart, and get an AI-generated summary + clothing/activity suggestion
powered by the Claude API.

Libraries used:
    tkinter      - GUI (standard library)
    requests     - HTTP calls to the weather service
    matplotlib   - forecast trend chart embedded in the window
    anthropic    - official Claude API SDK, for the AI insight feature

Weather data: wttr.in (free, no API key needed)
AI insight:   Claude API (needs your own ANTHROPIC_API_KEY)

Setup:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY="sk-ant-..."   # optional, enables AI insights
    python3 weather_app_advanced.py
"""

import os
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import ttk, scrolledtext

import requests

try:
    import anthropic
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

WEATHER_URL = "https://wttr.in/{city}"
TIMEOUT_SECONDS = 10
AI_MODEL = "claude-sonnet-5"   # swap to "claude-haiku-4-5-20251001" for a cheaper/faster response
MAX_HISTORY = 5

COLORS = {
    "bg": "#12121c",
    "surface": "#1c1c2b",
    "surface_alt": "#242438",
    "accent": "#5eb8ff",
    "accent_soft": "#2b3550",
    "text": "#e7e9ee",
    "muted": "#8a8fa3",
    "error": "#ff6b6b",
}


def pick_font() -> str:
    """Pick the first available cross-platform font so the UI looks decent
    on Windows, macOS, and Linux alike."""
    preferred = ["Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
    available = set(tkfont.families())
    for name in preferred:
        if name in available:
            return name
    return "TkDefaultFont"


def weather_icon(description: str) -> str:
    """Map a text weather description to an emoji icon."""
    d = description.lower()
    if "thunder" in d:
        return "⛈️"
    if "snow" in d or "sleet" in d or "ice" in d:
        return "❄️"
    if "rain" in d or "drizzle" in d or "shower" in d:
        return "🌧️"
    if "fog" in d or "mist" in d or "haze" in d:
        return "🌫️"
    if "overcast" in d:
        return "☁️"
    if "partly cloudy" in d or "cloudy" in d:
        return "⛅"
    if "clear" in d or "sunny" in d:
        return "☀️"
    return "🌡️"


# --------------------------------------------------------------------------
# Weather data
# --------------------------------------------------------------------------

def get_weather(city: str) -> dict:
    """Fetch current conditions + short forecast for a city from wttr.in."""
    try:
        response = requests.get(
            WEATHER_URL.format(city=city),
            params={"format": "j1"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise RuntimeError("The request timed out. Check your internet connection.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Could not connect. Check your internet connection.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Server returned an error: {e}")
    except ValueError:
        raise RuntimeError("Received an unreadable response from the server.")


# --------------------------------------------------------------------------
# AI insight (Claude API)
# --------------------------------------------------------------------------

def build_weather_summary(city: str, data: dict) -> str:
    current = data["current_condition"][0]
    lines = [
        f"City: {city}",
        f"Condition: {current['weatherDesc'][0]['value']}",
        f"Temperature: {current['temp_C']}C, feels like {current['FeelsLikeC']}C",
        f"Humidity: {current['humidity']}%",
        f"Wind: {current['windspeedKmph']} km/h {current['winddir16Point']}",
    ]
    for day in data.get("weather", [])[:3]:
        lines.append(f"{day['date']}: high {day['maxtempC']}C / low {day['mintempC']}C")
    return "\n".join(lines)


def get_ai_insight(city: str, data: dict) -> str:
    """Ask Claude for a friendly summary + clothing/activity suggestion."""
    if not AI_AVAILABLE:
        return "The 'anthropic' package isn't installed. Run: pip install anthropic"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "No ANTHROPIC_API_KEY found in your environment.\n"
            "Get a key at console.anthropic.com, then set it and restart:\n"
            "  export ANTHROPIC_API_KEY=\"your-key-here\"      (macOS/Linux)\n"
            "  setx ANTHROPIC_API_KEY \"your-key-here\"        (Windows)"
        )

    summary = build_weather_summary(city, data)
    prompt = (
        "Here is today's weather data:\n\n"
        f"{summary}\n\n"
        "In 4-5 friendly, conversational sentences: describe how the day will "
        "feel, suggest appropriate clothing, and recommend one activity suited "
        "to these conditions."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=AI_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in message.content if b.type == "text").strip()
    except anthropic.AuthenticationError:
        return "Authentication failed. Check that your ANTHROPIC_API_KEY is valid."
    except anthropic.RateLimitError:
        return "Rate limit reached. Wait a moment and try again."
    except anthropic.APIConnectionError:
        return "Could not connect to the Claude API. Check your internet connection."
    except anthropic.APIStatusError as e:
        return f"Claude API returned an error: {e}"
    except Exception as e:
        return f"AI insight unavailable: {e}"


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

class WeatherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Weather App")
        self.geometry("900x760")
        self.configure(bg=COLORS["bg"])
        self.minsize(760, 680)

        self.font_family = pick_font()
        self.history = []          # list of recently searched cities
        self.last_city = None
        self.last_data = None

        self._build_style()
        self._build_layout()

    # ---- styling -----------------------------------------------------

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])

        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"],
                         font=(self.font_family, 10))
        style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"],
                         font=(self.font_family, 10))
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["accent"],
                         font=(self.font_family, 20, "bold"))
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"],
                         font=(self.font_family, 9))
        style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"],
                         font=(self.font_family, 9))
        style.configure("Big.TLabel", background=COLORS["surface"], foreground=COLORS["text"],
                         font=(self.font_family, 26, "bold"))
        style.configure("Icon.TLabel", background=COLORS["surface"], foreground=COLORS["text"],
                         font=(self.font_family, 30))

        style.configure("TButton", background=COLORS["accent_soft"], foreground=COLORS["text"],
                         borderwidth=0, focusthickness=0, font=(self.font_family, 10, "bold"),
                         padding=8)
        style.map("TButton", background=[("active", COLORS["accent"])])

        style.configure("History.TButton", background=COLORS["surface_alt"], foreground=COLORS["muted"],
                         borderwidth=0, font=(self.font_family, 8), padding=4)
        style.map("History.TButton", background=[("active", COLORS["accent_soft"])])

        style.configure("TEntry", fieldbackground=COLORS["surface_alt"], foreground=COLORS["text"],
                         borderwidth=0, insertcolor=COLORS["text"])

    # ---- layout --------------------------------------------------------

    def _build_layout(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        # Title
        ttk.Label(root, text="🌦  Advanced Weather App", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Search a city, view the forecast trend, and get an AI weather insight.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        # Search bar
        search_frame = ttk.Frame(root)
        search_frame.pack(fill="x", pady=(0, 4))

        self.city_var = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=self.city_var, font=(self.font_family, 12))
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        entry.bind("<Return>", lambda e: self.start_search())
        entry.focus_set()

        self.search_btn = ttk.Button(search_frame, text="Search", command=self.start_search)
        self.search_btn.pack(side="left", padx=(8, 0))

        # Recent searches row
        self.history_frame = ttk.Frame(root)
        self.history_frame.pack(fill="x", pady=(6, 8))

        # Status line
        self.status_var = tk.StringVar(value="Enter a city to get started.")
        self.status_label = ttk.Label(root, textvariable=self.status_var, style="Muted.TLabel")
        self.status_label.pack(anchor="w", pady=(0, 10))

        # Current conditions + forecast row
        content = ttk.Frame(root)
        content.pack(fill="x", pady=(0, 12))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)

        self.current_card = ttk.Frame(content, style="Card.TFrame", padding=16)
        self.current_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.forecast_card = ttk.Frame(content, style="Card.TFrame", padding=16)
        self.forecast_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._render_placeholder_cards()

        # Chart
        chart_card = ttk.Frame(root, style="Card.TFrame", padding=(12, 8))
        chart_card.pack(fill="x", pady=(0, 12))
        self.fig = Figure(figsize=(7.5, 2.2), dpi=100, facecolor=COLORS["surface"])
        self.ax = self.fig.add_subplot(111)
        self._style_axes()
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.draw()

        # AI insight section
        ai_header = ttk.Frame(root)
        ai_header.pack(fill="x")
        ttk.Label(ai_header, text="AI Insight", style="TLabel",
                  font=(self.font_family, 12, "bold")).pack(side="left")
        self.ai_btn = ttk.Button(ai_header, text="✨ Get AI Insight", command=self.start_ai_insight,
                                  state="disabled")
        self.ai_btn.pack(side="right")

        self.ai_text = scrolledtext.ScrolledText(
            root, height=6, wrap="word", bg=COLORS["surface"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat", font=(self.font_family, 10),
            padx=10, pady=10,
        )
        self.ai_text.pack(fill="both", expand=True, pady=(6, 0))
        self._set_ai_text(
            "Search a city, then click \"Get AI Insight\" for a friendly weather "
            "summary and suggestions." if AI_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY")
            else "Set the ANTHROPIC_API_KEY environment variable and restart the app to enable this feature."
        )
        self.ai_text.config(state="disabled")

    def _style_axes(self):
        self.ax.clear()
        self.ax.set_facecolor(COLORS["surface"])
        for spine in self.ax.spines.values():
            spine.set_color(COLORS["muted"])
        self.ax.tick_params(colors=COLORS["muted"], labelsize=8)
        self.ax.set_title("3-Day Forecast Trend", color=COLORS["text"], fontsize=10, loc="left")

    def _render_placeholder_cards(self):
        for widget in self.current_card.winfo_children():
            widget.destroy()
        for widget in self.forecast_card.winfo_children():
            widget.destroy()
        ttk.Label(self.current_card, text="No city searched yet.", style="CardMuted.TLabel").pack()
        ttk.Label(self.forecast_card, text="Forecast will appear here.", style="CardMuted.TLabel").pack()

    # ---- history buttons ------------------------------------------------

    def _refresh_history_buttons(self):
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        if not self.history:
            return
        ttk.Label(self.history_frame, text="Recent:", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        for city in self.history:
            btn = ttk.Button(self.history_frame, text=city, style="History.TButton",
                              command=lambda c=city: self._search_from_history(c))
            btn.pack(side="left", padx=2)

    def _search_from_history(self, city):
        self.city_var.set(city)
        self.start_search()

    def _remember_city(self, city):
        if city in self.history:
            self.history.remove(city)
        self.history.insert(0, city)
        self.history = self.history[:MAX_HISTORY]
        self._refresh_history_buttons()

    # ---- status helpers ---------------------------------------------------

    def set_status(self, message, error=False):
        self.status_var.set(message)
        self.status_label.configure(style="Error.TLabel" if error else "Muted.TLabel")

    def _set_ai_text(self, text):
        self.ai_text.config(state="normal")
        self.ai_text.delete("1.0", "end")
        self.ai_text.insert("1.0", text)
        self.ai_text.config(state="disabled")

    # ---- search flow -----------------------------------------------------

    def start_search(self):
        city = self.city_var.get().strip()
        if not city:
            self.set_status("Please enter a city name.", error=True)
            return

        self.search_btn.config(state="disabled")
        self.ai_btn.config(state="disabled")
        self.set_status(f"Fetching weather for '{city}'...")
        threading.Thread(target=self._fetch_worker, args=(city,), daemon=True).start()

    def _fetch_worker(self, city):
        try:
            data = get_weather(city)
            self.after(0, lambda: self._on_fetch_success(city, data))
        except RuntimeError as e:
            self.after(0, lambda: self._on_fetch_error(str(e)))

    def _on_fetch_success(self, city, data):
        self.last_city = city
        self.last_data = data
        self.search_btn.config(state="normal")
        if AI_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
            self.ai_btn.config(state="normal")
        self.set_status(f"Showing weather for {city}.")
        self._remember_city(city)
        self._render_current(data)
        self._render_forecast(data)
        self._render_chart(data)

    def _on_fetch_error(self, message):
        self.search_btn.config(state="normal")
        self.set_status(message, error=True)

    # ---- rendering ---------------------------------------------------------

    def _render_current(self, data):
        for widget in self.current_card.winfo_children():
            widget.destroy()

        current = data["current_condition"][0]
        area = data["nearest_area"][0]
        place = area["areaName"][0]["value"]
        region = area["region"][0]["value"]
        country = area["country"][0]["value"]
        location = ", ".join(p for p in (place, region, country) if p)

        description = current["weatherDesc"][0]["value"]
        icon = weather_icon(description)

        ttk.Label(self.current_card, text=location, style="Card.TLabel",
                  font=(self.font_family, 11, "bold")).pack(anchor="w")
        ttk.Label(self.current_card, text=icon, style="Icon.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(self.current_card, text=f"{current['temp_C']}°C", style="Big.TLabel").pack(anchor="w")
        ttk.Label(self.current_card, text=description, style="CardMuted.TLabel").pack(anchor="w", pady=(0, 8))

        details = [
            f"Feels like: {current['FeelsLikeC']}°C",
            f"Humidity: {current['humidity']}%",
            f"Wind: {current['windspeedKmph']} km/h {current['winddir16Point']}",
            f"Pressure: {current['pressure']} hPa",
            f"Visibility: {current['visibility']} km",
        ]
        for line in details:
            ttk.Label(self.current_card, text=line, style="Card.TLabel").pack(anchor="w", pady=1)

    def _render_forecast(self, data):
        for widget in self.forecast_card.winfo_children():
            widget.destroy()

        days = data.get("weather", [])[:3]
        row = ttk.Frame(self.forecast_card, style="Card.TFrame")
        row.pack(fill="x")
        for i, day in enumerate(days):
            date_obj = datetime.strptime(day["date"], "%Y-%m-%d")
            weekday = date_obj.strftime("%a")
            noon = day["hourly"][min(4, len(day["hourly"]) - 1)]
            desc = noon["weatherDesc"][0]["value"]
            icon = weather_icon(desc)

            cell = ttk.Frame(row, style="Card.TFrame", padding=8)
            cell.grid(row=0, column=i, sticky="nsew", padx=4)
            row.columnconfigure(i, weight=1)

            ttk.Label(cell, text=weekday, style="Card.TLabel", font=(self.font_family, 10, "bold")).pack()
            ttk.Label(cell, text=icon, style="Card.TLabel", font=(self.font_family, 20)).pack(pady=4)
            ttk.Label(cell, text=f"{day['maxtempC']}° / {day['mintempC']}°C",
                      style="Card.TLabel").pack()
            ttk.Label(cell, text=desc, style="CardMuted.TLabel", wraplength=110,
                      justify="center").pack(pady=(4, 0))

    def _render_chart(self, data):
        self._style_axes()
        days = data.get("weather", [])[:3]
        labels = [datetime.strptime(d["date"], "%Y-%m-%d").strftime("%a") for d in days]
        highs = [float(d["maxtempC"]) for d in days]
        lows = [float(d["mintempC"]) for d in days]

        self.ax.plot(labels, highs, marker="o", color=COLORS["accent"], label="High °C")
        self.ax.plot(labels, lows, marker="o", color=COLORS["muted"], label="Low °C")
        self.ax.legend(facecolor=COLORS["surface"], labelcolor=COLORS["text"], fontsize=8,
                        frameon=False)
        self.fig.tight_layout()
        self.canvas.draw()

    # ---- AI insight flow -----------------------------------------------

    def start_ai_insight(self):
        if not self.last_city or not self.last_data:
            return
        self.ai_btn.config(state="disabled")
        self._set_ai_text("Thinking...")
        threading.Thread(target=self._ai_worker, daemon=True).start()

    def _ai_worker(self):
        result = get_ai_insight(self.last_city, self.last_data)
        self.after(0, lambda: self._on_ai_done(result))

    def _on_ai_done(self, result):
        self._set_ai_text(result)
        self.ai_btn.config(state="normal")


def main():
    app = WeatherApp()
    # define an error style now that the app (and ttk.Style) exists
    style = ttk.Style(app)
    style.configure("Error.TLabel", background=COLORS["bg"], foreground=COLORS["error"],
                     font=(app.font_family, 9))
    app.mainloop()


if __name__ == "__main__":
    main()