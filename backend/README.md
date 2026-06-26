# BPMN Agent - Backend

FastAPI-based backend for the BPMN Semantic Agent system.

## Architecture

Based on the 12-module architecture:

- **Module 1**: API Gateway (`routers/gateway.py`)
- **Module 2**: Agent Orchestrator (`core/orchestrator.py`)
- **Module 3**: Planner (`core/planner.py`)
- **Module 4**: Clarifier (`core/clarifier.py`)
- **Module 5**: BPMN Generator (`core/generator.py`)
- **Module 6**: Validator (`core/validator.py`)
- **Module 7**: LLM Provider (`services/llm_service.py`)
- **Module 8**: Short-term Memory / MariaDB (`services/memory_service.py`)
- **Module 9**: Semantic Memory / Neo4j (`services/semantic_service.py`)
- **Module 10**: SVG Render Service (external client in `services/external_services.py`)
- **Module 11**: Selection Box Service (external client in `services/external_services.py`)
- **Module 12**: Embedding Service (`services/embedding_service.py`)

## Setup

### Prerequisites

- Python 3.10+
- MariaDB 10.5+
- Neo4j 5.0+
- AvalAI API credentials or OpenAI API key

### Installation

```bash
cd backend
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```
LLM_API_KEY=your_key_here
MARIADB_PASSWORD=your_password_here
NEO4J_PASSWORD=your_password_here
```

### Running

```bash
python main.py
```

API will be available at `http://localhost:8000`

API docs: `http://localhost:8000/docs`

## API Endpoints

### Create Process
```
POST /api/v1/process-models
```

### Revise Process
```
POST /api/v1/process-models/{id}/revisions
```

### Get Process
```
GET /api/v1/process-models/{id}
```

### Get History
```
GET /api/v1/process-models/{id}/history
```

## Development

### Project Structure

```
backend/
├── main.py              # FastAPI app entry
├── config.py            # Configuration management
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── core/                # Core agent modules
│   ├── orchestrator.py  # Module 2
│   ├── planner.py       # Module 3
│   ├── clarifier.py     # Module 4
│   ├── generator.py     # Module 5
│   └── validator.py     # Module 6
├── routers/             # API endpoints
│   └── gateway.py       # Module 1
├── schemas/             # Pydantic models
│   └── process.py       # Process schemas
└── services/            # External & internal services
    ├── llm_service.py         # Module 7
    ├── memory_service.py      # Module 8
    ├── semantic_service.py    # Module 9
    ├── embedding_service.py   # Module 12
    └── external_services.py   # Modules 10, 11
```

## Next Steps

1. Implement LLM integration in Planner, Clarifier, Generator, and Validator
2. Complete BPMN schema validation in Validator
3. Implement semantic search and entity extraction in SemanticService
4. Add comprehensive error handling and logging
5. Add authentication and authorization
6. Add request/response logging
7. Add health checks for dependencies
8. Deploy with Docker
