#!/bin/bash
# Failover Controller Script
# Manages failover orchestration and recovery procedures

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if a region is healthy
check_region_health() {
    local region=$1
    local port

    case $region in
        "us-east")      port=8001 ;;
        "eu-west")      port=8002 ;;
        "ap-southeast") port=8003 ;;
        *)              return 1 ;;
    esac

    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" 2>/dev/null || echo "000")

    if [ "$response" = "200" ]; then
        return 0
    else
        return 1
    fi
}

# Get current active region
get_active_region() {
    local status=$(curl -s "http://localhost:9000/lb/status" 2>/dev/null)

    if [ -n "$status" ]; then
        echo "$status" | jq -r '.regions | to_entries | map(select(.value.is_healthy == true and .value.status == "active")) | .[0].key // "none"'
    else
        echo "unknown"
    fi
}

# Get region status
get_region_status() {
    local region=$1
    local status=$(curl -s "http://localhost:9000/lb/status" 2>/dev/null)

    if [ -n "$status" ]; then
        echo "$status" | jq -r ".regions[\"$region\"].status // \"unknown\""
    else
        echo "unknown"
    fi
}

# Manual failover to specific region
manual_failover() {
    local target_region=$1
    local target_port

    case $target_region in
        "us-east"|"us-east-1")     target_region="us-east-1"; target_port=8001 ;;
        "eu-west"|"eu-west-1")     target_region="eu-west-1"; target_port=8002 ;;
        "ap-southeast"|"ap-southeast-1") target_region="ap-southeast-1"; target_port=8003 ;;
        *)
            log_error "Invalid region: $target_region"
            return 1
            ;;
    esac

    log_info "Initiating manual failover to $target_region..."

    # Check if target is healthy
    if ! curl -s -o /dev/null -w "%{http_code}" "http://localhost:$target_port/health" | grep -q "200"; then
        log_error "Target region $target_region is not healthy!"
        return 1
    fi

    # Put other regions in maintenance mode
    for region in "us-east-1" "eu-west-1" "ap-southeast-1"; do
        if [ "$region" != "$target_region" ]; then
            log_info "Setting $region to maintenance mode..."
            curl -s "http://localhost:9000/lb/region/$region/maintenance" > /dev/null
        fi
    done

    log_success "Failover to $target_region complete!"
}

# Automatic failover (find next healthy region)
auto_failover() {
    log_info "Checking for automatic failover opportunity..."

    local current_active=$(get_active_region)
    log_info "Current active region: $current_active"

    # Priority order: us-east-1, eu-west-1, ap-southeast-1
    for region in "us-east" "eu-west" "ap-southeast"; do
        local region_full="${region}-1"

        if [ "$region_full" != "$current_active" ]; then
            if check_region_health "$region"; then
                log_info "Found healthy failover target: $region_full"
                manual_failover "$region_full"
                return 0
            fi
        fi
    done

    log_error "No healthy regions available for failover!"
    return 1
}

# Recover all regions
recover_all() {
    log_info "Initiating recovery of all regions..."

    for port in 8001 8002 8003; do
        log_info "Recovering region on port $port..."
        curl -s -X POST "http://localhost:$port/admin/recover" > /dev/null
    done

    # Reactivate all regions in load balancer
    for region in "us-east-1" "eu-west-1" "ap-southeast-1"; do
        log_info "Activating $region in load balancer..."
        curl -s "http://localhost:9000/lb/region/$region/activate" > /dev/null
    done

    log_success "All regions recovered and activated!"
}

# Health check all regions
health_check() {
    log_info "Performing health check on all regions..."
    echo ""

    all_healthy=true

    for region in "us-east" "eu-west" "ap-southeast"; do
        local port
        case $region in
            "us-east")      port=8001 ;;
            "eu-west")      port=8002 ;;
            "ap-southeast") port=8003 ;;
        esac

        if check_region_health "$region"; then
            echo -e "  ${GREEN}✓${NC} ${region}-1: ${GREEN}HEALTHY${NC}"
        else
            echo -e "  ${RED}✗${NC} ${region}-1: ${RED}UNHEALTHY${NC}"
            all_healthy=false
        fi
    done

    echo ""

    if $all_healthy; then
        log_success "All regions are healthy!"
        return 0
    else
        log_warning "Some regions are unhealthy!"
        return 1
    fi
}

# Change load balancing strategy
set_strategy() {
    local strategy=$1

    case $strategy in
        "priority"|"weighted"|"round_robin"|"least_latency")
            log_info "Setting load balancing strategy to: $strategy"
            curl -s "http://localhost:9000/lb/strategy/$strategy" > /dev/null
            log_success "Strategy changed to $strategy"
            ;;
        *)
            log_error "Invalid strategy: $strategy"
            log_info "Valid strategies: priority, weighted, round_robin, least_latency"
            return 1
            ;;
    esac
}

# Show detailed status
show_status() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              FAILOVER CONTROLLER STATUS                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Get load balancer status
    local lb_status=$(curl -s "http://localhost:9000/lb/status" 2>/dev/null)

    if [ -z "$lb_status" ]; then
        log_error "Cannot connect to load balancer!"
        return 1
    fi

    echo "$lb_status" | jq '{
        "Strategy": .strategy,
        "Total Requests": .total_requests,
        "Total Failovers": .total_failovers,
        "Active Failover": .active_failover,
        "Healthy Regions": "\(.healthy_regions)/\(.total_regions)"
    }'

    echo ""
    echo -e "${BLUE}Region Details:${NC}"
    echo ""

    echo "$lb_status" | jq -r '.regions | to_entries[] | "  \(.key): \(.value.status) | Healthy: \(.value.is_healthy) | Latency: \(.value.latency_ms)ms | Requests: \(.value.total_requests)"'
}

# Watch mode - continuous monitoring
watch_status() {
    local interval=${1:-5}

    log_info "Starting watch mode (refresh every ${interval}s)..."
    log_info "Press Ctrl+C to stop"
    echo ""

    while true; do
        clear
        show_status
        sleep "$interval"
    done
}

# Usage
usage() {
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  status                           Show current status"
    echo "  health                           Health check all regions"
    echo "  failover <region>                Manual failover to region"
    echo "  auto-failover                    Automatic failover to next healthy region"
    echo "  recover                          Recover all regions"
    echo "  strategy <name>                  Set LB strategy"
    echo "  watch [interval]                 Continuous monitoring"
    echo ""
    echo "Regions: us-east, eu-west, ap-southeast"
    echo "Strategies: priority, weighted, round_robin, least_latency"
}

# Main
case "$1" in
    status)         show_status ;;
    health)         health_check ;;
    failover)       manual_failover "$2" ;;
    auto-failover)  auto_failover ;;
    auto)           auto_failover ;;
    recover)        recover_all ;;
    strategy)       set_strategy "$2" ;;
    watch)          watch_status "${2:-5}" ;;
    help|*)         usage ;;
esac
