import pytest
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"

@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture"""
    return {
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "rca_system_test",
            "user": "postgres",
            "password": "test_password"
        },
        "vector_db": {
            "collection_name": "test_rca_patterns",
            "persist_directory": "./test_chroma_db"
        },
        "llm": {
            "provider": "mock",  # Use mock for testing
            "model": "test-model",
            "temperature": 0.1,
            "max_tokens": 1000
        },
        "rca": {
            "confidence_threshold": 80,
            "max_context_length": 2000,
            "enable_agentic_fallback": False
        }
    }

@pytest.fixture(autouse=True)
def setup_test_environment(test_config):
    """Setup test environment before each test"""
    # Clean up test directories
    import shutil
    test_dirs = ["./test_chroma_db", "./test_logs"]
    
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
    
    yield
    
    # Cleanup after tests
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for testing"""
    return {
        "choices": [{
            "message": {
                "content": """{
                    "root_cause": "Test root cause analysis",
                    "confidence_score": 0.85,
                    "suggested_fix": "Test suggested fix",
                    "llm_reasoning": "Test reasoning"
                }"""
            }
        }]
    }

# Test database setup (optional - only if test database is available)
@pytest.fixture(scope="session")
def test_database_available():
    """Check if test database is available"""
    try:
        from database.connection import db_manager
        session = db_manager.get_session()
        session.execute("SELECT 1")
        session.close()
        return True
    except Exception:
        return False

# Skip database tests if not available
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "database: mark test as requiring database connection"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
