#!/usr/bin/env python3
"""
RCA System Setup Script
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python version {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def check_postgresql():
    """Check if PostgreSQL is available"""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️  PostgreSQL not found in PATH")
    print("Please install PostgreSQL:")
    
    system = platform.system().lower()
    if system == "darwin":  # macOS
        print("  brew install postgresql")
    elif system == "linux":
        print("  sudo apt-get install postgresql postgresql-contrib  # Ubuntu/Debian")
        print("  sudo yum install postgresql postgresql-server     # CentOS/RHEL")
    elif system == "windows":
        print("  Download from: https://www.postgresql.org/download/windows/")
    
    return False

def create_virtual_environment():
    """Create virtual environment"""
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    print("📦 Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False

def get_pip_executable():
    """Get the pip executable path for the virtual environment"""
    system = platform.system().lower()
    if system == "windows":
        return Path("venv/Scripts/pip.exe")
    else:
        return Path("venv/bin/pip")

def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing Python dependencies...")
    
    pip_path = get_pip_executable()
    
    if not pip_path.exists():
        print("❌ Virtual environment pip not found")
        return False
    
    try:
        # Upgrade pip first
        subprocess.run([str(pip_path), "install", "--upgrade", "pip"], check=True)
        
        # Install dependencies
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
        
        # Install additional CLI dependencies
        subprocess.run([str(pip_path), "install", "click", "tabulate"], check=True)
        
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_env_file():
    """Create .env file template"""
    env_path = Path(".env")
    
    if env_path.exists():
        print("✅ .env file already exists")
        return True
    
    print("📝 Creating .env file template...")
    
    env_content = """# RCA System Environment Variables

# OpenAI API Key (required for LLM analysis)
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration (optional, overrides config.yaml)
# DATABASE_URL=postgresql://username:password@localhost:5432/rca_system

# Additional configuration
# LOG_LEVEL=INFO
# ENVIRONMENT=development
"""
    
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        print("✅ .env file created")
        print("⚠️  Please edit .env file and add your OpenAI API key")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def create_database():
    """Create PostgreSQL database"""
    print("🗄️  Setting up database...")
    
    db_name = "rca_system"
    
    try:
        # Check if database exists
        result = subprocess.run([
            'psql', '-lqt'
        ], capture_output=True, text=True, env={"PGUSER": "postgres"})
        
        if db_name in result.stdout:
            print(f"✅ Database '{db_name}' already exists")
            return True
        
        # Create database
        subprocess.run([
            'createdb', db_name
        ], check=True, env={"PGUSER": "postgres"})
        
        print(f"✅ Database '{db_name}' created")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Could not create database automatically: {e}")
        print("Please create the database manually:")
        print(f"  createdb {db_name}")
        print("Or using psql:")
        print(f"  CREATE DATABASE {db_name};")
        return False

def initialize_database():
    """Initialize database tables"""
    print("🗄️  Initializing database tables...")
    
    python_path = get_python_executable()
    
    try:
        subprocess.run([
            str(python_path), "-c",
            "from database.connection import db_manager; db_manager.create_tables()"
        ], check=True)
        
        print("✅ Database tables created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create database tables: {e}")
        return False

def get_python_executable():
    """Get the Python executable path for the virtual environment"""
    system = platform.system().lower()
    if system == "windows":
        return Path("venv/Scripts/python.exe")
    else:
        return Path("venv/bin/python")

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")
    
    directories = [
        "logs",
        "chroma_db",
        "exports"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directories created")

def run_initial_setup():
    """Run initial system setup"""
    print("🚀 Running initial setup...")
    
    python_path = get_python_executable()
    
    try:
        # Initialize system
        subprocess.run([str(python_path), "cli.py", "setup", "init"], check=True)
        
        # Generate sample data
        choice = input("Generate sample data for testing? (y/N): ")
        if choice.lower() in ['y', 'yes']:
            subprocess.run([str(python_path), "cli.py", "setup", "sample-data"], check=True)
        
        print("✅ Initial setup completed")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Initial setup failed: {e}")
        return False

def print_usage_instructions():
    """Print usage instructions"""
    system = platform.system().lower()
    
    if system == "windows":
        activate_cmd = "venv\\Scripts\\activate"
        python_cmd = "venv\\Scripts\\python"
    else:
        activate_cmd = "source venv/bin/activate"
        python_cmd = "venv/bin/python"
    
    print("\n" + "="*60)
    print("🎉 RCA System Setup Complete!")
    print("="*60)
    print("\n📋 Next Steps:")
    print(f"1. Activate virtual environment: {activate_cmd}")
    print("2. Edit .env file and add your OpenAI API key")
    print("3. Ensure PostgreSQL is running")
    print("\n🚀 Quick Start Commands:")
    print(f"  {python_cmd} cli.py status system          # Check system status")
    print(f"  {python_cmd} main.py --mode pipeline       # Run continuous pipeline")
    print(f"  {python_cmd} main.py --mode api            # Start API server")
    print(f"  {python_cmd} main.py --mode dashboard      # Start Streamlit dashboard")
    print("\n🔧 CLI Management:")
    print(f"  {python_cmd} cli.py --help                 # Show all commands")
    print(f"  {python_cmd} cli.py setup check            # Verify environment")
    print(f"  {python_cmd} cli.py pipeline run           # Run single pipeline cycle")
    print(f"  {python_cmd} cli.py data events            # List recent events")
    print(f"  {python_cmd} cli.py data incidents         # List recent incidents")
    print("\n📚 Documentation:")
    print("  README.md - Complete setup and usage guide")
    print("  config/config.yaml - System configuration")
    print("\n⚠️  Important:")
    print("  • Add your OpenAI API key to .env file")
    print("  • Ensure PostgreSQL service is running")
    print("  • Check logs/ directory for detailed logs")

def main():
    """Main setup function"""
    print("🔧 RCA System Setup")
    print("="*40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check PostgreSQL
    postgres_available = check_postgresql()
    
    # Create virtual environment
    if not create_virtual_environment():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Database setup (optional if PostgreSQL not available)
    if postgres_available:
        create_database()
        initialize_database()
    else:
        print("⚠️  Skipping database setup - PostgreSQL not available")
        print("Please install PostgreSQL and run: python cli.py setup init")
    
    # Run initial setup (optional if database not ready)
    if postgres_available:
        run_initial_setup()
    
    # Print usage instructions
    print_usage_instructions()

if __name__ == "__main__":
    main()
