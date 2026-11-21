# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed (paketleme / başlatma)
- `electron/package.json` `build.files` listesi eski düz dosya düzenine göre yazılmıştı (`../ibt_parser.py` vb.); mevcut `core/`, `services/`, `models/`, `utils/`, `app_context.py`, `main.py`, `config.yaml` düzenine güncellendi, test mevcut yolları doğrular. Paketli `.exe` derlemesi denenmedi.
- `python app.py` artık `--port` bayrağını dikkate alır (bilinmeyen `--electron` yok sayılır).

### Notes
- Büyük dosyalar için tembel yükleme yapılmadı: ölçüm — 235 MB dosya tam ayrıntıyla 2,5 sn, ~170 MB bellek; mevcut Endurance/Ultra Lazy downsample modları yeterli.

### Added (Faz 6c)
- 🔧 **Setup differences** (Team sekmesi): yüklü dosyalar arasında farklı olan sayısal setup parametreleri (dosyaların içine gömülü `CarSetup`'tan), sürücü bazında ve fark (Spread) ile. Tanımlayıcıdır; birkaç dosyayla neden-sonuç çıkarılamayacağı için korelasyon/tahmin yok.
- Setup sınıflandırma ML modeli bilinçli olarak yapılmadı: veritabanında etiketli setup yok (2 oturum, 0 setup) ve pist başına 2–5 dosya istatistiksel olarak yetersiz.

### Fixed (Faz 6c)
- "Load team" ile yüklenen dosyalarda sürücü adı, pist klasöründen (ör. "Watkins") alınıyordu; artık kök altındaki sürücü klasöründen alınır (`load_ibt_from_path(driver_name=...)`).

### Added (Faz 6b)
- ⚠️ **Flagged laps** kartı (Overview): uçuş turlarında yavaş tur (medyana göre robust z-skor > 3.5 ve en az %2 yavaş) ve tur ortasında durma/spin (hız < 3 m/s, pit dışı) işaretlenir. `services/lap_anomalies.py` + testleri. Gerçek Watkins dosyalarında yavaş turlar durma/spin ile örtüştü, temiz turlar işaretlenmedi.

### Added (Faz 6)
- 🔮 **Pace model** (Fuel & Stints sekmesi): tur süresi = taban + yakıt etkisi + lastik yaşı etkisi, Huber regresyonla (aykırı turlara dayanıklı). Yakıt ve yaş aynı stint içinde doğrusal bağlı olduğundan ayrıştırılamıyorsa tek "net trend" (sn/tur) raporlanır; R² ve kalite (good/fair/weak) gösterilir. `services/pace_model.py` (`fit_pace_model`, `predict_laps`, `stint_time`), `fig_pace_model`, testleri.
- Gerçek Watkins verisinde uyum zayıf (R² ≈ 0.03–0.06): tur süreleri gürültü baskın; arayüz bunu açıkça söyler.

### Added (Faz 5b)
- Klasör taramasından sonra **👥 Team compare**: takım kökü (`<kök>/<sürücü>/.../*.ibt`) taranınca birden çok sürücünün sürdüğü pistler listelenir; "Load team" her sürücünün o pistteki en dolu (en büyük) dosyasını tek tıkla yükler (en fazla 6 sürücü). `services/team_loader.py` + testleri.

### Added (Faz 5)
- 👥 **Team** sekmesi: aynı pist için yüklenen birden çok dosyayı karşılaştırır — sürücü tablosu (en iyi/medyan tur, tutarlılık, yakıt/tur, azami hız, fark), en iyi tur farkı grafiği ve pist dilimi (20 dilim) × sürücü ısı haritası (en hızlıya göre kaybedilen süre). Farklı pistler karışırsa uyarır; aynı sürücünün birden çok dosyası `#n` ile ayrılır.
- `services/team_service.py`, `plotting/team.py`, `ui/tabs/team.py` ve testleri.

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
