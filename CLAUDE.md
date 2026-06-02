# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tafel Analyzer — a desktop application for electrochemical Tafel plot analysis. It reads measurement data (TDMS/CSV/Excel/COR), auto-detects segments, performs Tafel fitting, and provides visualization with multi-file comparison. Built with PySide6 (Qt).

## Commands

```bash
# Run GUI
python main.py

# Run CLI
python run_cli.py <file> [options]

# CLI options
python run_cli.py data/*.tdms --potential-formula "-[Vgs]+0.23" --current-formula "[Igs/area]/(2.4e-7+3)" --e-eq 0

# Install dependencies
pip install -r requirements.txt
```

## Architecture

Three layers, strictly separated:

### 1. `src/core/` — Pure business logic + shared rendering/utilities (no GUI imports)
- **`types.py`**: Frozen dataclasses (`TafelFit`, `SegmentInfo`, `PreparedSeries`, `FormulaResult`) and channel name constants
- **`readers.py`**: File I/O — TDMS, COR, CSV/Excel/XLSX via pandas
- **`formula.py`**: Formula parser/evaluator (`[ChannelName]` reference syntax, arithmetic ops)
- **`fitting.py`**: Tafel fitting — auto-segmentation detection, optimal window search, linear regression, manual fit
- **`export.py`**: Export to txt/npz/png, matplotlib plotting
- **`cli.py`**: argparse CLI entry point
- **`utils.py`**: Channel name resolution, CJK font helpers
- **`theme.py`**: Color/style constants, matplotlib RC config
- **`rendering.py`**: Matplotlib chart rendering, figure/axes state management
- **`comparison.py`**: Comparison chart rendering and export
- **`serialization.py`**: TafelFit/PreparedSeries/SegmentInfo dict conversion
- **`cache.py`**: Result cache key building, payload serialization
- **`logger.py`**: Application logging with rotating file handler

### 2. `src/ui/` — PySide6 GUI
- **`app.py`**: `QMainWindow` with 3-panel layout (activity bar → side stack → right stack)
- **`controllers/`**: `BaseAppController(QObject)` base class; `FileController`, `FittingController`, `ComparisonController`, `ExportController` — communicate via Qt Signals
- **`panels/`**: Side panel widgets — `FileSegmentPanel` (file list + segment list + params), `ComparisonPanel` (cross-file comparison), `PaletteSidebar` (color scheme management)
- **`central/`**: Right area — `ToolBar` (formulas + params + fit buttons), `ChartArea` (matplotlib Figure w/ QtAgg), `ChartToolBar` (save/manual/zoom/pan), `SummaryTable`, `PaletteWorkspace`
- **`theme.py`**: QSS stylesheet constants for all widgets (Tailwind-like palette)
- **`activity_bar.py`**: 48px vertical icon strip for panel switching

### Key patterns
- **Controller pattern**: Controllers hold `app` reference for state access, wire signals from widgets to actions, no UI code in controllers
- **App state**: Single `_app_state: dict` on `TafelAnalyzerApp` — all shared state lives here, accessible via `self.app._app_state`
- **matplotlib backend**: `QtAgg` (PySide6)
- **No tests exist** — no test framework, no test files, no coverage tooling

## Project Structure

```
src/
├── core/              # Pure logic + shared rendering/utilities
│   ├── types.py       # Data classes & constants
│   ├── readers.py     # File I/O
│   ├── formula.py     # Formula parsing
│   ├── fitting.py     # Tafel fitting
│   ├── export.py      # Export & plotting
│   ├── cli.py         # CLI
│   ├── utils.py       # Utilities
│   ├── theme.py       # Color/style constants
│   ├── rendering.py   # Matplotlib chart rendering
│   ├── comparison.py  # Comparison chart rendering
│   ├── serialization.py # Data serialization
│   ├── cache.py       # Result caching
│   └── logger.py      # Application logging
├── ui/                # PySide6 GUI
│   ├── controllers/
│   ├── panels/
│   └── central/
main.py                # GUI entry point
run_cli.py             # CLI entry point
TafelAnalyzer_Setup.iss # Inno Setup installer config
data/                  # Sample .tdms files
```

## Build & Package

- Windows installer: Inno Setup via `TafelAnalyzer_Setup.iss`
- No pyproject.toml, no Makefile, no build system
- PyInstaller for standalone EXE (target dir: `dist/TafelAnalyzer/`)

## Important constraints

- **Windows target**: This is a Windows desktop app (electrochemistry lab environment)
- **CJK support**: GUI includes Chinese labels and CJK font handling
- **Layered architecture**: `ui/` depends on `core/` — no duplication of logic
