# doctask-nishanth 

doctask-nishanth/
├── README.md                      # setup, architecture, supported formats, assumptions, trade-offs
├── TASK.md                        # instructions and workflow followed while building
├── PROGRESS.md                    # development log, assumptions, and decisions
├── LICENSE
├── Makefile                       # one-command setup/run/test helpers
├── docker-compose.yml             # local development services
├── .env.example                   # environment variable template
├── .gitignore                     # ignore secrets, logs, virtual environments
│
├── backend/
│   ├── pyproject.toml             # Python dependencies and project configuration
│   ├── alembic/                   # database migrations
│   ├── tests/
│   │   ├── unit/                  # unit tests
│   │   ├── integration/           # integration tests
│   │   └── fixtures/              # mocked LLMs, sample documents, test data
│   │
│   └── app/
│       ├── main.py                # FastAPI application entry point
│       │
│       ├── api/
│       │   ├── routes_ingest.py   # upload/watch document endpoints
│       │   ├── routes_runs.py     # start, stop, resume workflow runs
│       │   └── routes_review.py   # approve/reject findings and updates
│       │
│       ├── mcp/
│       │   ├── server.py          # MCP server entry point
│       │   ├── tools.py           # MCP tool definitions
│       │   └── handlers.py        # executes MCP tool requests
│       │
│       ├── workflow/
│       │   ├── graph.py           # LangGraph workflow definition
│       │   ├── state.py           # shared workflow state
│       │   ├── checkpointer.py    # save and restore workflow checkpoints
│       │   └── nodes/
│       │       ├── classify.py    # identify document type
│       │       ├── extract.py     # extract structured facts with citations
│       │       ├── reconcile.py   # detect contradictions across documents
│       │       ├── rule_checker.py     # validate against user rules
│       │       └── update.py      # generate focused document updates
│       │
│       ├── services/
│       │   ├── llm.py             # wrapper around LLM providers
│       │   ├── embeddings.py      # embedding generation
│       │   └── citations.py       # source citation management
│       │
│       ├── prompts/
│       │   ├── classify.md        # classification prompt
│       │   ├── extract.md         # extraction prompt
│       │   ├── reconcile.md       # contradiction detection prompt
│       │   ├── examine.md         # rule checking prompt
│       │   └── update.md          # incremental update prompt
│       │
│       ├── persistence/
│       │   ├── models/            # SQLAlchemy database models
│       │   ├── repositories/      # database access layer
│       │   └── vector_store.py    # pgvector retrieval
│       │
│       ├── schemas/
│       │   ├── run.py             # run request/response models
│       │   ├── review.py          # review API schemas
│       │   ├── document.py        # document schemas
│       │   └── finding.py         # findings and reports schemas
│       │
│       ├── ingestion/
│       │   ├── watcher.py         # monitor incoming documents
│       │   └── loaders/           # PDF, DOCX, TXT loaders
│       │
│       ├── storage/
│       │   ├── uploads/           # uploaded source documents
│       │   ├── generated/         # generated reports and outputs
│       │   └── storage.py         # file storage operations
│       │
│       ├── guardrails/
│       │   └── injection_filter.py # detect prompt injection attempts
│       │
│       ├── costs/
│       │   └── tracker.py         # track tokens, latency, and API costs
│       │
│       ├── core/
│       │   ├── config.py          # application configuration
│       │   ├── logging.py         # centralized logging
│       │   └── security.py        # authentication and security helpers
│       │
│       └── utils/
│           ├── retry.py           # retry helpers
│           ├── hashing.py         # file hashing and deduplication
│           ├── timing.py          # execution timing utilities
│           └── helpers.py         # shared helper functions
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.tsx                # application root
│       ├── pages/                 # application pages
│       ├── components/
│       │   ├── RunTimeline.tsx    # visualize workflow stages
│       │   ├── ReviewQueue.tsx    # human approval interface
│       │   └── ChangeLog.tsx      # change history and audit trail
│       ├── hooks/                 # reusable React hooks
│       ├── services/              # API client layer
│       ├── store/                 # global state management
│       ├── types/                 # TypeScript type definitions
│       └── utils/                 # frontend helper utilities
│
├── use-cases/
│   ├── run-1/                     # first document set
│   └── run-2/                     # second document set for validation
│
└── docs/
    ├── architecture.drawio        # editable architecture diagram
    ├── architecture.png           # exported architecture diagram
    ├── api.md                     # API documentation
    ├── decisions.md               # architectural decisions and trade-offs
    └── writeup.md                 # Task 4 one-page write-up


                         ┌──────────────┐
                         │     Run      │
                         └──────┬───────┘
                                │ 1
                ┌───────────────┼────────────────┐
                │               │                │
               *│              *│               1│
          ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
          │ Document  │   │  Finding  │   │   Report    │
          └───────────┘   └───────────┘   └─────────────┘
                │
                │1
               *│
        ┌───────▼────────┐
        │ DocumentChunk   │
        └────────────────┘

Run
 │
 └───────────────*
                 │
          WorkflowEvent