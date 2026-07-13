# FlexiRAG Projesi — Tam Süreç Özeti

---

## PROJE BAĞLAMI

**Kullanıcı:** Mirac Can Ince — QA Engineer'dan ML Engineer'a geçiş yapıyor, Hollanda'da iş arıyor.

**Ana proje:** FlexiRAG — Üretim ortamına hazır, çok-domainli RAG (Retrieval-Augmented Generation) framework'ü.
GitHub: `https://github.com/miraccanince/FlexiRAG`

**Ayrıca:** Bir take-home assignment var — Cleeng B2B SaaS şirketi için AI destekli lead yönetim ve qualification workflow tasarımı. Bu ayrı bir klasörde (`docs 14-44-09-180/` ve `xml/`).

---

## FLEXIRAG — 4 HAFTALIK GELİŞTİRME SÜRECİ

### Hafta 1 — Temel RAG Pipeline
- PDF yükleme ve chunking (PyPDF)
- Yerel embedding: `sentence-transformers/all-MiniLM-L6-v2` (384 boyut)
- Vektör DB: ChromaDB (kalıcı depolama)
- Yerel LLM: Ollama + Llama 3.2 3B (Q4_K_M quantization, 2GB)
- Temel Q&A arayüzü
- Sıfır dış API bağımlılığı — her şey yerelde

### Hafta 2 — Multi-Domain Framework
- Klasör yapısından otomatik domain tespiti (`data/automotive/`, `data/fashion/` vb.)
- CSV loader: herhangi bir CSV formatını otomatik işliyor (sütun tespiti)
- Domain filtering: sorgularda belirli domaine yönlendirme
- Incremental indexing: yeni doküman eklerken var olanları silmiyor
- UUID tabanlı doküman ID'leri (çakışma sorunu çözüldü)

### Hafta 3 — İleri RAG Teknikleri
- **Hybrid Search:** ChromaDB semantic search + BM25 keyword search + Reciprocal Rank Fusion
- **LLM Reranking:** Yerel Llama 3.2 3B ile sonuçları yeniden sıralama
- **LRU Cache:** Tekrar eden sorgularda 360x hızlanma (<10ms vs 3.6s)
- **PCA Visualization:** Embedding uzayı görselleştirmesi
- FastAPI backend (streaming NDJSON)
- Streamlit frontend

### Hafta 4 — Production Özellikleri
- **JWT Authentication:** bcrypt password hashing, OAuth2 uyumlu token sistemi
- **Semantic Cache:** Embedding tabanlı cache (cosine similarity threshold: 0.85) — paraphrase'leri yakalıyor, %95.6 doğruluk
- **Rate Limiting:** IP bazlı (10-30 req/min), slowapi ile
- **User Feedback:** thumbs up/down, analytics, CSV/JSON export
- **CI/CD:** GitHub Actions — her commit'te 87 unit test
- **Docker:** multi-container deployment
- **bcrypt uyumluluğu:** 72-byte sınırı sorunu CI/CD için çözüldü

---

## MEVCUT METRİKLER

| Metrik | Değer |
|--------|-------|
| İndekslenmiş doküman | 31,396 (automotive: 635, fashion: 30,758) |
| Ortalama sorgu süresi | 3.6s |
| Cache hit süresi | <10ms (360x hızlanma) |
| Semantic cache doğruluğu | %95.6 similarity match |
| Test sayısı | 87 unit test, %100 pass |
| Code coverage | %90+ (auth, semantic cache, vector store, feedback) |
| Domain sayısı | 7 (automotive, fashion, legal, medical, tech + 2 varyant) |

---

## TEKNOLOJİ STACK

- **Backend:** Python, FastAPI, LangChain, ChromaDB, Sentence-Transformers, BM25
- **LLM:** Ollama + Llama 3.2 3B (tamamen yerel)
- **Frontend:** Streamlit, Plotly
- **Auth:** JWT + bcrypt
- **Test:** Pytest, pytest-cov, GitHub Actions CI/CD
- **Deploy:** Docker, docker-compose, Uvicorn

---

## REFERANS ALINAN TEKNİKLER / KAYNAKLAR

Projede uygulanan teknikler ve dayandıkları çalışmalar:

1. **BM25 (Okapi BM25)** — Robertson & Walker (1994) — keyword retrieval için klasik probabilistic model
2. **Reciprocal Rank Fusion** — Cormack et al. (2009) — hybrid search için birleştirme yöntemi
3. **Sentence-BERT / all-MiniLM-L6-v2** — Reimers & Gurevych (2019) — semantic embedding
4. **Hybrid Search (dense + sparse)** — modern RAG literature'ından alınan yaklaşım
5. **LLM Reranking (pointwise/listwise)** — RAG reranking literature'ından
6. **Semantic Caching** — cosine similarity ile cache hit tespiti — GPTCache benzeri yaklaşım

---

## TAKE-HOME ASSIGNMENT (CLEENG)

Ayrı bir proje olarak Cleeng B2B SaaS için AI destekli lead management workflow tasarlandı:

- **Trigger:** Webhook tabanlı (Webinar, LinkedIn Ads, Demo Request, Content Download)
- **Step 1:** Data Normalization & Deduplication (field standardization, fuzzy match, email validation)
- **Step 2:** AI Research & Enrichment Agent (company intel, intent signals, structured JSON output)
- **Step 3:** AI Lead Scoring Engine (0-100) — ICP Fit (0-40) + Intent (0-35) + Behavioral (0-25)
- **Step 4:** Human-in-the-loop routing (confidence < 0.75 → manual review)
- **Step 5:** CRM entegrasyonu ve otomatik aksiyon

Çıktılar: `workflow_technical_spec.md`, `workflow_flowchart.md`, `workflow_mermaid.md`, `workFlow.xml` (draw.io), `page1_workflow.pdf`

---

## SON İSTEK — SUNUM SLAYT TASARIMI

Konuşmanın son mesajında kullanıcı bir **1 sayfalık teknik sunum slaytı** istedi (istek yarıda kesildi):

**Hedef kitle:** Biotech/research ortamı, Research Data Engineering team

**Amaç:** Teknik internship mülakatı için 3-5 dakikalık engineering walkthrough

**İstenen çerçeve:**
- "LLM hype projesi değil" olarak konumlandırılmalı
- Modüler altyapı, retrieval workflow engineering, maintainable backend, deployment ve testing odaklı

**İstenen yapı:**
1. Problem
2. Research / Design Thinking
3. System Architecture
4. Key Engineering Decisions
5. Outcome / What I Learned

**Stil gereksinimleri:**
- Minimal metin
- Mimari/workflow diyagramları
- Startup pitch tarzı yok, "AI magic" dili yok, abartılı iddialar yok
- Engineering tradeoff ve pratik kısıtlamalar odaklı
- Production-minded ve teknik olarak sağlam hissettirmeli

**Optimize edilecek kullanım durumları:**
- Teknik internship mülakatları
- Ekran paylaşımı sırasında tartışmayı yönlendirme
- Teknik kararları doğal şekilde açıklamaya yardım etme

---

*Bu dosya, projenin tamamını başka bir AI'a aktarmak için hazırlanmıştır.*
