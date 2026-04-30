# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tafel Analyzer — a desktop application for electrochemical Tafel plot analysis. It reads measurement data (TDMS/CSV/Excel/COR), auto-detects segments, performs Tafel fitting, and provides visualization with multi-file comparison. Currently migrating from CustomTkinter to PySide6.

## Commands

```bash
# Run GUI
python main.py

# Run CLI
python run_cli.py <file> [options]

# CLI options
python run_cli.py data/*.tdms --potential-formula "-[Vgs]+0.23" --current-formula "[Igs/area]/(2.4e-7+3)" --e-eq 0

# Run refactoring verification (checks cross-module consistency during migration)
python src/scripts/verify_refactor.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture

Three layers, strictly separated:

### 1. `src/core/` — Pure business logic (no GUI imports)
- **`types.py`**: Frozen dataclasses (`TafelFit`, `SegmentInfo`, `PreparedSeries`, `FormulaResult`) and channel name constants
- **`readers.py`**: File I/O — TDMS, COR, CSV/Excel/XLSX via pandas
- **`formula.py`**: Formula parser/evaluator (`[ChannelName]` reference syntax, arithmetic ops)
- **`fitting.py`**: Tafel fitting — auto-segmentation detection, optimal window search, linear regression, manual fit
- **`export.py`**: Export to txt/npz/png, matplotlib plotting
- **`cli.py`**: argparse CLI entry point
- **`utils.py`**: Channel name resolution, CJK font helpers

### 2. `src/gui/` — Legacy CustomTkinter GUI (being replaced)
- Full app with TkinterDnD2 drag-drop, CTk widgets, matplotlib TkAgg
- Controllers in `src/gui/controllers/` (FileManager, FittingController, ExportManager, ComparisonManager, SegmentPanel)

### 3. `src/gui_qt/` — New PySide6 GUI (active migration)
- **`app.py`**: `QMainWindow` with 3-panel layout (activity bar → side stack → right stack)
- **`controllers/`**: `BaseAppController(QObject)` base class; `FileController`, `FittingController`, `ComparisonController`, `ExportController` — communicate via Qt Signals
- **`panels/`**: Side panel widgets — `FileSegmentPanel` (file list + segment list + params), `ComparisonPanel` (cross-file comparison), `PaletteSidebar` (color scheme management)
- **`central/`**: Right area — `ToolBar` (formulas + params + fit buttons), `ChartArea` (matplotlib Figure w/ QtAgg), `ChartToolBar` (save/manual/zoom/pan), `SummaryTable`, `PaletteWorkspace`
- **`theme.py`**: QSS stylesheet constants for all widgets (Tailwind-like palette)
- **`activity_bar.py`**: 48px vertical icon strip for panel switching

### Key patterns
- **Controller pattern**: Controllers hold `app` reference for state access, wire signals from widgets to actions, no UI code in controllers
- **App state**: Single `_app_state: dict` on `TafelAnalyzerApp` — all shared state lives here, accessible via `self.app._app_state`
- **Migration status**: `gui_qt` is replacing `gui`. Recent commits show progressive migrating of controllers, panels, and removing old modules.
- **matplotlib backend**: `QtAgg` for PySide6, `TkAgg` in legacy
- **No tests exist** — no test framework, no test files, no coverage tooling

## Project Structure

```
src/
├── core/              # Pure logic (no GUI deps)
│   ├── types.py       # Data classes & constants
│   ├── readers.py     # File I/O
│   ├── formula.py     # Formula parsing
│   ├── fitting.py     # Tafel fitting
│   ├── export.py      # Export & plotting
│   ├── cli.py         # CLI
│   └── utils.py       # Utilities
├── gui/               # Legacy (CustomTkinter)
│   └── controllers/
├── gui_qt/            # New (PySide6)
│   ├── controllers/
│   ├── panels/
│   └── central/
├── scripts/
│   └── verify_refactor.py
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
- **In-place migration**: `gui_qt/` depends on `core/` (same as `gui/`) — no duplication of core logic
- **Verify script**: Run `src/scripts/verify_refactor.py` after refactoring to catch parameter mismatches and stale app attribute references
