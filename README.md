# Multi-Region Failover Demo

A production-ready demonstration of multi-region deployment architecture with automated failover, health monitoring, and disaster recovery capabilities. This project simulates a globally distributed application infrastructure using Docker containers.

## Features

- **Multi-Region Deployment**: Simulated deployment across 3 regions (US-East, EU-West, AP-Southeast)
- **Automatic Failover**: Health-based failover with configurable thresholds
- **Global Load Balancing**: Multiple strategies (priority, weighted, round-robin, least-latency)
- **HAProxy Integration**: Optional production-grade load balancer with health checks
- **Real-time Monitoring**: Live dashboard with region health visualization
- **Prometheus + Grafana**: Comprehensive monitoring stack with pre-built dashboards
- **Chaos Engineering**: Built-in failure simulation scripts (Chaos Monkey style)
- **Prometheus Metrics**: Export metrics for external monitoring systems
- **Zero External Dependencies**: Pure Python implementation using only stdlib

## Architecture

```
                                    ┌─────────────────────────────────────────┐
                                    │           Client Traffic                │
                                    └───────────────────┬─────────────────────┘
                                                        │
                                                        ▼
                                    ┌─────────────────────────────────────────┐
                                    │        Global Load Balancer             │
                                    │        (Port 9000)                      │
                                    │  • Health-based routing                 │
                                    │  • Multiple LB strategies               │
                                    │  • Automatic failover                   │
                                    └───────────────────┬─────────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        │                               │                               │
                        ▼                               ▼                               ▼
        ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐
        │        US-EAST-1          │   │        EU-WEST-1          │   │     AP-SOUTHEAST-1        │
        │      (Primary)            │   │       (Secondary)         │   │       (Secondary)         │
        │       Port 8001           │   │       Port 8002           │   │       Port 8003           │
        │                           │   │                           │   │                           │
        │  • Application Server     │   │  • Application Server     │   │  • Application Server     │
        │  • Primary Database       │   │  • Read Replica DB        │   │  • Read Replica DB        │
        │  • Priority: 1            │   │  • Priority: 2            │   │  • Priority: 3            │
        └───────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘
                        │                               │                               │
                        └───────────────────────────────┴───────────────────────────────┘
                                                        │
                                                        ▼
                                    ┌─────────────────────────────────────────┐
                                    │         Health Monitor                  │
                                    │         (Port 8080)                     │
                                    │  • Continuous health checks             │
                                    │  • Alert aggregation                    │
                                    │  • Availability metrics                 │
                                    └─────────────────────────────────────────┘
                                                        │
                                                        ▼
                                    ┌─────────────────────────────────────────┐
                                    │           Dashboard                     │
                                    │           (Port 3000)                   │
                                    │  • Real-time visualization              │
                                    │  • Failover simulation controls         │
                                    │  • Alert history                        │
                                    └─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- curl, jq (for testing scripts)

### Start the Demo

```bash
# Clone and start
cd 24-multi-region-failover

# Make scripts executable
chmod +x scripts/demo.sh

# Start all services
./scripts/demo.sh start
```

### Access the Services

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | Visual monitoring interface |
| Grafana | http://localhost:3001 | Grafana monitoring dashboard |
| Prometheus | http://localhost:9090 | Prometheus metrics and queries |
| Load Balancer | http://localhost:9000/lb/status | LB status and metrics |
| Health Monitor | http://localhost:8080/status | Region health status |
| HAProxy Stats | http://localhost:8404 | HAProxy statistics (optional) |
| US-East API | http://localhost:8001/api/data | Direct region access |
| EU-West API | http://localhost:8002/api/data | Direct region access |
| AP-Southeast API | http://localhost:8003/api/data | Direct region access |

## Usage Examples

### Testing Failover

```bash
# Simulate US-East failure
./scripts/demo.sh fail us-east

# Watch the dashboard for automatic failover
open http://localhost:3000

# Recover the region
./scripts/demo.sh recover us-east
```

### Load Testing

```bash
# Run 1000 requests through the load balancer
./scripts/demo.sh load 1000

# Check metrics
./scripts/demo.sh metrics
```

### Add Latency

```bash
# Add 2 second latency to EU-West
./scripts/demo.sh latency eu-west 2000
```

## API Reference

### Regional Service Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/deep` | GET | Full dependency health check |
| `/metrics` | GET | Prometheus-format metrics |
| `/status` | GET | Detailed service status |
| `/api/data` | GET | Sample API endpoint |
| `/admin/fail` | POST | Simulate failure |
| `/admin/recover` | POST | Recover from failure |
| `/admin/latency` | POST | Add latency |

### Load Balancer Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/lb/status` | GET | All regions status |
| `/lb/health` | GET | LB health check |
| `/lb/failovers` | GET | Failover history |
| `/lb/strategy/{strategy}` | GET | Change LB strategy |
| `/lb/region/{name}/maintenance` | GET | Set region to maintenance |
| `/lb/region/{name}/activate` | GET | Activate region |
| `/*` | ALL | Proxied to backend |

### Health Monitor Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Monitor status and all regions |
| `/health` | GET | Monitor health check |
| `/alerts` | GET | Recent alerts |
| `/region/{name}` | GET | Specific region details |

## Load Balancing Strategies

The system supports multiple load balancing strategies:

### 1. Priority (Default)
Routes all traffic to the highest priority healthy region.

```bash
curl http://localhost:9000/lb/strategy/priority
```

### 2. Weighted
Distributes traffic based on region weights.

```bash
curl http://localhost:9000/lb/strategy/weighted
```

### 3. Round Robin
Cycles through healthy regions evenly.

```bash
curl http://localhost:9000/lb/strategy/round_robin
```

### 4. Least Latency
Routes to the region with lowest latency.

```bash
curl http://localhost:9000/lb/strategy/least_latency
```

## Configuration

### Environment Variables

#### Regional Service

| Variable | Default | Description |
|----------|---------|-------------|
| `REGION` | us-east-1 | Region identifier |
| `PORT` | 8000 | Service port |
| `PRIMARY` | false | Is primary region |
| `DB_HOST` | localhost | Database host |
| `DB_PORT` | 5432 | Database port |

#### Load Balancer

| Variable | Default | Description |
|----------|---------|-------------|
| `LB_PORT` | 9000 | LB service port |
| `HEALTH_CHECK_INTERVAL` | 5 | Health check interval (sec) |
| `FAILURE_THRESHOLD` | 3 | Failures before failover |
| `RECOVERY_THRESHOLD` | 2 | Successes before recovery |
| `REQUEST_TIMEOUT` | 10 | Request timeout (sec) |

#### Health Monitor

| Variable | Default | Description |
|----------|---------|-------------|
| `MONITOR_PORT` | 8080 | Monitor service port |
| `CHECK_INTERVAL` | 5 | Check interval (sec) |
| `FAILURE_THRESHOLD` | 3 | Failures before alert |
| `RECOVERY_THRESHOLD` | 2 | Successes before recovery |

## Prometheus Metrics

The regional services expose Prometheus-compatible metrics at `/metrics`:

```promql
# Request count by region
service_requests_total{region="us-east-1"}

# Health status (1 = healthy, 0 = unhealthy)
service_healthy{region="us-east-1"}

# Response latency
service_latency_ms{region="us-east-1"}

# Resource usage
service_cpu_usage{region="us-east-1"}
service_memory_usage{region="us-east-1"}

# Replication lag (secondary only)
service_replication_lag_ms{region="eu-west-1"}
```

## Monitoring Stack

### Prometheus

Prometheus is configured to scrape metrics from all regional services and provides alerting capabilities.

**Key Features:**
- Automatic service discovery
- Pre-configured alert rules for failover events
- 10-second scrape interval
- Web UI at http://localhost:9090

**Useful Queries:**
```promql
# Overall health status
sum(service_healthy) / count(service_healthy) * 100

# Request rate
sum(rate(service_requests_total[5m]))

# P99 latency approximation
max(service_latency_ms) by (region)

# Alert status
ALERTS{alertstate="firing"}
```

### Grafana

Pre-configured Grafana dashboard with:
- System overview (healthy regions, request rate, latency, failover status)
- Region health panel with status indicators
- Latency graphs by region
- Request rate graphs
- CPU/Memory usage monitoring
- Database replication lag tracking

**Access:**
- URL: http://localhost:3001
- Username: `admin`
- Password: `admin123`

## Chaos Engineering

The project includes a Chaos Monkey-style script for testing failover scenarios:

### Basic Chaos Commands

```bash
# Random region failure
make chaos
# or
./scripts/chaos/chaos-monkey.sh random 60

# Specific region failure
./scripts/chaos/chaos-monkey.sh fail us-east 60

# Database failure simulation
./scripts/chaos/chaos-monkey.sh database eu-west 60

# Add latency
./scripts/chaos/chaos-monkey.sh latency ap-southeast 2000
```

### Advanced Scenarios

```bash
# Cascading failures (fail regions sequentially)
./scripts/chaos/chaos-monkey.sh cascade 30 120

# Network partition (only one region survives)
./scripts/chaos/chaos-monkey.sh partition eu-west 60

# Stress test (add latency to all regions)
./scripts/chaos/chaos-monkey.sh stress 3000 60

# Flapping simulation (rapid up/down)
./scripts/chaos/chaos-monkey.sh flap us-east 5 10

# Blast radius test
./scripts/chaos/chaos-monkey.sh blast-radius 60
```

### Test Suites

```bash
# Basic test suite
make chaos-suite
# or
./scripts/chaos/chaos-monkey.sh suite basic

# Advanced test suite
./scripts/chaos/chaos-monkey.sh suite advanced

# Extreme test suite (WARNING: causes significant disruption)
./scripts/chaos/chaos-monkey.sh suite extreme
```

### Recovery

```bash
# Recover all regions
make recover
# or
./scripts/chaos/chaos-monkey.sh recover-all
```

## Makefile Commands

```bash
# Service Management
make start           # Start all services
make stop            # Stop all services
make restart         # Restart all services
make status          # Show service status
make logs            # Show logs
make clean           # Clean up containers and volumes

# Testing
make test            # Run unit tests
make itest           # Run integration/load test

# Failure Simulation
make fail-us         # Fail US-East
make fail-eu         # Fail EU-West
make fail-ap         # Fail AP-Southeast
make recover         # Recover all regions

# Chaos Engineering
make chaos           # Random region failure
make chaos-suite     # Run chaos test suite
make chaos-cascade   # Cascading failures
make chaos-stress    # Stress all regions

# Monitoring
make metrics         # Show current metrics
make dashboard       # Open web dashboard
make grafana         # Open Grafana
make prometheus      # Open Prometheus
make watch           # Watch failover status

# Load Balancer
make haproxy         # Start with HAProxy
make failover-status # Show failover status
make failover-health # Health check all regions
```

## Project Structure

```
24-multi-region-failover/
├── app/
│   ├── service.py          # Regional application service
│   └── Dockerfile
├── monitor/
│   ├── health_monitor.py   # Health monitoring service
│   └── Dockerfile
├── loadbalancer/
│   ├── failover_lb.py      # Global load balancer with failover
│   └── Dockerfile
├── dashboard/
│   ├── dashboard.py        # Web dashboard
│   └── Dockerfile
├── config/
│   ├── prometheus/
│   │   ├── prometheus.yml  # Prometheus configuration
│   │   └── alerts/
│   │       └── failover_alerts.yml  # Alert rules
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/
│   │   │   └── dashboards/
│   │   └── dashboards/
│   │       └── multi-region-overview.json
│   └── haproxy/
│       └── haproxy.cfg     # HAProxy configuration
├── scripts/
│   ├── demo.sh             # Management and demo script
│   ├── failover.sh         # Failover control script
│   └── chaos/
│       └── chaos-monkey.sh # Chaos engineering script
├── tests/
│   └── test_*.py           # Test files
├── docs/
│   ├── DISASTER_RECOVERY.md
│   └── ARCHITECTURE.md
├── docker-compose.yml
├── Makefile
└── README.md
```

## Disaster Recovery

For complete disaster recovery procedures, see [DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md).

### Quick Recovery Commands

```bash
# Check system status
./scripts/demo.sh status

# View all metrics
./scripts/demo.sh metrics

# Recover all failed regions
./scripts/demo.sh recover us-east
./scripts/demo.sh recover eu-west
./scripts/demo.sh recover ap-southeast

# Full system restart
./scripts/demo.sh restart
```

## Testing Scenarios

### Scenario 1: Primary Region Failure

```bash
# 1. Verify initial state
curl http://localhost:9000/lb/status | jq '.regions'

# 2. Fail primary region
./scripts/demo.sh fail us-east

# 3. Wait 15 seconds for failover
sleep 15

# 4. Verify traffic routing
curl http://localhost:9000/api/data | jq '.region'

# 5. Check failover event
curl http://localhost:9000/lb/failovers | jq '.events[-1]'
```

### Scenario 2: Cascading Failures

```bash
# 1. Fail US-East
./scripts/demo.sh fail us-east

# 2. Wait for failover
sleep 15

# 3. Fail EU-West (now handling traffic)
./scripts/demo.sh fail eu-west

# 4. Verify AP-Southeast takes over
curl http://localhost:9000/api/data | jq '.region'

# 5. Recover all
./scripts/demo.sh recover us-east
./scripts/demo.sh recover eu-west
```

### Scenario 3: Performance Degradation

```bash
# 1. Add high latency to primary
./scripts/demo.sh latency us-east 5000

# 2. Monitor impact
watch -n 1 'curl -s http://localhost:9000/lb/status | jq ".regions[].latency_ms"'

# 3. Switch to least-latency strategy
curl http://localhost:9000/lb/strategy/least_latency

# 4. Verify routing to faster region
curl http://localhost:9000/api/data | jq '.region'
```

## Key Design Decisions

### 1. Active-Active vs Active-Passive

This demo uses **priority-based active-passive** routing where:
- Primary region handles all traffic when healthy
- Secondary regions are on standby for failover
- Enables manual traffic distribution via strategy changes

### 2. Health Check Strategy

Two-tier health checking:
- **Basic (`/health`)**: Quick response, minimal overhead
- **Deep (`/health/deep`)**: Full dependency verification

### 3. Failover Thresholds

Configurable thresholds balance:
- **Too sensitive**: False positive failovers
- **Too slow**: Extended downtime
- **Default (3 failures)**: ~15 second detection time

### 4. Database Strategy

Simulated async replication:
- Primary handles all writes
- Secondaries replicate with configurable lag
- Failover assumes replica promotion

## Production Considerations

When implementing this pattern in production:

1. **Use managed services**: AWS Route 53, Azure Traffic Manager, GCP Cloud Load Balancing
2. **Implement circuit breakers**: Prevent cascade failures
3. **Add rate limiting**: Protect against traffic spikes
4. **Use real databases**: With proper replication (PostgreSQL, MySQL, MongoDB)
5. **Implement proper secrets management**: Never hardcode credentials
6. **Add comprehensive logging**: Structured logs with correlation IDs
7. **Set up alerting**: PagerDuty, OpsGenie, or similar
8. **Regular DR testing**: Monthly failover drills

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Acknowledgments

This demo demonstrates concepts used in production systems at major cloud providers. The architecture patterns are based on real-world multi-region deployments.
