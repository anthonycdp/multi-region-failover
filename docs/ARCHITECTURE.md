# Architecture Diagrams

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    INTERNET / CLIENTS                                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│   │                           GLOBAL LOAD BALANCER                                            │  │
│   │                              (Port 9000)                                                  │  │
│   │                                                                                            │  │
│   │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │  │
│   │   │  Health Checks  │  │  LB Strategies  │  │  Failover Logic │  │  Metrics & Logging  │  │  │
│   │   │  (5s interval)  │  │  • Priority     │  │  • Threshold: 3 │  │  • Request count    │  │  │
│   │   │                 │  │  • Weighted     │  │  • Auto-recover │  │  • Failover events  │  │  │
│   │   │                 │  │  • Round-robin  │  │  • Alerting     │  │  • Latency tracking │  │  │
│   │   │                 │  │  • Least-latency│  │                 │  │                     │  │  │
│   │   └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │  │
│   │                                                                                            │  │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐  ┌─────────────────────────────┐
│                             │  │                             │  │                             │
│        US-EAST-1            │  │        EU-WEST-1            │  │     AP-SOUTHEAST-1          │
│        (PRIMARY)            │  │        (SECONDARY)          │  │        (SECONDARY)          │
│                             │  │                             │  │                             │
│   ┌───────────────────┐     │  │   ┌───────────────────┐     │  │   ┌───────────────────┐     │
│   │  Application      │     │  │   │  Application      │     │  │   │  Application      │     │
│   │  Server           │     │  │   │  Server           │     │  │   │  Server           │     │
│   │  (Port 8000)      │     │  │   │  (Port 8000)      │     │  │   │  (Port 8000)      │     │
│   │                   │     │  │   │                   │     │  │   │                   │     │
│   │  /health          │     │  │   │  /health          │     │  │   │  /health          │     │
│   │  /health/deep     │     │  │   │  /health/deep     │     │  │   │  /health/deep     │     │
│   │  /metrics         │     │  │   │  /metrics         │     │  │   │  /metrics         │     │
│   │  /api/data        │     │  │   │  /api/data        │     │  │   │  /api/data        │     │
│   └───────────────────┘     │  │   └───────────────────┘     │  │   └───────────────────┘     │
│            │                │  │            │                │  │            │                │
│            ▼                │  │            ▼                │  │            ▼                │
│   ┌───────────────────┐     │  │   ┌───────────────────┐     │  │   ┌───────────────────┐     │
│   │  Database         │     │  │   │  Database         │     │  │   │  Database         │     │
│   │  (PRIMARY)        │◄────┼──┼───│  (READ REPLICA)   │     │  │   │  (READ REPLICA)   │     │
│   │                   │     │  │   │                   │     │  │   │                   │     │
│   │  • Writes         │     │  │   │  • Reads          │     │  │   │  • Reads          │     │
│   │  • Reads          │     │  │   │  • Async repl     │     │  │   │  • Async repl     │     │
│   └───────────────────┘     │  │   └───────────────────┘     │  │   └───────────────────┘     │
│                             │  │                             │  │                             │
│   Priority: 1               │  │   Priority: 2               │  │   Priority: 3               │
│   Weight: 100               │  │   Weight: 80                │  │   Weight: 60                │
│   Host: us-east-service     │  │   Host: eu-west-service     │  │   Host: ap-southeast-service│
│   Exposed Port: 8001        │  │   Exposed Port: 8002        │  │   Exposed Port: 8003        │
│                             │  │                             │  │                             │
└─────────────────────────────┘  └─────────────────────────────┘  └─────────────────────────────┘

                    ┌──────────────────────────────────────────────────────────────┐
                    │                                                               │
                    │   ┌─────────────────────────────────────────────────────┐    │
                    │   │              HEALTH MONITOR                         │    │
                    │   │                (Port 8080)                          │    │
                    │   │                                                     │    │
                    │   │   • Polls all regions every 5 seconds              │    │
                    │   │   • Tracks consecutive failures/successes          │    │
                    │   │   • Calculates availability percentages            │    │
                    │   │   • Generates alerts on state changes              │    │
                    │   │                                                     │    │
                    │   └─────────────────────────────────────────────────────┘    │
                    │                                                               │
                    │   ┌─────────────────────────────────────────────────────┐    │
                    │   │              DASHBOARD UI                           │    │
                    │   │                (Port 3000)                          │    │
                    │   │                                                     │    │
                    │   │   • Real-time region health visualization          │    │
                    │   │   • Failover simulation controls                   │    │
                    │   │   • Alert history display                          │    │
                    │   │   • Latency and request metrics                    │    │
                    │   │                                                     │    │
                    │   └─────────────────────────────────────────────────────┘    │
                    │                                                               │
                    └──────────────────────────────────────────────────────────────┘
```

## Failover Flow

```
                         NORMAL OPERATION
                         ================

    Client ──────► Load Balancer ──────► US-EAST-1 (Primary)
                   (Priority LB)
                         │
                         ├──► EU-WEST-1 (Standby)
                         │
                         └──► AP-SOUTHEAST-1 (Standby)


                         FAILURE DETECTED
                         ================

    US-EAST-1 ────► Health Check Fails (x1)
                      │
                      ▼
    US-EAST-1 ────► Health Check Fails (x2)
                      │
                      ▼
    US-EAST-1 ────► Health Check Fails (x3) ◄── FAILURE THRESHOLD
                      │
                      ▼
    Load Balancer ──► Marks US-EAST-1 Unhealthy
                      │
                      ▼
    Load Balancer ──► Triggers Failover
                      │
                      ▼
                      └──► Log Failover Event
                      └──► Send Alert


                         FAILOVER ACTIVE
                         ===============

    Client ──────► Load Balancer ──────► EU-WEST-1 (New Primary)
                   (Priority LB)
                         │
                         ├──► US-EAST-1 (Unhealthy)
                         │
                         └──► AP-SOUTHEAST-1 (Backup)


                         RECOVERY
                         ========

    US-EAST-1 ────► Health Check Passes (x1)
                      │
                      ▼
    US-EAST-1 ────► Health Check Passes (x2) ◄── RECOVERY THRESHOLD
                      │
                      ▼
    Load Balancer ──► Marks US-EAST-1 Healthy
                      │
                      ▼
    Load Balancer ──► Traffic resumes to US-EAST-1
```

## Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           WRITE PATH                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   Client ──► Load Balancer ──► US-EAST-1 (Primary)                       │
│                                    │                                      │
│                                    ▼                                      │
│                              Primary DB                                   │
│                                    │                                      │
│                    ┌───────────────┼───────────────┐                      │
│                    │               │               │                      │
│                    ▼               ▼               ▼                      │
│              Async Replication (Wal Shipping / CDC)                       │
│                    │               │               │                      │
│                    ▼               ▼               ▼                      │
│              EU-West DB    AP-Southeast DB                               │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                           READ PATH                                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   Client ──► Load Balancer ──► [Nearest Healthy Region]                  │
│                                    │                                      │
│                                    ▼                                      │
│                              Local DB Read                                │
│                                    │                                      │
│                                    ▼                                      │
│                              Response                                     │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Network Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Docker Network: multi-region-net                 │
│                           Subnet: 172.28.0.0/16                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌────────────────┐                                                    │
│   │ load-balancer  │  172.28.0.10                                       │
│   │ Port: 9000     │                                                    │
│   └───────┬────────┘                                                    │
│           │                                                              │
│   ┌───────┴────────┐                                                    │
│   │ health-monitor │  172.28.0.11                                       │
│   │ Port: 8080     │                                                    │
│   └───────┬────────┘                                                    │
│           │                                                              │
│   ┌───────┴────────┐                                                    │
│   │   dashboard    │  172.28.0.12                                       │
│   │ Port: 3000     │                                                    │
│   └───────┬────────┘                                                    │
│           │                                                              │
│   ┌───────┴────────┐  ┌────────────────┐  ┌────────────────┐           │
│   │ us-east-service│  │ eu-west-service│  │ap-southeast-svc│           │
│   │ 172.28.0.20    │  │ 172.28.0.21    │  │ 172.28.0.22    │           │
│   │ Port: 8000     │  │ Port: 8000     │  │ Port: 8000     │           │
│   └────────────────┘  └────────────────┘  └────────────────┘           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Health Check Sequence

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Health        │     │ Regional      │     │ Database      │
│ Monitor       │     │ Service       │     │               │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        │ GET /health/deep    │                     │
        │────────────────────►│                     │
        │                     │                     │
        │                     │ Check DB Connection │
        │                     │────────────────────►│
        │                     │                     │
        │                     │ Connection OK       │
        │                     │◄────────────────────│
        │                     │                     │
        │ 200 OK + Health     │                     │
        │◄────────────────────│                     │
        │                     │                     │
        │ Record latency      │                     │
        │ Update status       │                     │
        │                     │                     │
        ▼                     ▼                     ▼
```
