#!/bin/bash
# Multi-Region Failover Demo - Management Script
# Usage: ./demo.sh [command]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Multi-Region Failover Demo                                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

start() {
    print_header
    print_info "Starting Multi-Region Failover Demo..."
    cd "$PROJECT_DIR"
    docker-compose up -d --build
    print_success "Services started!"
    echo ""
    print_info "Waiting for services to be ready..."
    sleep 10
    status
}

stop() {
    print_header
    print_info "Stopping Multi-Region Failover Demo..."
    cd "$PROJECT_DIR"
    docker-compose down
    print_success "Services stopped!"
}

restart() {
    stop
    echo ""
    start
}

status() {
    print_header
    echo -e "${BLUE}Service Status:${NC}"
    echo ""
    cd "$PROJECT_DIR"
    docker-compose ps
    echo ""
    print_info "Endpoints:"
    echo "  • Dashboard:     http://localhost:3000"
    echo "  • Load Balancer: http://localhost:9000/lb/status"
    echo "  • Health Monitor: http://localhost:8080/status"
    echo "  • US-East API:   http://localhost:8001/api/data"
    echo "  • EU-West API:   http://localhost:8002/api/data"
    echo "  • AP-Southeast:  http://localhost:8003/api/data"
}

logs() {
    cd "$PROJECT_DIR"
    if [ -z "$2" ]; then
        docker-compose logs -f --tail=100
    else
        docker-compose logs -f --tail=100 "$2"
    fi
}

# Simulate region failure
fail_region() {
    local region=$1
    local port

    case $region in
        "us-east")     port=8001; region_name="us-east-1" ;;
        "eu-west")     port=8002; region_name="eu-west-1" ;;
        "ap-southeast") port=8003; region_name="ap-southeast-1" ;;
        *)
            print_error "Invalid region. Use: us-east, eu-west, or ap-southeast"
            exit 1
            ;;
    esac

    print_warning "Simulating failure for $region_name..."
    curl -s -X POST "http://localhost:$port/admin/fail" \
        -H "Content-Type: application/json" \
        -d '{"type": "general", "duration": 120}' | jq .

    print_info "Failure simulated for 120 seconds. Watch the dashboard for failover!"
}

# Recover a region
recover_region() {
    local region=$1
    local port

    case $region in
        "us-east")     port=8001 ;;
        "eu-west")     port=8002 ;;
        "ap-southeast") port=8003 ;;
        *)
            print_error "Invalid region. Use: us-east, eu-west, or ap-southeast"
            exit 1
            ;;
    esac

    print_info "Recovering region..."
    curl -s -X POST "http://localhost:$port/admin/recover" | jq .
    print_success "Region recovered!"
}

# Add latency to a region
add_latency() {
    local region=$1
    local latency=$2
    local port

    case $region in
        "us-east")     port=8001 ;;
        "eu-west")     port=8002 ;;
        "ap-southeast") port=8003 ;;
        *)
            print_error "Invalid region. Use: us-east, eu-west, or ap-southeast"
            exit 1
            ;;
    esac

    print_info "Adding ${latency}ms latency to $region..."
    curl -s -X POST "http://localhost:$port/admin/latency" \
        -H "Content-Type: application/json" \
        -d "{\"latency_ms\": $latency}" | jq .
}

# Run load test
load_test() {
    local requests=${1:-100}
    print_info "Running load test with $requests requests..."

    for i in $(seq 1 $requests); do
        curl -s "http://localhost:9000/api/data" > /dev/null &
    done

    wait
    print_success "Load test complete!"
}

# Show metrics
metrics() {
    print_header
    echo -e "${BLUE}Load Balancer Status:${NC}"
    curl -s "http://localhost:9000/lb/status" | jq '{
        strategy,
        total_requests,
        total_failovers,
        active_failover,
        healthy_regions,
        total_regions
    }'

    echo ""
    echo -e "${BLUE}Region Health:${NC}"
    curl -s "http://localhost:9000/lb/status" | jq '.regions | to_entries[] | {
        region: .key,
        healthy: .value.is_healthy,
        status: .value.status,
        latency_ms: .value.latency_ms,
        requests: .value.total_requests
    }'
}

# Clean up
clean() {
    print_header
    print_warning "This will remove all containers and volumes..."
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$PROJECT_DIR"
        docker-compose down -v --remove-orphans
        docker system prune -f
        print_success "Cleanup complete!"
    fi
}

# Usage
usage() {
    print_header
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  start               Start all services"
    echo "  stop                Stop all services"
    echo "  restart             Restart all services"
    echo "  status              Show service status and endpoints"
    echo "  logs [service]      Show logs (optional: specific service)"
    echo "  fail <region>       Simulate region failure (us-east|eu-west|ap-southeast)"
    echo "  recover <region>    Recover a failed region"
    echo "  latency <region> <ms>  Add latency to a region"
    echo "  load [count]        Run load test (default: 100 requests)"
    echo "  metrics             Show current metrics"
    echo "  clean               Remove all containers and volumes"
    echo "  help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 fail us-east"
    echo "  $0 recover us-east"
    echo "  $0 latency eu-west 500"
    echo "  $0 load 1000"
}

# Main
case "$1" in
    start)    start ;;
    stop)     stop ;;
    restart)  restart ;;
    status)   status ;;
    logs)     logs "$@" ;;
    fail)     fail_region "$2" ;;
    recover)  recover_region "$2" ;;
    latency)  add_latency "$2" "$3" ;;
    load)     load_test "$2" ;;
    metrics)  metrics ;;
    clean)    clean ;;
    help|*)   usage ;;
esac
