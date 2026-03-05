# Disaster Recovery Plan

## Multi-Region Failover Demo

### Document Information

| Field | Value |
|-------|-------|
| **Document Version** | 1.0.0 |
| **Last Updated** | 2024 |
| **Classification** | Internal / Demo |
| **Review Frequency** | Quarterly |

---

## 1. Executive Summary

This document outlines the disaster recovery (DR) strategy for the Multi-Region Failover Demo system. The architecture is designed to provide high availability across multiple geographic regions with automatic failover capabilities.

### Key Objectives

- **RTO (Recovery Time Objective)**: < 30 seconds (automatic failover)
- **RPO (Recovery Point Objective)**: < 1 second (active-active replication)
- **Availability Target**: 99.99% (52.6 minutes downtime/year)

---

## 2. Architecture Overview

### 2.1 Regional Deployment

```
                    ┌─────────────────────────────────────┐
                    │        Global Load Balancer         │
                    │      (DNS-based + Health Checks)    │
                    └───────────────┬─────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │   US-EAST-1   │       │   EU-WEST-1   │       │ AP-SOUTHEAST-1│
    │   (Primary)   │       │  (Secondary)  │       │  (Secondary)  │
    │   Priority: 1 │       │   Priority: 2 │       │   Priority: 3 │
    └───────────────┘       └───────────────┘       └───────────────┘
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │    Database   │◄─────►│    Database   │◄─────►│    Database   │
    │   (Primary)   │       │  (Replica)    │       │  (Replica)    │
    └───────────────┘       └───────────────┘       └───────────────┘
            │
            └──────────────► Cross-Region Replication
```

### 2.2 Component Inventory

| Component | US-East-1 | EU-West-1 | AP-Southeast-1 |
|-----------|-----------|-----------|----------------|
| Application Server | ✓ Primary | ✓ Secondary | ✓ Secondary |
| Database | ✓ Primary | ✓ Read Replica | ✓ Read Replica |
| Health Monitor | - | - | ✓ Central |
| Load Balancer | - | - | ✓ Global |

---

## 3. Failure Scenarios and Response

### 3.1 Application Server Failure

**Detection:**
- Health check failures (3 consecutive failures)
- Latency threshold exceeded (> 5 seconds)

**Automatic Response:**
1. Health monitor detects failure
2. Load balancer marks region as unhealthy
3. Traffic automatically routed to next priority region
4. Alert triggered to operations team

**Manual Recovery:**
```bash
# Check region status
curl http://localhost:9000/lb/status

# If manual recovery needed
curl -X POST http://localhost:8001/admin/recover
```

### 3.2 Database Failure

**Detection:**
- Deep health check reveals database connectivity issues
- Replication lag exceeds threshold

**Automatic Response:**
1. Application health check fails
2. Region marked unhealthy
3. Failover to secondary region

**Manual Recovery:**
```bash
# Verify database status
curl http://localhost:8001/health/deep

# Promote replica to primary (if needed)
# This would typically involve:
# 1. Stop writes to failed primary
# 2. Promote replica
# 3. Update connection strings
# 4. Verify data consistency
```

### 3.3 Complete Region Outage

**Detection:**
- All services in region unreachable
- Health checks timing out

**Automatic Response:**
1. Load balancer detects complete outage
2. All traffic routed to remaining healthy regions
3. Failover event logged
4. Alerts sent to operations team

**Recovery Steps:**
1. Assess root cause of outage
2. Restore infrastructure
3. Verify data replication
4. Gradually reintroduce region to traffic pool

---

## 4. Failover Procedures

### 4.1 Automatic Failover

The system performs automatic failover when:
- 3 consecutive health check failures occur
- Region latency exceeds threshold for > 30 seconds
- Database connection pool exhausted

**Failover Flow:**
```
Primary Failure Detected
        │
        ▼
Health Checks Fail (x3)
        │
        ▼
Load Balancer Updates
        │
        ▼
Traffic Rerouted → Secondary Region
        │
        ▼
Failover Event Logged
        │
        ▼
Alerts Triggered
```

### 4.2 Manual Failover

Use manual failover for:
- Planned maintenance
- Performance degradation
- Security incidents

```bash
# Simulate failure to trigger failover
./scripts/demo.sh fail us-east

# Or via API
curl -X POST http://localhost:8001/admin/fail \
  -H "Content-Type: application/json" \
  -d '{"type": "general", "duration": 300}'

# Set region to maintenance mode
curl http://localhost:9000/lb/region/us-east-1/maintenance
```

### 4.3 Failback Procedure

When the primary region recovers:

```bash
# Verify region health
curl http://localhost:8001/health/deep

# Check replication lag
curl http://localhost:8001/metrics | grep replication_lag

# Reactivate region
curl http://localhost:9000/lb/region/us-east-1/activate

# Monitor traffic distribution
curl http://localhost:9000/lb/status
```

---

## 5. Monitoring and Alerting

### 5.1 Health Check Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Application | `/health` | Basic health status |
| Application | `/health/deep` | Full dependency check |
| Application | `/metrics` | Prometheus metrics |
| Load Balancer | `/lb/status` | All regions status |
| Load Balancer | `/lb/failovers` | Failover history |
| Health Monitor | `/status` | Monitoring status |
| Health Monitor | `/alerts` | Recent alerts |

### 5.2 Key Metrics to Monitor

```bash
# Get all metrics
curl http://localhost:9000/lb/status | jq '.regions'

# Monitor specific metrics
curl http://localhost:8001/metrics | grep -E "service_(healthy|latency|requests)"
```

**Critical Metrics:**
- `service_healthy` - Binary health status
- `service_latency_ms` - Response latency
- `service_replication_lag_ms` - Database replication delay
- `service_requests_total` - Request count

### 5.3 Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Health Check Failures | 2 | 3+ |
| Latency (p99) | > 500ms | > 2000ms |
| Replication Lag | > 1000ms | > 5000ms |
| CPU Usage | > 70% | > 90% |
| Memory Usage | > 80% | > 95% |

---

## 6. Testing Procedures

### 6.1 Failover Testing (Monthly)

```bash
# 1. Start the demo
./scripts/demo.sh start

# 2. Verify all regions healthy
./scripts/demo.sh status

# 3. Simulate primary failure
./scripts/demo.sh fail us-east

# 4. Verify failover (check dashboard)
# Dashboard: http://localhost:3000

# 5. Verify traffic routing
curl http://localhost:9000/api/data

# 6. Recover primary
./scripts/demo.sh recover us-east

# 7. Verify failback
./scripts/demo.sh metrics
```

### 6.2 Load Testing

```bash
# Run load test
./scripts/demo.sh load 1000

# Monitor during load
watch -n 1 './scripts/demo.sh metrics'
```

### 6.3 Chaos Engineering

```bash
# Add latency
./scripts/demo.sh latency us-east 2000

# Simulate database failure
curl -X POST http://localhost:8001/admin/fail \
  -H "Content-Type: application/json" \
  -d '{"type": "database", "duration": 60}'
```

---

## 7. Recovery Time Objectives

| Scenario | RTO | RPO | Notes |
|----------|-----|-----|-------|
| Single Server Failure | < 30s | 0 | Automatic |
| Database Failure | < 60s | < 1s | Automatic with replica promotion |
| Region Outage | < 30s | < 1s | Automatic traffic reroute |
| Multi-Region Outage | N/A | Varies | Requires manual intervention |

---

## 8. Contact Information

### Escalation Path

1. **Level 1**: On-call Engineer (response: 5 min)
2. **Level 2**: Senior Engineer (response: 15 min)
3. **Level 3**: Engineering Manager (response: 30 min)
4. **Level 4**: VP Engineering (response: 1 hour)

### Communication Channels

- **Slack**: #incidents-multi-region
- **PagerDuty**: Multi-Region Service
- **Email**: oncall@example.com

---

## 9. Post-Incident Procedures

### 9.1 Immediate Actions

1. Verify failover completed successfully
2. Assess impact on users
3. Notify stakeholders
4. Begin root cause analysis

### 9.2 Post-Mortem Template

```markdown
# Incident Report: [Date]

## Summary
- Duration: [Start] - [End]
- Impact: [Number] users affected
- Root Cause: [Description]

## Timeline
- [Time] Issue detected
- [Time] Failover initiated
- [Time] Service restored

## Action Items
1. [ ] [Action item]
2. [ ] [Action item]

## Lessons Learned
- [What went well]
- [What could be improved]
```

---

## 10. Appendices

### A. Useful Commands

```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs -f load-balancer
docker-compose logs -f health-monitor

# Restart specific service
docker-compose restart us-east-service

# Full reset
docker-compose down -v && docker-compose up -d --build
```

### B. Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CHECK_INTERVAL` | 5 | Health check interval (seconds) |
| `FAILURE_THRESHOLD` | 3 | Failures before failover |
| `RECOVERY_THRESHOLD` | 2 | Successes before recovery |
| `REQUEST_TIMEOUT` | 10 | Request timeout (seconds) |
| `HEALTH_CHECK_INTERVAL` | 5 | LB health check interval |

### C. Architecture Decisions

1. **Active-Active vs Active-Passive**: Chose priority-based routing for gradual traffic shift
2. **Database Strategy**: Primary-replica with async replication
3. **Health Check Strategy**: Two-tier (basic + deep) for efficiency
4. **Load Balancing**: Priority-based with manual override capability
