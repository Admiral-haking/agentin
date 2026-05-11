# Agentin - Instagram DM Bot 🤖

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-blue)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A **webhook-driven DM assistant** for Instagram that stores conversation history, routes between multiple LLM providers (OpenAI, DeepSeek), and sends intelligent replies via your outbound API.

## 🎯 Key Features

- **Multi-LLM Routing** — Seamlessly switch between OpenAI GPT-4 and DeepSeek models
- **Persistent Memory** — PostgreSQL-backed conversation history with full context awareness
- **Admin Dashboard** — React-based panel for monitoring and configuration
- **Dockerized Deployment** — One-command setup with Docker Compose
- **Extensible Architecture** — Modular design for adding new providers and tools

## 🚀 Quick Start

```bash
# Clone & setup
git clone https://github.com/Admiral-haking/agentin.git
cd agentin

# Environment
cp .env.example .env  # Configure your API keys

# Run with Docker
docker compose up -d

# Or manually
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 🧪 MLOps & Quality Assurance

### Evaluation Suite
```bash
# Run automated evaluation (50+ test scenarios)
python scripts/evaluate.py

# Monitor metrics in real-time
python scripts/monitor.py --metrics latency,tokens,errors
```

### Quality Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Response Latency | < 2s | ✅ 1.2s avg |
| Hallucination Detection | Confidence-based filtering | ✅ Active |
| Token Usage Tracking | Per-request logging | ✅ Active |
| Error Rate | < 1% | 📊 Monitoring |

## 📁 Project Structure

```
├── app/              # FastAPI application
├── admin-ui/         # React admin dashboard
├── alembic/          # Database migrations
├── deploy/           # Deployment configuration
├── scripts/          # Utility & evaluation scripts
├── tests/            # Test suite
└── docker-compose.yml
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — We welcome contributions!

## 📄 License

MIT License — see [LICENSE](LICENSE)
