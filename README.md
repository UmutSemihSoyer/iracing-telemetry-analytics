# iRacing Telemetry Analytics (Professional Desktop Edition)

[![Python CI](https://github.com/UmutSemihSoyer/iracing-telemetry-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/UmutSemihSoyer/iracing-telemetry-analytics/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

![Dashboard Preview](assets/dashboard_preview.png)

A high-performance, **native desktop platform** for professional **iRacing** telemetry analysis. Built with Python for data science and **Electron** for a premium desktop experience.

---

## 🖥️ Professional Desktop Experience

Unlike basic telemetry scripts, this platform is designed as a standalone desktop application:
- **Electron Integration:** Runs in a dedicated window with a native look and feel.
- **Native File Dialogs:** Seamlessly browse your `Documents/iRacing/telemetry` folder using OS-native pickers.
- **Standalone Execution:** Can be packaged into a single `.exe` for easy distribution.
- **High Performance:** Multi-process architecture (Python backend + Electron frontend).

---

## Features

- **`.ibt` File Parser:** Reads iRacing's binary telemetry format and converts it into structured Pandas DataFrames.
- **Lap Classification:** Automatically categorizes laps as *Best Lap*, *In-lap*, *Out-lap*, *Invalid*, or *Safety Car* lap.
- **Corner & Sector Detection:** Uses track position and G-Force data to automatically detect corners and divide the circuit into sectors.
- **Advanced Telemetry Metrics:** Calculates slip angle, trail braking score, throttle application points, and more.
- **Tire Analysis:** Deep dive into tire behavior, temperature distribution, and degradation patterns across a stint.
- **Setup Advisor:** Provides data-driven car setup recommendations based on telemetry evidence.
- **AI-Powered Feedback:** Analyzes driving telemetry and delivers coaching feedback to help improve lap times.
- **Interactive Dashboard:** Multi-tab interface for Overview, Dynamics, Brakes, Tires, and GPS Map views.
- **PDF Report Export:** Generates professional session reports with charts and analysis.

---

## Architecture

```
iracingf1/
├── electron/              # Desktop app wrapper (Main & Preload)
├── app.py                 # Core Dash application server
├── main.py                # Launcher
├── core/                  # Data science engine (Physics & ML)
├── services/              # Persistence, PDF & AI services
├── ui/                    # Dash UI components
├── plotting/              # Professional chart templates
└── assets/                # Styling and branding
```

---

## Setup & Installation

### Prerequisites
- Python 3.9+
- An iRacing subscription (for `.ibt` telemetry files)

### Install

1. Clone the repository:
   ```bash
   git clone https://github.com/UmutSemihSoyer/iracing-telemetry-analytics.git
   cd iracing-telemetry-analytics
   ```

2. (Recommended) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   source venv/bin/activate # macOS/Linux
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

### Run the Dashboard

```bash
python main.py
```

Then open your browser and navigate to: **`http://127.0.0.1:8050`**

### Load a Telemetry File

1. In the dashboard, use the **file upload area** to drag & drop or select an `.ibt` file.
   - iRacing saves telemetry files to: `Documents\iRacing\telemetry\`
2. The app will automatically parse the file, classify laps, and populate all analysis tabs.

### Where to Find `.ibt` Files

iRacing must have **telemetry logging enabled** in-game:
- Go to **Options → Sports → Enable Disk Logging**
- After a session, your `.ibt` files will be in: `C:\Users\<YourName>\Documents\iRacing\telemetry\`

---

## License

MIT License — see [LICENSE](LICENSE) for details.
