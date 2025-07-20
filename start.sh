#!/bin/bash

# RCA System Startup Script
# This script provides quick commands to start different components

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        print_error "Virtual environment not found!"
        print_info "Run: python setup.py"
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
}

# Get Python executable
get_python() {
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "venv/Scripts/python.exe"
    else
        echo "venv/bin/python"
    fi
}

# Check system status
check_status() {
    print_info "Checking system status..."
    activate_venv
    PYTHON=$(get_python)
    $PYTHON cli.py setup check
}

# Setup system
setup() {
    print_info "Setting up RCA System..."
    
    if [ ! -f ".env" ]; then
        print_warning ".env file not found, copying template..."
        cp .env.template .env
        print_warning "Please edit .env file and add your OpenAI API key!"
    fi
    
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    $PYTHON cli.py setup init
    print_success "System initialized!"
    
    read -p "Generate sample data? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $PYTHON cli.py setup sample-data
        print_success "Sample data generated!"
    fi
}

# Start pipeline mode
start_pipeline() {
    print_info "Starting RCA System in pipeline mode..."
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    print_info "Pipeline will run continuously. Press Ctrl+C to stop."
    $PYTHON main.py --mode pipeline
}

# Start API server
start_api() {
    print_info "Starting RCA System API server..."
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    PORT=${1:-8000}
    print_info "API server will be available at: http://localhost:$PORT"
    print_info "API documentation: http://localhost:$PORT/docs"
    $PYTHON main.py --mode api --port $PORT
}

# Start dashboard
start_dashboard() {
    print_info "Starting RCA System dashboard..."
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    PORT=${1:-8501}
    print_info "Dashboard will be available at: http://localhost:$PORT"
    $PYTHON main.py --mode dashboard --port $PORT
}

# Show system status
status() {
    print_info "System Status:"
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    $PYTHON cli.py status system
}

# Run single pipeline cycle
run_pipeline() {
    print_info "Running single pipeline cycle..."
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    $PYTHON cli.py pipeline run
}

# Show recent activity
recent() {
    print_info "Recent Activity:"
    check_venv
    activate_venv
    PYTHON=$(get_python)
    
    $PYTHON cli.py status recent
}

# Show logs
logs() {
    print_info "Recent logs:"
    if [ -f "logs/app.log" ]; then
        tail -n 50 logs/app.log
    else
        print_warning "No log file found at logs/app.log"
    fi
}

# Show help
show_help() {
    echo "🔍 RCA System Startup Script"
    echo "================================"
    echo
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  setup              - Initialize the system"
    echo "  status             - Show system status"
    echo "  check              - Check system environment"
    echo "  pipeline           - Start continuous pipeline"
    echo "  api [port]         - Start API server (default: 8000)"
    echo "  dashboard [port]   - Start Streamlit dashboard (default: 8501)"
    echo "  run                - Run single pipeline cycle"
    echo "  recent             - Show recent activity"
    echo "  logs               - Show recent logs"
    echo "  help               - Show this help"
    echo
    echo "Examples:"
    echo "  $0 setup           # Initialize system"
    echo "  $0 pipeline        # Start continuous processing"
    echo "  $0 api 9000        # Start API on port 9000"
    echo "  $0 dashboard       # Start dashboard on default port"
    echo "  $0 status          # Check system status"
    echo
    echo "Quick Start:"
    echo "  1. $0 setup        # First time setup"
    echo "  2. Edit .env file and add OpenAI API key"
    echo "  3. $0 check        # Verify environment"
    echo "  4. $0 pipeline     # Start processing"
    echo
}

# Main command processing
case "${1:-help}" in
    "setup")
        setup
        ;;
    "check")
        check_status
        ;;
    "status")
        status
        ;;
    "pipeline")
        start_pipeline
        ;;
    "api")
        start_api $2
        ;;
    "dashboard")
        start_dashboard $2
        ;;
    "run")
        run_pipeline
        ;;
    "recent")
        recent
        ;;
    "logs")
        logs
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac
