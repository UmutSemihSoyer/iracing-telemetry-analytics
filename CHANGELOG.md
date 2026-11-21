# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added (Faz 4)
- 🎯 **Apex & Braking Points** haritası (Sectors sekmesi): en iyi turda her viraj için fren başlangıcı (▼) ve apex (●, minimum hız). `services/track_markers.py`, `plotting/gps_maps.fig_apex_brake_map`, testleri.
- `SessionFlags` ve `PaceMode` kanalları artık dashboard DataFrame'ine alınıyor.
- Safety Car tespiti: bir turun en az %30'unda caution bayrağı (0x4000/0x8000) açıksa tur "Safety Car" olur (pit turları önceliklidir; eski hız/süre sezgisi yedek olarak durur).

### Notes (Faz 4)
- `PaceMode` bilinçli olarak kullanılmıyor: gerçek Sebring yarış dosyasında tüm oturum boyunca 4 dışı kalıp her turu yanlışlıkla Safety Car yapıyordu.

### Changed (Faz 3)
- `app.py` 725 satırdan ~45 satıra indi. Paylaşılan bağlam `app_context.py`'de, callback'ler `ui/callbacks/{ui,data,tab,session,export}_callbacks.py` altında. Davranış değişmedi: 41 callback'in id/input/state haritası altın kopyayla birebir aynı (`tests/golden_callbacks.json`).
- Hata/uyarı `print`'leri `utils.logger` ile loglanıyor; çıplak `except:` kalmadı.

### Fixed (Faz 3)
- Yeni plotly sürümlerinde `go.Scattermapbox` kaldırıldığı için Dynamics sekmesi çöküyordu; `go.Scattermap` kullanılıyor (eski sürümlerde otomatik geri dönüş). `requirements.txt`: `plotly>=5.24.0`.
- Eksik kanal içeren dosyada (ör. Brake/Throttle yok) sekmeler 500 ile çöküyordu; artık hata loglanıp okunur bir uyarı gösteriliyor.

### Added (Faz 3)
- Tarayıcısız uçtan uca testler (`tests/test_app_e2e.py`, `tests/dash_client.py`): Flask test client ile gerçek `/_dash-update-component` yolundan her sekmeyi ve pit penceresi callback'ini çağırır.

### Added (Faz 2)
- ⛽ **Fuel & Stints** sekmesi: KPI'lar, yakıt seviyesi grafiği (pit çizgileriyle), tur başı tüketim, stint karşılaştırma, stint ve pit durak tabloları, pit penceresi hesaplayıcı (tank + kalan tur).
- `services/fuel_service.py` (`lap_fuel_table`, `stint_summary`, `pit_stops`, `pit_window`), `plotting/fuel.py`, `ui/tabs/fuel.py` ve testleri.

### Fixed (Faz 2)
- `lap_classifier`: tur süresi `LapLastTime`'ın `max()` değeriyle alınıyordu; iRacing yeni turun ilk örneklerinde önceki turun süresini gösterdiği için daha yavaş eski tur süresi seçilebiliyor, ardışık turlar aynı süreyi alıyordu (tur sıralaması ve en hızlı tur bozuluyordu). Artık grubun son değeri kullanılıyor.

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
