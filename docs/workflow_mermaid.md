flowchart TD
    S1(["Webinar Registration"]):::triggerStyle
    S2(["LinkedIn Ads"]):::triggerStyle
    S3(["Demo Request"]):::triggerStyle
    S4(["Content Download"]):::triggerStyle

    S1 & S2 & S3 & S4 --> NORM

    NORM["STEP 1: Data Normalization & Deduplication
    ---
    Standardize fields, unified schema
    Email MX record + domain validation
    Deduplicate: exact + fuzzy match"]:::blueStyle

    NORM --> ENRICH

    ENRICH["STEP 2: AI Research & Enrichment Agent
    ---
    Company intel: industry, size, funding, tech stack
    Intent signals: website visits, content engagement
    Output: Structured JSON + confidence score"]:::purpleStyle

    ENRICH --> SCORE

    SCORE["STEP 3: AI Lead Scoring Engine 0-100
    ---
    ICP Fit 0-40: industry, size, region, tech
    Intent 0-35: web activity, content, demo signals
    Behavioral 0-25: email, webinar, pricing page"]:::purpleStyle

    SCORE --> CONF_CHECK

    CONF_CHECK{Confidence >= 0.75?}:::diamondStyle

    CONF_CHECK -- Low confidence --> HUMAN_Q
    CONF_CHECK -- Confident --> DECISION

    HUMAN_Q["Human Review Queue
    ---
    Analyst verifies enrichment data
    Manual research + score override"]:::yellowStyle

    HUMAN_Q --> DECISION

    DECISION{Score >= 80?}:::diamondStyle

    DECISION -- Hot Lead --> OUTREACH
    DECISION -- Nurture --> NURTURE

    OUTREACH["AI Personalized Outreach Generation
    ---
    Email draft + LinkedIn message
    Company-specific value prop + social proof
    Multi-channel cadence Day 1-14"]:::purpleStyle

    OUTREACH --> REVIEW

    REVIEW["Sales Rep Review & Edit
    ---
    Review AI draft, personalize, approve"]:::yellowStyle

    REVIEW --> ROUTE

    ROUTE["Route to Sales Rep
    ---
    Territory + industry + capacity matching"]:::greenStyle

    ROUTE --> ACTIONS

    NURTURE["Automated Nurture Workflow
    ---
    Warm 60-79 / Cool 40-59 / Cold under 40
    Drip email sequences + educational content
    Monitor re-engagement signals"]:::blueStyle

    NURTURE -- Re-engagement detected --> SCORE
    NURTURE --> ACTIONS

    ACTIONS["Final Actions
    ---
    Update CRM - HubSpot/Salesforce
    Log scoring data for analytics
    Slack notification to sales-leads
    Schedule follow-up cadence"]:::greenStyle

    classDef triggerStyle fill:#DBEAFE,stroke:#2563EB,stroke-width:2px,color:#1E40AF
    classDef blueStyle fill:#EFF6FF,stroke:#2563EB,stroke-width:2px,color:#1E293B
    classDef purpleStyle fill:#F5F3FF,stroke:#7C3AED,stroke-width:2px,color:#1E293B
    classDef yellowStyle fill:#FFFBEB,stroke:#D97706,stroke-width:2px,color:#1E293B
    classDef greenStyle fill:#ECFDF5,stroke:#059669,stroke-width:2px,color:#1E293B
    classDef diamondStyle fill:#EDE9FE,stroke:#7C3AED,stroke-width:2.5px,color:#4C1D95
