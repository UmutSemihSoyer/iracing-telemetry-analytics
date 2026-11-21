# iRacing Telemetry Analytics — Proje Yol Haritası (PROJECT_ROADMAP.md)

Bu döküman, projenin mevcut durumu, yapılması gereken teknik iyileştirmeler ve gelecek vizyonunu tek bir yerde toplar. ✅ İşaretli olanlar tamamlanmıştır.

---

## 🗺️ 0. Güncel Faz Planı (Kasım 2026)

| Faz | Kapsam | Durum |
|-----|--------|-------|
| 0 | Git hijyeni, .gitignore, yol haritası güncelleme | ✅ |
| 1 | Sentetik veriyle testler: `lap_classifier`, `detect_stints`, `predict_fuel_strategy`; CI'da coverage; gerçek .ibt ile duman testi | ⏳ |
| 2 | Yakıt/Stint sekmesi: tur başı tüketim, pit penceresi, sürücü değişimi tespiti, stint karşılaştırma | ⏳ |
| 3 | `app.py`'yi `ui/callbacks` modüllerine bölme, logging (`utils/logger`), `except:` temizliği, büyük dosya performansı | ⏳ |
| 4 | Teorik en iyi tur, safety car tespiti, apex/fren noktası işaretleri | ⏳ |
| 5 | Takım entegrasyonu: AutoTelemetry ile inen çok sürücülü dosyaların toplu analizi, sürücü karşılaştırma | ⏳ |
| 6 | ML (anomali, setup sınıflandırma) | ⏳ |

---

## 🛠️ 1. Mevcut Altyapı & Teknik Borçlar (Kısa Vade)
*Uygulamanın kararlılığını ve kullanıcı deneyimini artıracak düzeltmeler.*

- [x] **Electron Masaüstü Entegrasyonu**: Native uygulama olarak çalışma yeteneği.
- [x] **Native Dosya İşleme**: 500MB+ dosyalar için tarayıcı limitlerini aşan yerel okuma sistemi.
- [x] **Gelişmiş Dosya Yükleme**: Drag-and-drop ve sürücü bazlı kutu sistemi.
- [~] **Yakıt Analizi**: `predict_fuel_strategy` ve `detect_stints` servis katmanında yazıldı; arayüze (sekme) bağlanması ve testleri Faz 1-2'de.
- [ ] **Hata Yönetimi (Error Handling)**: Bozuk dosya veya eksik veri durumunda kullanıcıya dostane uyarılar gösterilmesi.
- [ ] **Kanal Filtreleme Performansı**: Büyük dosyalarda (24h yarış) hızı artırmak için "Lazy Loading" veri okuma.
- [ ] **Safety Car Tespiti**: Pace car turlarını otomatik tespit edip analiz dışı bırakma veya işaretleme.

---

## 🏁 2. Gelişmiş Viraj & Sektör Analizi (Sektör Map)
*Sürücü performansını milimetrik verilerle analiz edin.*

- [ ] **Apex Visualizer**: Her virajın apex noktasının haritada işaretlenmesi ve üzerine hız farkının (ref vs current) yazılması.
- [ ] **Braking Point Markers**: Fren noktalarının haritada işaretlenmesi ve mesafe farklarının (m) gösterilmesi.
- [ ] **Corner Zoom Overlay**: Tıklanan virajın büyütülmüş hali ve sürüş çizgilerinin (Line comparison) kıyaslanması.
- [ ] **G-Force Heatmap**: Pist üzerindeki yanal ve boylamsal G yüklerinin ısı haritası olarak gösterilmesi.
- [ ] **Apex Kaçırma Analizi**: İdeal hat ile sürücünün izi arasındaki mesafenin ölçümü.
- [ ] **Theoretical Best Lap (Stitched)**: Oturumdaki en iyi sektörlerin birleştirilip "mükemmel tur" zamanının hesaplanması.

---

## 🚦 3. Sürüş Tekniği & Dinamik Analiz
*Sürücünün direksiyon ve pedal kalitesini puanlayın.*

- [x] **Driving Style Metrics**: Trail-brake, Throttle smoothness ve Coasting metrikleri.
- [ ] **Vites Değişim Kaybı (Shift Efficiency)**: Vites geçişlerindeki devir kaybı ve zamanlama optimizasyonu.
- [ ] **Slip Angle (Kayma Açısı)**: Lastiklerin limitin neresinde olduğunun hesaplanarak gösterilmesi.
- [ ] **ABS & TC Müdahale Takibi**: Elektronik sistemlerin nerede ve ne kadar süreyle devreye girdiği.

---

## 🧠 4. Machine Learning & Yapay Zeka (Orta/Uzun Vade)
*Veriden öğrenen akıllı sistemler.*

- [x] **Otomatik Anomali Tespiti**: Sürüşteki hatalı noktaları (spin, kilitlenme vb.) otomatik bulan model.
- [ ] **Data Pipeline**: `setup_rating` üzerinden toplanan verilerin ML eğitimi için dataset haline getirilmesi.
- [ ] **XGBoost Regressor**: Setup ve pist koşullarına göre "Tahmini Tur Süresi" hesaplama.
- [ ] **Setup Classifier**: Telemetri verilerinden setup'ın kalitesini (1-5 yıldız) tahmin eden model.

---

## 📄 5. Raporlama & Dışa Aktarma
- [x] **Profesyonel PDF Raporu**: v9.0 standartlarında gelişmiş görsel raporlama.
- [ ] **AI Feedback PDF Entegrasyonu**: AI Engineer'ın ürettiği yorumların rapora dahil edilmesi.
- [ ] **Dil Seçeneği**: Tutarlı bir Türkçe/İngilizce dil tercihi sistemi.

---

*Bu dosya, projenin gelişim sürecine göre güncellenecektir.*
