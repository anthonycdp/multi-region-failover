#!/bin/bash
# Chaos Engineering Script for Multi-Region Failover Demo
# Inspired by Chaos Monkey / Simmy - simulates various failure scenarios

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default values
DEFAULT_DURATION=60
DEFAULT_LATENCY=2000
DEFAULT_PACKET_LOSS=20

print_banner() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    CHAOS MONKEY 🐒                           ║"
    echo "║              Failure Injection Testing                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_chaos() {
    echo -e "${PURPLE}[CHAOS]${NC} $1"
}

# Get port for region
get_region_port() {
    local region=$1
    case $region in
        "us-east")      echo "8001" ;;
        "eu-west")      echo "8002" ;;
        "ap-southeast") echo "8003" ;;
        *)              echo "" ;;
    esac
}

# Get full region name
get_region_name() {
    local region=$1
    case $region in
        "us-east")      echo "us-east-1" ;;
        "eu-west")      echo "eu-west-1" ;;
        "ap-southeast") echo "ap-southeast-1" ;;
        *)              echo "$region" ;;
    esac
}

# Simulate region failure
inject_failure() {
    local region=$1
    local duration=${2:-$DEFAULT_DURATION}
    local failure_type=${3:-"general"}

    local port=$(get_region_port "$region")
    local region_name=$(get_region_name "$region")

    if [ -z "$port" ]; then
        log_error "Invalid region: $region"
        return 1
    fi

    log_chaos "Injecting $failure_type failure into $region_name for ${duration}s..."

    curl -s -X POST "http://localhost:$port/admin/fail" \
        -H "Content-Type: application/json" \
        -d "{\"type\": \"$failure_type\", \"duration\": $duration}"

    log_success "Failure injected! Watch the dashboard for failover."
}

# Recover a region
recover_region() {
    local region=$1
    local port=$(get_region_port "$region")

    if [ -z "$port" ]; then
        log_error "Invalid region: $region"
        return 1
    fi

    log_info "Recovering $region..."
    curl -s -X POST "http://localhost:$port/admin/recover" > /dev/null
    log_success "Region recovered!"
}

# Add latency
inject_latency() {
    local region=$1
    local latency=${2:-$DEFAULT_LATENCY}
    local port=$(get_region_port "$region")

    if [ -z "$port" ]; then
        log_error "Invalid region: $region"
        return 1
    fi

    log_chaos "Adding ${latency}ms latency to $region..."

    curl -s -X POST "http://localhost:$port/admin/latency" \
        -H "Content-Type: application/json" \
        -d "{\"latency_ms\": $latency}"

    log_success "Latency injected!"
}

# Random region failure (true Chaos Monkey style)
random_failure() {
    local duration=${1:-$DEFAULT_DURATION}
    local regions=("us-east" "eu-west" "ap-southeast")

    # Pick random region
    local random_index=$((RANDOM % ${#regions[@]}))
    local region=${regions[$random_index]}

    log_chaos "🎲 Chaos Monkey selected: $region"
    inject_failure "$region" "$duration"
}

# Cascading failure simulation
cascading_failure() {
    local interval=${1:-30}
    local duration=${2:-120}

    log_chaos "Starting cascading failure simulation..."
    log_info "Regions will fail sequentially with ${interval}s interval"

    # Fail US-East first
    inject_failure "us-east" "$duration"
    sleep "$interval"

    # Fail EU-West
    inject_failure "eu-west" "$duration"
    sleep "$interval"

    # Fail AP-Southeast (total outage)
    inject_failure "ap-southeast" "$duration"

    log_warning "ALL REGIONS DOWN! Complete outage simulation."
    log_info "Regions will auto-recover after ${duration}s"
}

# Flapping simulation (rapid up/down)
flapping_simulation() {
    local region=${1:-"us-east"}
    local cycles=${2:-5}
    local interval=${3:-10}

    local port=$(get_region_port "$region")

    log_chaos "Starting flapping simulation for $region ($cycles cycles)"

    for i in $(seq 1 $cycles); do
        log_info "Cycle $i: Failing region..."
        curl -s -X POST "http://localhost:$port/admin/fail" \
            -H "Content-Type: application/json" \
            -d '{"type": "general", "duration": 5}'
        sleep "$interval"
        curl -s -X POST "http://localhost:$port/admin/recover" > /dev/null
        log_info "Cycle $i: Region recovered"
        sleep "$interval"
    done

    log_success "Flapping simulation complete!"
}

# Network partition simulation (fail all but one)
network_partition() {
    local surviving_region=${1:-"eu-west"}
    local duration=${2:-$DEFAULT_DURATION}
    local regions=("us-east" "eu-west" "ap-southeast")

    log_chaos "Simulating network partition - only $surviving_region survives"

    for region in "${regions[@]}"; do
        if [ "$region" != "$surviving_region" ]; then
            inject_failure "$region" "$duration" &
        fi
    done

    wait
    log_warning "Network partition active! Only $surviving_region is reachable."
}

# Database failure simulation
database_failure() {
    local region=${1:-"us-east"}
    local duration=${2:-$DEFAULT_DURATION}
    local port=$(get_region_port "$region")

    log_chaos "Simulating database failure in $region..."

    curl -s -X POST "http://localhost:$port/admin/fail" \
        -H "Content-Type: application/json" \
        -d "{\"type\": \"database\", \"duration\": $duration}"

    log_success "Database failure injected!"
}

# Stress test - high latency across all regions
stress_test() {
    local latency=${1:-3000}
    local duration=${2:-60}

    log_chaos "Starting stress test - adding ${latency}ms latency to all regions"

    for port in 8001 8002 8003; do
        curl -s -X POST "http://localhost:$port/admin/latency" \
            -H "Content-Type: application/json" \
            -d "{\"latency_ms\": $latency}" &
    done

    wait
    log_warning "Stress test active! All regions have high latency."

    # Auto-recover after duration
    (
        sleep "$duration"
        log_info "Auto-recovering from stress test..."
        for port in 8001 8002 8003; do
            curl -s -X POST "http://localhost:$port/admin/latency" \
                -H "Content-Type: application/json" \
                -d '{"latency_ms": 50}' > /dev/null &
        done
        wait
        log_success "Stress test complete!"
    ) &
}

# Blast radius test - fail primary and monitor impact
blast_radius_test() {
    local duration=${1:-60}

    log_chaos "Starting blast radius test..."
    log_info "This will fail the primary region to test failover behavior"

    # Capture initial state
    log_info "Initial state:"
    curl -s "http://localhost:9000/lb/status" | jq '{
        healthy_regions,
        total_regions,
        active_failover
    }'

    # Fail primary
    inject_failure "us-east" "$duration"

    # Monitor for failover
    sleep 5
    log_info "After 5s:"
    curl -s "http://localhost:9000/lb/status" | jq '{
        healthy_regions,
        total_regions,
        active_failover,
        regions: .regions | to_entries | map({region: .key, healthy: .value.is_healthy, status: .value.status})
    }'

    sleep 10
    log_info "After 15s (failover should be complete):"
    curl -s "http://localhost:9000/lb/status" | jq '{
        healthy_regions,
        active_failover,
        serving_from: (.regions | to_entries | map(select(.value.is_healthy == true)) | .[0].key)
    }'
}

# Recovery all regions
recover_all() {
    log_info "Recovering all regions..."

    for port in 8001 8002 8003; do
        curl -s -X POST "http://localhost:$port/admin/recover" > /dev/null &
        curl -s -X POST "http://localhost:$port/admin/latency" \
            -H "Content-Type: application/json" \
            -d '{"latency_ms": 50}' > /dev/null &
    done

    wait
    log_success "All regions recovered!"
}

# Show current status
show_status() {
    log_info "Current System Status:"
    echo ""
    curl -s "http://localhost:9000/lb/status" | jq '{
        strategy,
        total_requests,
        total_failovers,
        active_failover,
        healthy_regions,
        total_regions,
        regions: .regions | to_entries | map({
            region: .key,
            healthy: .value.is_healthy,
            status: .value.status,
            latency_ms: .value.latency_ms,
            requests: .value.total_requests
        })
    }'
}

# Run comprehensive chaos test suite
run_test_suite() {
    local test_type=${1:-"basic"}

    case $test_type in
        "basic")
            print_banner
            log_info "Running BASIC chaos test suite..."
            echo ""

            log_info "Test 1: Single region failure"
            inject_failure "us-east" 30
            sleep 20
            recover_region "us-east"
            sleep 5

            log_info "Test 2: Latency injection"
            inject_latency "eu-west" 1000
            sleep 10
            inject_latency "eu-west" 50

            log_success "Basic test suite complete!"
            ;;

        "advanced")
            print_banner
            log_info "Running ADVANCED chaos test suite..."
            echo ""

            log_info "Test 1: Primary failover"
            inject_failure "us-east" 45
            sleep 20
            recover_region "us-east"
            sleep 5

            log_info "Test 2: Database failure"
            database_failure "eu-west" 30
            sleep 20
            ;;

        "extreme")
            print_banner
            log_warning "Running EXTREME chaos test suite..."
            log_warning "This will cause significant disruption!"
            echo ""

            log_info "Test 1: Cascading failures"
            cascading_failure 15 60
            sleep 60

            recover_all
            sleep 10

            log_info "Test 2: Stress test"
            stress_test 3000 30
            sleep 35

            log_success "Extreme test suite complete!"
            ;;

        *)
            log_error "Unknown test suite: $test_type"
            log_info "Available: basic, advanced, extreme"
            return 1
            ;;
    esac
}

# Usage
usage() {
    print_banner
    echo "Usage: $0 <command> [args]"
    echo ""
    echo -e "${CYAN}Failure Injection Commands:${NC}"
    echo "  fail <region> [duration] [type]  - Inject failure into region"
    echo "  recover <region>                 - Recover a failed region"
    echo "  recover-all                      - Recover all regions"
    echo "  latency <region> <ms>            - Add latency to region"
    echo "  database <region> [duration]     - Simulate DB failure"
    echo ""
    echo -e "${CYAN}Chaos Scenarios:${NC}"
    echo "  random [duration]                - Random region failure"
    echo "  cascade [interval] [duration]    - Cascading failures"
    echo "  flap <region> [cycles]           - Flapping simulation"
    echo "  partition <survivor> [duration]  - Network partition"
    echo "  stress [latency] [duration]      - Stress all regions"
    echo "  blast-radius [duration]          - Blast radius test"
    echo ""
    echo -e "${CYAN}Test Suites:${NC}"
    echo "  suite basic                      - Basic chaos tests"
    echo "  suite advanced                   - Advanced chaos tests"
    echo "  suite extreme                    - Extreme chaos tests"
    echo ""
    echo -e "${CYAN}Utilities:${NC}"
    echo "  status                           - Show current status"
    echo ""
    echo -e "${CYAN}Regions:${NC} us-east, eu-west, ap-southeast"
    echo ""
    echo "Examples:"
    echo "  $0 fail us-east 60               - Fail US-East for 60s"
    echo "  $0 random 30                     - Random region fails for 30s"
    echo "  $0 cascade 20 90                 - Cascading failures"
    echo "  $0 suite basic                   - Run basic test suite"
}

# Main
case "$1" in
    fail)           inject_failure "$2" "${3:-60}" "${4:-general}" ;;
    recover)        recover_region "$2" ;;
    recover-all)    recover_all ;;
    latency)        inject_latency "$2" "${3:-2000}" ;;
    database)       database_failure "$2" "${3:-60}" ;;
    random)         random_failure "${2:-60}" ;;
    cascade)        cascading_failure "${2:-30}" "${3:-120}" ;;
    flap)           flapping_simulation "$2" "${3:-5}" "${4:-10}" ;;
    partition)      network_partition "$2" "${3:-60}" ;;
    stress)         stress_test "${2:-3000}" "${3:-60}" ;;
    blast-radius)   blast_radius_test "${2:-60}" ;;
    blast)          blast_radius_test "${2:-60}" ;;
    suite)          run_test_suite "$2" ;;
    status)         show_status ;;
    help|*)         usage ;;
esac
