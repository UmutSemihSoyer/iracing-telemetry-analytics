# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- `detect_stints`: pit turu + yakıt dolumu aynı pit'i iki kez sayıyordu (stint sayısı şişiyordu). Ardışık pit turları artık tek pit; ilk turda garajdan çıkış stint ayırmaz.
- `_enrich`: `LapDistPct` sabitken (araç pitte/garajda) `pd.cut` "Bin edges must be unique" ile çöküyordu; mikro sektörler artık sabit 0-1 kenarlarla hesaplanıyor.
- `predict_fuel_strategy` artık numpy yerine düz `float` döndürüyor.

### Added
- Sentetik telemetri üreticisi (`tests/synthetic.py`) ve `lap_classifier`, `detect_stints`, `predict_fuel_strategy`, `_enrich` testleri.
- Gerçek `.ibt` duman testi (`IBT_TEST_FILE` / `IBT_TEST_DIR`, `pytest -m realdata`).
- CI'da `pytest-cov` coverage raporu.

## [9.1.0] - 2026-05-04

### Added
- Professional README with dashboard preview.
- Local SQLite database persistence for session history.
- AI-powered driving feedback system.
- Professional MIT License and contribution guidelines.
- GitHub Release tagging system.

### Changed
- Improved `.ibt` parsing performance.
- Refactored UI for a more premium "dark mode" aesthetic.
- Enhanced corner detection algorithm for high-speed circuits.

### Fixed
- Fixed `IS_ELECTRON` NameError in `app.py`.
- Corrected `lap_classifier` import path issues.
- Fixed placeholder URLs in documentation.
