.PHONY: all start stop restart status logs clean test fail-us fail-eu fail-ap recover metrics dashboard help chaos chaos-suite prometheus grafana haproxy

# Default target
all: start

# Start all services
start:
	@./scripts/demo.sh start

# Stop all services
stop:
	@./scripts/demo.sh stop

# Restart all services
restart:
	@./scripts/demo.sh restart

# Show service status
status:
	@./scripts/demo.sh status

# Show logs
logs:
	@./scripts/demo.sh logs

# Clean up containers and volumes
clean:
	@./scripts/demo.sh clean

# Run load test
test:
	@python test.py

# Run integration test
itest:
	@./scripts/demo.sh load 500

# Simulate US-East failure
fail-us:
	@./scripts/chaos/chaos-monkey.sh fail us-east 60

# Simulate EU-West failure
fail-eu:
	@./scripts/chaos/chaos-monkey.sh fail eu-west 60

# Simulate AP-Southeast failure
fail-ap:
	@./scripts/chaos/chaos-monkey.sh fail ap-southeast 60

# Recover all regions
recover:
	@./scripts/failover.sh recover

# Show metrics
metrics:
	@./scripts/demo.sh metrics

# Open dashboard in browser
dashboard:
	@open http://localhost:3000 || xdg-open http://localhost:3000 2>/dev/null || echo "Open http://localhost:3000 in your browser"

# Open Grafana dashboard
grafana:
	@open http://localhost:3001 || xdg-open http://localhost:3001 2>/dev/null || echo "Open http://localhost:3001 in your browser"

# Open Prometheus UI
prometheus:
	@open http://localhost:9090 || xdg-open http://localhost:9090 2>/dev/null || echo "Open http://localhost:9090 in your browser"

# Start with HAProxy
haproxy:
	@docker-compose --profile haproxy up -d

# Chaos engineering: random failure
chaos:
	@./scripts/chaos/chaos-monkey.sh random 60

# Chaos engineering: run test suite
chaos-suite:
	@./scripts/chaos/chaos-monkey.sh suite basic

# Chaos engineering: cascading failures
chaos-cascade:
	@./scripts/chaos/chaos-monkey.sh cascade 30 120

# Chaos engineering: stress test
chaos-stress:
	@./scripts/chaos/chaos-monkey.sh stress 2000 60

# Failover control
failover-status:
	@./scripts/failover.sh status

# Failover health check
failover-health:
	@./scripts/failover.sh health

# Watch failover status
watch:
	@./scripts/failover.sh watch 5

# Show help
help:
	@echo "Multi-Region Failover Demo"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Service Management:"
	@echo "  start           Start all services"
	@echo "  stop            Stop all services"
	@echo "  restart         Restart all services"
	@echo "  status          Show service status"
	@echo "  logs            Show service logs"
	@echo "  clean           Remove all containers and volumes"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run unit tests"
	@echo "  itest           Run integration/load test"
	@echo ""
	@echo "Failure Simulation:"
	@echo "  fail-us         Simulate US-East failure"
	@echo "  fail-eu         Simulate EU-West failure"
	@echo "  fail-ap         Simulate AP-Southeast failure"
	@echo "  recover         Recover all regions"
	@echo ""
	@echo "Chaos Engineering:"
	@echo "  chaos           Random region failure"
	@echo "  chaos-suite     Run chaos test suite"
	@echo "  chaos-cascade   Cascading failures"
	@echo "  chaos-stress    Stress all regions"
	@echo ""
	@echo "Failover Control:"
	@echo "  failover-status Show failover status"
	@echo "  failover-health Health check all regions"
	@echo "  watch           Watch failover status (live)"
	@echo ""
	@echo "Monitoring:"
	@echo "  metrics         Show current metrics"
	@echo "  dashboard       Open web dashboard (port 3000)"
	@echo "  grafana         Open Grafana (port 3001)"
	@echo "  prometheus      Open Prometheus (port 9090)"
	@echo "  haproxy         Start with HAProxy load balancer"
	@echo ""
	@echo "  help            Show this help message"
