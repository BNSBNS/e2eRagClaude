# e2eRagClaude


Technology Stack

Backend: FastAPI + SQLAlchemy + Celery seenode +6
Frontend: Next.js 15 + TypeScript nextjs + Zustand Next.jsMedium
Databases: PostgreSQL + Redis + Neo4j TestDriven.ioReadthedocs
AI/ML: LangChain + LangGraph + OpenAI FutureSmart AIFutureSmart AI
Cloud: AWS (ECS, RDS, S3, CloudFront) Porter
Monitoring: Prometheus + Grafana + LangSmith CloudZero +3


ai-document-platform/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # 🔥 MAIN FastAPI APPLICATION
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── ai.py
│   │   │   └── websocket.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── database.py            # 🔥 DATABASE CONNECTION
│   │   │   ├── redis_client.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── document.py            # 🔥 DOCUMENT MODEL
│   │   │   └── chat.py                # 🔥 CHAT MODEL
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── document_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── neo4j_service.py
│   │   │   └── langgraph_service.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── file_utils.py
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   ├── tests/
│   ├── .env                           # 🔥 BACKEND ENVIRONMENT VARS
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   └── api/
│   ├── components/
│   │   ├── ui/
│   │   ├── DocumentUpload.tsx
│   │   ├── AIChat.tsx
│   │   └── TutorInterface.tsx
│   ├── lib/
│   │   ├── auth.ts
│   │   ├── api.ts
│   │   └── websocket.ts
│   ├── types/
│   │   └── index.ts
│   ├── .env.local                     # 🔥 FRONTEND ENVIRONMENT VARS
│   ├── package.json
│   ├── Dockerfile
│   └── next.config.js
├── monitoring/
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   ├── ai-platform.json       # 🔥 GRAFANA DASHBOARD CONFIG
│   │   │   └── llm-monitoring.json
│   │   └── provisioning/
│   │       ├── dashboards.yml
│   │       └── datasources.yml
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alert_rules.yml
│   └── tempo/
│       └── tempo.yml
├── docker-compose.yml                 # 🔥 LOCAL DEVELOPMENT
├── docker-compose.prod.yml            # 🔥 PRODUCTION CONFIG
├── .env.example                       # 🔥 EXAMPLE ENVIRONMENT VARS
└── README.md