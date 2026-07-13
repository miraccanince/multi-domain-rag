# AI-Powered Lead Management & Qualification Workflow
## Detaylı Teknik Spesifikasyon — Cleeng B2B SaaS

---

## 1. TRIGGER: New Lead Entry

### Desteklenen Kaynaklar

| Kaynak | Entegrasyon Yöntemi | Veri Formatı | Öncelik Sinyali |
|--------|---------------------|-------------|-----------------|
| **Webinar Registration** | Zoom/GoToWebinar Webhook | JSON payload | Katılım durumu, süre, sorular |
| **LinkedIn Ads** | LinkedIn Lead Gen Forms API | CSV/JSON | Form doldurma, reklam etkileşimi |
| **Demo Request** | Web form → Webhook | JSON payload | Aciliyet, şirket büyüklüğü |
| **Content Download** | HubSpot/Marketo webhook | JSON payload | İçerik tipi, indirme sıklığı |

### Webhook Payload Standardı

```json
{
  "source": "linkedin_ads",
  "timestamp": "2026-02-17T14:30:00Z",
  "raw_data": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@company.com",
    "company": "StreamCo",
    "job_title": "VP of Marketing",
    "phone": "+31612345678",
    "utm_source": "linkedin",
    "utm_campaign": "cleeng_d2c_q1"
  }
}
```

---

## 2. STEP 1: Data Normalization, Field Mapping & Deduplication

### 2.1 Field Standardization

```python
# Normalizasyon kuralları
FIELD_MAPPING = {
    # İsim normalizasyonu
    "first_name + last_name" → "full_name",    # Title case
    "firstName"              → "full_name",

    # Şirket normalizasyonu
    "company"     → "company_name",             # Strip: Inc, Ltd, BV, GmbH
    "company_url" → "company_domain",           # Extract root domain

    # İletişim normalizasyonu
    "phone"   → "phone_e164",                   # E.164 format
    "country" → "country_iso",                  # ISO 3166-1 alpha-2
    "email"   → "email_normalized",             # Lowercase, trim

    # Rol normalizasyonu
    "job_title" → "job_title_normalized",       # Seniority mapping
}

# Seniority Mapping
SENIORITY_MAP = {
    "C-Level":  ["CEO", "CTO", "CMO", "COO", "CFO", "CRO"],
    "VP":       ["VP", "Vice President", "SVP", "EVP"],
    "Director": ["Director", "Head of", "Managing Director"],
    "Manager":  ["Manager", "Team Lead", "Lead"],
    "IC":       ["Specialist", "Analyst", "Coordinator", "Associate"]
}
```

### 2.2 Deduplication Engine

```
Deduplication Pipeline:
│
├── Layer 1: Exact Match
│   └── email_normalized → %100 eşleşme → Merge
│
├── Layer 2: Domain Match
│   └── company_domain + full_name fuzzy → Levenshtein ≤ 2 → Merge candidate
│
├── Layer 3: Phone Match
│   └── phone_e164 exact → Merge candidate
│
└── Merge Strategy:
    ├── Mevcut lead varsa → Enrichment verisi güncelle, source ekle
    ├── Yeni lead → Yeni kayıt oluştur
    └── Conflict → En güncel veri + tüm source'ları sakla
```

### 2.3 Validation Layer

| Kontrol | Yöntem | Başarısızlık Aksiyonu |
|---------|--------|----------------------|
| Email geçerliliği | MX record + SMTP check | Reddet, log'a kaydet |
| Disposable email | Blocklist kontrolü (Mailinator vb.) | Reddet |
| Şirket domain | WHOIS lookup | Uyarı flag'i |
| Bot/spam tespiti | Honeypot + submission timing | Sil |
| Veri bütünlüğü | Required fields kontrolü | Manual review queue'ya gönder |

---

## 3. STEP 2: AI Research & Enrichment Agent (RAG-based)

### 3.1 Mimari Tasarım

```
┌─────────────────────────────────────────────────────┐
│              AI RESEARCH & ENRICHMENT AGENT          │
│                                                      │
│  ┌──────────────┐   ┌──────────────┐                │
│  │  RAG Engine   │   │  Web Scraper  │               │
│  │  (FlexiRAG    │   │  Agent        │               │
│  │   tabanlı)    │   │               │               │
│  └──────┬───────┘   └──────┬───────┘               │
│         │                   │                        │
│         ▼                   ▼                        │
│  ┌──────────────────────────────────┐               │
│  │      Data Fusion Layer           │               │
│  │  • Company profile builder       │               │
│  │  • Intent signal aggregator      │               │
│  │  • Confidence scorer             │               │
│  └──────────────┬──────────────────┘               │
│                  │                                   │
│                  ▼                                   │
│  ┌──────────────────────────────────┐               │
│  │      Structured JSON Output      │               │
│  └──────────────────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

### 3.2 Veri Kaynakları & Enrichment

| Veri Kategorisi | Kaynak | Çıkarılan Bilgi |
|----------------|--------|-----------------|
| **Şirket Profili** | LinkedIn Company API, Crunchbase | Sektör, çalışan sayısı, kuruluş yılı |
| **Finansal** | Crunchbase, PitchBook | Fonlama turu, yatırımcılar, gelir aralığı |
| **Teknoloji Stack** | BuiltWith, Wappalyzer | Kullanılan platformlar, CMS, ödeme altyapısı |
| **Intent Sinyalleri** | Bombora, G2 | Araştırma konuları, rakip karşılaştırmaları |
| **Sosyal Varlık** | LinkedIn, Twitter | Çalışan büyüme trendi, içerik aktivitesi |
| **İş İlanları** | LinkedIn Jobs, Indeed | Açık pozisyonlar → büyüme/tech sinyali |

### 3.3 RAG Agent Workflow

```python
# RAG-based Enrichment Pipeline (FlexiRAG mimarisi üzerine)

async def enrich_lead(lead: Lead) -> EnrichedLead:
    # 1. Company knowledge base'den RAG sorgusu
    company_context = await rag_query(
        query=f"Company profile: {lead.company_domain}",
        domain="company_intelligence",
        search_method="hybrid"  # Semantic + BM25
    )

    # 2. External API enrichment
    api_data = await gather(
        linkedin_api.get_company(lead.company_domain),
        crunchbase_api.get_company(lead.company_name),
        builtwith_api.get_tech_stack(lead.company_domain)
    )

    # 3. Intent signal extraction (LLM-powered)
    intent_analysis = await llm_analyze(
        prompt=INTENT_EXTRACTION_PROMPT,
        context={
            "company_profile": company_context,
            "job_postings": api_data.job_posts,
            "content_engagement": lead.engagement_history,
            "tech_stack": api_data.tech_stack
        }
    )

    # 4. Structured output
    return EnrichedLead(
        company_profile=merge(company_context, api_data),
        intent_signals=intent_analysis.signals,
        tech_stack=api_data.tech_stack,
        enrichment_confidence=calculate_confidence(api_data),
        enrichment_timestamp=datetime.utcnow()
    )
```

### 3.4 Structured JSON Output

```json
{
  "lead_id": "lead_abc123",
  "enrichment": {
    "company_profile": {
      "name": "StreamCo",
      "industry": "Media & Entertainment",
      "sub_industry": "OTT Streaming",
      "employee_count": 250,
      "employee_growth_6m": "+15%",
      "revenue_range": "$10M-$50M",
      "funding_stage": "Series B",
      "total_funding": "$35M",
      "headquarters": "Amsterdam, NL",
      "founded_year": 2019
    },
    "tech_stack": {
      "cms": "WordPress",
      "payment": "Stripe",
      "analytics": "Mixpanel",
      "current_subscription_platform": "Custom-built",
      "crm": "HubSpot"
    },
    "intent_signals": [
      {
        "signal": "subscription_management_research",
        "strength": "high",
        "evidence": "3 blog posts on churn reduction visited in last 7 days"
      },
      {
        "signal": "competitor_evaluation",
        "strength": "medium",
        "evidence": "G2 comparison: Cleeng vs Recurly vs Chargebee viewed"
      },
      {
        "signal": "hiring_signal",
        "strength": "medium",
        "evidence": "Open role: 'Subscription Operations Manager'"
      }
    ],
    "icp_match_indicators": {
      "is_d2c": true,
      "has_subscription_model": true,
      "pain_points_detected": ["churn", "billing_complexity", "subscriber_analytics"],
      "cleeng_fit_assessment": "Strong fit — D2C streaming with custom-built subscription infra"
    },
    "enrichment_confidence": 0.92,
    "enrichment_sources": ["linkedin", "crunchbase", "builtwith", "g2"],
    "enrichment_timestamp": "2026-02-17T14:35:22Z"
  }
}
```

---

## 4. STEP 3: AI Lead Scoring Engine (0-100)

### 4.1 Scoring Model Architecture

```
┌────────────────────────────────────────────────────────────┐
│                  AI LEAD SCORING ENGINE                      │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐        │
│  │ ICP Fit      │  │ Intent      │  │ Behavioral   │        │
│  │ Score        │  │ Score       │  │ Score        │        │
│  │ (0-40)       │  │ (0-35)      │  │ (0-25)       │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘        │
│         │                │                 │                 │
│         ▼                ▼                 ▼                 │
│  ┌──────────────────────────────────────────────────┐       │
│  │            Weighted Score Fusion                   │      │
│  │      Total = ICP + Intent + Behavioral            │      │
│  │      Confidence = min(data_completeness,           │      │
│  │                       model_certainty)              │      │
│  └──────────────────────┬───────────────────────────┘       │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────┐       │
│  │   Output: { score: 85, confidence: 0.91,          │      │
│  │            breakdown: {...}, reasoning: "..." }    │      │
│  └──────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────┘
```

### 4.2 Scoring Kriterleri (Detaylı)

#### A. ICP (Ideal Customer Profile) Fit Score — 0-40 Puan

| Kriter | Puan Aralığı | Puanlama Mantığı |
|--------|-------------|-----------------|
| **Sektör Uyumu** | 0-10 | Media/OTT: 10, E-commerce D2C: 8, SaaS: 5, Diğer: 2 |
| **Şirket Büyüklüğü** | 0-10 | 50-500 çalışan: 10, 500-2000: 8, 10-50: 5, <10 veya >2000: 2 |
| **Bölge** | 0-10 | EU/NA: 10, UK: 8, APAC: 5, Diğer: 3 |
| **Teknoloji Uyumu** | 0-10 | Mevcut subscription platform: 10, Custom-built: 8, Yok: 3 |

#### B. Intent Score — 0-35 Puan

| Kriter | Puan Aralığı | Puanlama Mantığı |
|--------|-------------|-----------------|
| **Web Aktivitesi** | 0-10 | Pricing page visit: +5, Case study: +3, Blog: +2 |
| **İçerik Etkileşimi** | 0-10 | Whitepaper download: +5, Webinar attendance: +5 |
| **Demo/Trial Sinyali** | 0-10 | Demo request: +10, Free trial sign-up: +8 |
| **Rakipten Geçiş** | 0-5 | Competitor comparison page: +3, G2 review: +2 |

#### C. Behavioral Score — 0-25 Puan

| Kriter | Puan Aralığı | Puanlama Mantığı |
|--------|-------------|-----------------|
| **Email Etkileşimi** | 0-10 | Açılma: +2/email, Tıklama: +4/email, Reply: +8 |
| **Webinar Katılım** | 0-5 | Kayıt: +2, Katılım: +3, Soru sorma: +5 |
| **Fiyat Sayfası** | 0-5 | 1 ziyaret: +2, 2+ ziyaret: +5 |
| **Chatbot/Form** | 0-5 | Chatbot etkileşim: +2, Contact form: +5 |

### 4.3 Confidence Calculation

```python
def calculate_confidence(enrichment_data, scoring_inputs):
    # Data completeness (0-1)
    required_fields = ['industry', 'employee_count', 'tech_stack', 'intent_signals']
    completeness = sum(1 for f in required_fields if f in enrichment_data) / len(required_fields)

    # Signal freshness (0-1)
    freshness = calculate_signal_freshness(scoring_inputs.timestamps)

    # Source reliability (0-1)
    reliability = calculate_source_reliability(enrichment_data.sources)

    # Weighted confidence
    confidence = (
        completeness * 0.4 +
        freshness * 0.3 +
        reliability * 0.3
    )

    return round(confidence, 2)
```

### 4.4 Validation Loop

```
Score + Confidence Hesaplandı
         │
         ▼
    Confidence ≥ 0.75?
    ┌────┴────┐
    │ HAYIR   │ EVET
    ▼         ▼
[Human       Score ≥ 80?
 Review]     ┌────┴────┐
    │        │ HAYIR   │ EVET
    │        ▼         ▼
    │    [Nurture]  [Hot Lead → Outreach]
    │
    ▼
Analyst İnceleme:
• Enrichment verisi doğrulama
• Manuel araştırma
• Skor override (sebep zorunlu)
• → Akışa geri gönder
```

---

## 5. HOT LEAD PATH: AI Personalized Outreach Generation

### 5.1 Outreach Generation Pipeline

```
Enriched Lead Data + Score
         │
         ▼
┌─────────────────────────────────┐
│  CONTEXT ASSEMBLY               │
│  • Company profile              │
│  • Pain points detected         │
│  • Intent signals               │
│  • Similar customer case study  │
│  • Contact's role & seniority   │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  LLM PROMPT ENGINEERING         │
│  • Persona: Cleeng SDR          │
│  • Tone: Professional, concise  │
│  • Template: Problem → Solution │
│  • Constraints: <150 words      │
└──────────────┬──────────────────┘
               │
         ┌─────┴─────┐
         ▼           ▼
   [Email Draft]  [LinkedIn Msg]
         │           │
         ▼           ▼
   [A/B Variant] [A/B Variant]
         │           │
         └─────┬─────┘
               ▼
      [Multi-Channel Sequence]
```

### 5.2 Email Template (AI-Generated)

```
Subject: {company_name}'s subscriber churn — a pattern we've seen before

Hi {first_name},

I noticed {company_name} recently posted a role for a Subscription
Operations Manager — which tells me managing subscriber lifecycle
is becoming a priority.

At Cleeng, we help D2C streaming platforms like {similar_customer}
reduce churn by up to 30% through AI-powered subscriber retention
management.

Given {company_name}'s growth trajectory ({employee_growth}),
you're likely hitting the inflection point where a custom-built
subscription system starts holding you back.

Would a 15-minute call this week make sense to explore this?

Best,
{rep_name}
```

### 5.3 LinkedIn Message Template

```
Hi {first_name},

Saw {company_name} is scaling its streaming subscription business —
exciting growth! We've helped similar platforms reduce involuntary
churn by 25%+. Would love to share how. Open to connecting?
```

### 5.4 Multi-Channel Cadence

| Gün | Kanal | Aksiyon | Koşul |
|-----|-------|---------|-------|
| 1 | Email | İlk iletişim (personalized) | Otomatik |
| 2 | LinkedIn | Bağlantı isteği + kısa not | Otomatik |
| 3 | Email | Follow-up (farklı açı) | Email açılmadıysa |
| 5 | LinkedIn | InMail mesajı | Bağlantı kabul edilmediyse |
| 7 | Email | Case study paylaşımı | Hâlâ yanıt yoksa |
| 10 | Telefon | Doğrudan arama | Son girişim |
| 14 | Email | Break-up email | Kapanış |

---

## 6. COLD/WARM LEAD PATH: Automated Nurture Workflow

### 6.1 Segment Classification

| Segment | Skor Aralığı | Strateji | Kadans |
|---------|-------------|----------|--------|
| **Warm** | 60-79 | Accelerated nurture — case study + webinar ağırlıklı | 3-5 gün arası |
| **Cool** | 40-59 | Standard nurture — eğitim içerik ağırlıklı | 7-10 gün arası |
| **Cold** | < 40 | Long-term drip — marka bilinirliği | 14-21 gün arası |

### 6.2 Nurture Email Sequence (Warm Segment Örneği)

```
Email 1 (Gün 0):  "D2C abonelik yönetiminde 2026 trendleri" — Blog post
Email 2 (Gün 4):  "{sector} sektöründe churn azaltma yöntemleri" — Whitepaper
Email 3 (Gün 8):  "Nasıl {similar_company} churn oranını %30 düşürdü" — Case study
Email 4 (Gün 14): "Subscriber Retention webinarımıza davetlisiniz" — Webinar invite
Email 5 (Gün 21): "Ücretsiz churn analizi yapmak ister misiniz?" — Soft CTA
```

### 6.3 Re-Engagement & Re-Scoring

```python
# Re-engagement monitor
async def monitor_nurture_engagement(lead_id: str):
    events = await get_engagement_events(lead_id)

    # Re-score tetikleme koşulları
    rescore_triggers = [
        events.email_clicked >= 3,           # 3+ email tıklama
        events.pricing_page_visited,          # Fiyat sayfası ziyareti
        events.webinar_registered,            # Webinar kaydı
        events.content_downloaded >= 2,       # 2+ içerik indirme
        events.demo_requested,               # Demo talebi → anında hot path
    ]

    if any(rescore_triggers):
        new_score = await rescore_lead(lead_id)
        if new_score.total >= 80 and new_score.confidence >= 0.75:
            await move_to_hot_path(lead_id)
            await notify_sales("Lead upgraded", lead_id, new_score)

    # 90 gün inaktif → arşivle
    if events.last_activity_days_ago > 90:
        await archive_lead(lead_id, reason="90_day_inactive")
```

---

## 7. FINAL ACTIONS & INTEGRATIONS

### 7.1 CRM Update (HubSpot/Salesforce)

```python
async def update_crm(lead: ProcessedLead):
    crm_payload = {
        "contact": {
            "email": lead.email,
            "properties": {
                "lead_score": lead.score.total,
                "lead_confidence": lead.score.confidence,
                "lead_stage": lead.stage,  # "hot", "warm", "cool", "cold"
                "icp_fit_score": lead.score.icp_fit,
                "intent_score": lead.score.intent,
                "behavioral_score": lead.score.behavioral,
                "assigned_rep": lead.assigned_rep,
                "enrichment_data": json.dumps(lead.enrichment),
                "ai_outreach_draft": lead.outreach_draft,
                "source_original": lead.source,
                "last_scored_at": datetime.utcnow().isoformat()
            }
        },
        "timeline_event": {
            "type": "ai_lead_scored",
            "description": f"AI Score: {lead.score.total}/100 (Confidence: {lead.score.confidence})",
            "details": lead.score.reasoning
        }
    }
    await hubspot_api.update_contact(crm_payload)
```

### 7.2 Smart Sales Rep Routing

```python
ROUTING_RULES = {
    "territory": {
        "EU":   ["rep_amsterdam_1", "rep_amsterdam_2"],
        "NA":   ["rep_newyork_1", "rep_newyork_2"],
        "APAC": ["rep_singapore_1"]
    },
    "industry_expertise": {
        "OTT/Streaming":  ["rep_amsterdam_1", "rep_newyork_1"],
        "Sports":         ["rep_amsterdam_2"],
        "News/Publishing": ["rep_newyork_2"]
    }
}

async def route_to_rep(lead: ProcessedLead) -> str:
    # 1. Bölge filtresi
    territory_reps = ROUTING_RULES["territory"][lead.region]

    # 2. Sektör uzmanlığı eşleştirme
    industry_reps = ROUTING_RULES["industry_expertise"].get(lead.industry, [])

    # 3. Kesişim → en iyi eşleşme
    matched = set(territory_reps) & set(industry_reps)

    # 4. Kapasite dengeleme
    if matched:
        return await get_least_loaded_rep(list(matched))

    # 5. Fallback: round-robin
    return await round_robin_assign(territory_reps)
```

### 7.3 Notification System

```python
# Slack notification
async def notify_sales(lead: ProcessedLead):
    if lead.stage == "hot":
        # Acil bildirim — #sales-hot-leads
        await slack.post_message(
            channel="#sales-hot-leads",
            blocks=[
                {"type": "header", "text": f"🔥 Hot Lead: {lead.full_name} @ {lead.company}"},
                {"type": "section", "fields": [
                    f"*Score:* {lead.score.total}/100",
                    f"*Confidence:* {lead.score.confidence}",
                    f"*Industry:* {lead.enrichment.industry}",
                    f"*Source:* {lead.source}",
                    f"*Assigned to:* @{lead.assigned_rep}",
                    f"*Key Signal:* {lead.enrichment.top_intent_signal}"
                ]},
                {"type": "actions", "elements": [
                    {"type": "button", "text": "View in CRM", "url": lead.crm_url},
                    {"type": "button", "text": "View AI Draft", "url": lead.outreach_draft_url}
                ]}
            ]
        )

    # Günlük özet — her gün 09:00
    # Weekly pipeline review — her Pazartesi 10:00
```

### 7.4 Analytics & Data Warehouse

| Metrik | Açıklama | Takip Sıklığı |
|--------|----------|---------------|
| **Lead Volume** | Kaynak başına gelen lead sayısı | Gerçek zamanlı |
| **Conversion Rate** | Lead → MQL → SQL → Closed Won | Haftalık |
| **Score Accuracy** | AI skor vs gerçek conversion korelasyonu | Aylık |
| **Outreach Performance** | Email açılma, tıklama, yanıt oranları | Haftalık |
| **Time to Contact** | Lead girişinden ilk iletişime kadar süre | Gerçek zamanlı |
| **Rep Efficiency** | Temsilci başına conversion oranı | Haftalık |
| **Enrichment Coverage** | Zenginleştirme başarı oranı | Günlük |
| **Model Drift** | Scoring model performans değişimi | Aylık |

---

## 8. FlexiRAG Bağlantıları — Mevcut Proje Deneyiminin Uygulanması

| Workflow Bileşeni | FlexiRAG Karşılığı | Uyarlama Notu |
|-------------------|---------------------|---------------|
| AI Research Agent (RAG-based) | Hybrid Search + QA Chain | Domain'i company intelligence olarak değiştir |
| Lead Scoring (multi-signal fusion) | RRF Scoring (Reciprocal Rank Fusion) | Document rank → Lead score |
| Deduplication Engine | Semantic Cache (benzerlik tespiti) | Query similarity → Lead similarity |
| Personalized Outreach | LLM Content Generation | QA cevabı → Kişiselleştirilmiş email |
| Data Normalization | CSV/PDF Loader + Field Mapping | Dosya → API payload |
| Analytics Dashboard | Feedback Analytics | Feedback metrikleri → Lead metrikleri |
| Authentication | JWT Auth System | Aynı mimari, genişletilmiş roller |
| Caching & Performance | Semantic + LRU Cache | Scoring sonuçlarını önbellekle |

---

## 9. Teknoloji Stack Önerisi

| Katman | Teknoloji | Alternatif |
|--------|-----------|-----------|
| **Backend API** | FastAPI (Python) | — |
| **AI/LLM** | OpenAI GPT-4 / Ollama (local) | Claude API |
| **Vector DB** | ChromaDB / Pinecone | Weaviate |
| **Embeddings** | Sentence-Transformers | OpenAI Embeddings |
| **CRM** | HubSpot API | Salesforce API |
| **Email** | SendGrid / AWS SES | Mailgun |
| **Notifications** | Slack API | Microsoft Teams |
| **Scheduler** | Celery + Redis | APScheduler |
| **Data Warehouse** | BigQuery / Snowflake | PostgreSQL |
| **Monitoring** | Prometheus + Grafana | DataDog |
| **Deployment** | Docker + Kubernetes | AWS ECS |
| **CI/CD** | GitHub Actions | GitLab CI |

---

*Bu dokümantasyon, Cleeng AI-Powered Demand Generation Lead Management ödevi için hazırlanmıştır.*
*FlexiRAG projesi üzerine inşa edilen mimari yaklaşımı göstermektedir.*
