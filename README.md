# 🔍 RCA System - Root Cause Analysis Platform

A comprehensive, AI-powered Root Cause Analysis system that automatically ingests, enriches, fuses, and analyzes telemetry data to identify incident root causes using LLM + RAG with agentic AI fallback.

## 🏗️ Architecture Overview

```
Raw Events → Ingestion → Enrichment → Fusion → RCA Engine → Dashboard
    ↓           ↓           ↓          ↓         ↓
PostgreSQL  PostgreSQL  PostgreSQL  PostgreSQL + ChromaDB (RAG)
                                         ↓
                                    Agentic AI (Low Confidence)
                                         ↓
                                    External Tools
```

### Key Components

- **Ingestion Layer**: Stores raw alerts, events, logs, traces, metrics in PostgreSQL
- **Enrichment Layer**: Adds correlation IDs, anomaly detection, and contextual metadata
- **Fusion Layer**: Creates multimodal incident contexts (temporal + semantic + causal)
- **RCA Engine**: LLM-powered analysis with RAG from historical patterns (ChromaDB)
- **Agentic AI**: Advanced analysis using external tools for low-confidence incidents
- **Streamlit Dashboard**: Interactive web interface for monitoring and analysis

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- OpenAI API key

### Automated Setup

```bash
# Clone the repository
git clone <repository-url>
cd rca-system

# Run automated setup
python setup.py

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Edit environment file
cp .env.template .env
# Add your OpenAI API key to .env

# Verify setup
python cli.py setup check
```

### Manual Setup

1. **Create virtual environment**:
   ```bash
   sudo apt update
   sudo apt install python3-pip
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Setup PostgreSQL**:
   ```bash
   # Create database
   createdb rca_system
   
   # Initialize tables
   python cli.py setup init
   ```

3. **Configure environment**:
   ```bash
   cp .env.template .env
   # Edit .env and add your OpenAI API key
   ```

4. **Generate sample data** (optional):
   ```bash
   python cli.py setup sample-data
   ```

## 🔧 Usage

### Running the System

**Continuous Pipeline Mode** (recommended for production):
```bash
python main.py --mode pipeline
```

**API Server Mode**:
```bash
python main.py --mode api --host 0.0.0.0 --port 8000
```

**Dashboard Mode**:
```bash
python main.py --mode dashboard --host 0.0.0.0 --port 8501
```

### CLI Management

**System Status**:
```bash
python cli.py status system    # Overall system status
python cli.py status recent    # Recent activity
```

**Data Management**:
```bash
python cli.py data events --limit 50        # List recent events
python cli.py data incidents --limit 20     # List recent incidents
python cli.py data incident <incident-id>   # Detailed incident info
python cli.py data cleanup                  # Clean old data
```

**Pipeline Control**:
```bash
python cli.py pipeline run         # Single pipeline cycle
python cli.py pipeline enrichment  # Run enrichment only
python cli.py pipeline fusion      # Run fusion only
python cli.py pipeline rca         # Run RCA analysis only
python cli.py pipeline agentic     # Run agentic analysis only
```

**Configuration**:
```bash
python cli.py config show                          # Show current config
python cli.py config set rca.confidence_threshold 90  # Update config
```

## 📊 API Endpoints

### Events
- `POST /api/v1/events` - Ingest single event
- `POST /api/v1/events/batch` - Ingest multiple events
- `GET /api/v1/events` - List recent events

### Incidents
- `GET /api/v1/incidents` - List recent incidents
- `GET /api/v1/incidents/{id}` - Get incident details

### RCA Results
- `GET /api/v1/rca` - List RCA results
- `GET /api/v1/rca/{incident_id}` - Get specific RCA result
- `POST /api/v1/rca/{incident_id}/reanalyze` - Trigger re-analysis

### System
- `GET /health` - Health check
- `GET /api/v1/status` - System status and metrics
- `POST /api/v1/pipeline/process` - Trigger pipeline processing

### Example Event Ingestion

```bash
# Using curl
curl -X POST "http://localhost:8000/api/v1/events" \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "event",
       "source": "prometheus",
       "severity": "critical",
       "message": "High CPU usage detected",
       "metadata": {"cpu_usage": 95.5, "instance": "web-01"},
       "raw_data": {"alert": "HighCPUUsage"}
     }'
```

```python
# Using Python requests
import requests

event = {
    "event_type": "log",
    "source": "application",
    "severity": "high", 
    "message": "Database connection timeout",
    "metadata": {"service": "user-service", "database": "postgres"}
}

response = requests.post("http://localhost:8000/api/v1/events", json=event)
```

## 🎛️ Configuration

### Main Configuration (`config/config.yaml`)

```yaml
# Database settings
database:
  host: "localhost"
  port: 5432
  name: "rca_system"
  user: "postgres"
  password: "your_password"

# RCA Engine settings
rca:
  confidence_threshold: 95      # Threshold for agentic fallback
  max_context_length: 4000     # Max context for LLM
  enable_agentic_fallback: true

# LLM settings
llm:
  provider: "openai"
  model: "gpt-4"
  temperature: 0.1
  max_tokens: 2000

# Processing weights
fusion:
  temporal_weight: 0.4
  semantic_weight: 0.3
  causal_weight: 0.3
```

### Environment Variables (`.env`)

Key environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `DATABASE_URL` - PostgreSQL connection string (optional)
- `LOG_LEVEL` - Logging level (INFO, DEBUG, ERROR)
- `ENVIRONMENT` - Environment type (development, production)

## 📈 Dashboard Features

Access the Streamlit dashboard at `http://localhost:8501`:

### Dashboard Views

1. **System Overview**
   - Real-time metrics and KPIs
   - Event volume charts
   - Incident timeline
   - Resolution rate tracking

2. **Incident Analysis**
   - Detailed incident explorer
   - RCA results with confidence scores
   - Historical pattern matching
   - Filterable incident list

3. **System Status**
   - Component health monitoring
   - Database connection status
   - Vector store statistics
   - Agentic AI performance

4. **Data Pipeline**
   - Pipeline execution controls
   - Processing step triggers
   - Sample data generation
   - Performance monitoring

## 🧠 How It Works

### 1. Ingestion Layer
- Accepts events via API or batch processing
- Stores raw telemetry data in PostgreSQL
- Supports multiple event types: logs, metrics, traces, alerts

### 2. Enrichment Layer
- **Correlation Analysis**: Groups related events within time windows
- **Anomaly Detection**: Identifies unusual patterns and frequencies
- **Context Enhancement**: Adds temporal, service, and severity context

### 3. Fusion Layer
- **Temporal Context**: Event timing, burst patterns, frequency analysis
- **Semantic Context**: Event types, sources, severity levels, keywords
- **Causal Context**: Event relationships, progression patterns, root cause hints

### 4. RCA Engine
- **LLM Analysis**: GPT-4 powered root cause analysis
- **RAG Enhancement**: Historical pattern matching via ChromaDB
- **Confidence Scoring**: Reliability assessment of analysis

### 5. Agentic AI (Low Confidence Fallback)
- **External Tool Integration**: Monitoring APIs, GitHub, status pages
- **Deep Analysis**: Multi-source evidence gathering
- **Confidence Boosting**: Enhanced analysis with additional context

## 🔍 Example Workflow

1. **Event Ingestion**:
   ```
   Alert: "High CPU usage on web-server-01" → PostgreSQL
   ```

2. **Enrichment**:
   ```
   + Correlation ID: cpu-spike-incident-123
   + Anomaly Score: 0.85 (unusual for this time)
   + Context: Related to recent deployment
   ```

3. **Fusion**:
   ```
   Temporal: Burst pattern, 15 events/min
   Semantic: Performance category, critical severity
   Causal: Deployment → CPU spike progression
   ```

4. **RCA Analysis**:
   ```
   LLM + RAG → "Root cause: Memory leak in v2.1.3 deployment"
   Confidence: 0.92 (high confidence, no agentic needed)
   Fix: "Rollback to v2.1.2, apply memory patch"
   ```

5. **Dashboard Display**:
   ```
   ✅ Incident resolved with high confidence
   📊 Added to historical patterns for future reference
   ```

## 🧪 Testing

### Unit Tests
```bash
python -m pytest tests/ -v
```

### Integration Tests
```bash
python -m pytest tests/integration/ -v
```

### Load Testing
```bash
# Generate test events
python cli.py setup sample-data

# Run pipeline
python cli.py pipeline run

# Check results
python cli.py status system
```

## 🚀 Deployment

### Production Checklist

1. **Environment Setup**:
   - Set `ENVIRONMENT=production` in .env
   - Use production PostgreSQL instance
   - Configure proper logging levels

2. **Security**:
   - Secure OpenAI API keys
   - Enable API rate limiting
   - Use HTTPS for API endpoints

3. **Monitoring**:
   - Set up health check monitoring
   - Configure log aggregation
   - Monitor pipeline processing times

4. **Scaling**:
   - Consider horizontal scaling for API
   - Optimize database queries
   - Monitor vector store performance

### Docker Alternative (No Docker Required)

For containerized deployment without Docker, consider:
- Python virtual environments with systemd services
- PostgreSQL + Python application servers
- Reverse proxy setup (nginx) for multiple instances

## 📚 Development

### Project Structure

```
rca-system/
├── api/                    # FastAPI endpoints
├── agentic/               # Agentic AI components
├── config/                # Configuration files
├── database/              # Database models and connections
├── enrichment/            # Event enrichment logic
├── fusion/                # Context fusion algorithms
├── ingestion/             # Data ingestion layer
├── rca/                   # RCA engine and vector store
├── ui/                    # Streamlit dashboard
├── utils/                 # Utility functions
├── tests/                 # Test suites
├── main.py               # Application entry point
├── cli.py                # CLI management tool
├── setup.py              # Setup script
└── requirements.txt      # Dependencies
```

### Adding New Features

1. **New Event Sources**: Extend `ingestion/data_models.py`
2. **Custom Enrichment**: Add logic to `enrichment/enrichment_layer.py`
3. **Additional LLM Providers**: Extend `rca/rca_engine.py`
4. **New Agentic Tools**: Add to `agentic/agentic_ai.py`

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Add tests for new functionality
4. Ensure all tests pass: `python -m pytest`
5. Submit pull request

## 📋 Troubleshooting

### Common Issues

**Database Connection Error**:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Verify database exists
psql -l | grep rca_system

# Recreate tables
python cli.py setup init
```

**OpenAI API Errors**:
```bash
# Verify API key
echo $OPENAI_API_KEY

# Test connection
python -c "import openai; print(openai.Model.list())"
```

**Vector Store Issues**:
```bash
# Clear ChromaDB
rm -rf chroma_db/
python cli.py setup sample-data
```

**Pipeline Not Processing**:
```bash
# Check for events
python cli.py data events --limit 10

# Manual pipeline run
python cli.py pipeline run

# Check logs
tail -f logs/app.log
```

### Performance Tuning

- **Database**: Add indexes on timestamp columns
- **Vector Store**: Tune embedding model and collection size
- **LLM**: Adjust context length and temperature
- **Pipeline**: Optimize batch sizes and processing intervals

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

- **Documentation**: Check this README and inline code comments
- **Issues**: Submit GitHub issues for bugs and feature requests
- **Development**: See CONTRIBUTING.md for development guidelines

## 🎯 Roadmap

- [ ] Support for additional LLM providers (LLaMA, Claude)
- [ ] Real-time streaming event processing
- [ ] Advanced visualization and reporting
- [ ] Machine learning-based pattern detection
- [ ] Integration with popular monitoring tools
- [ ] Multi-tenant support
- [ ] Advanced security and RBAC

---

**Built with ❤️ for Site Reliability Engineers and DevOps teams**
