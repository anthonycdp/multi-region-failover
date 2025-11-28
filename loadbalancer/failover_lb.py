#!/usr/bin/env python3
"""
Global Load Balancer with Automatic Failover
Routes traffic to healthy regions and handles automatic failover.
"""

import os
import time
import json
import threading
import random
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import hashlib


class RegionStatus(Enum):
    """Status of a region."""
    ACTIVE = "active"           # Receiving traffic
    FAILOVER = "failover"       # Temporarily not receiving traffic
    DRAINING = "draining"       # Being drained of connections
    MAINTENANCE = "maintenance"  # Manually taken offline


@dataclass
class Region:
    """Represents a deployment region."""
    name: str
    endpoint: str
    priority: int = 1           # Lower = higher priority
    weight: int = 100           # For weighted load balancing
    status: RegionStatus = RegionStatus.ACTIVE
    is_healthy: bool = True
    latency_ms: float = 0
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0

    @property
    def is_available(self) -> bool:
        """Check if region can receive traffic."""
        return self.status == RegionStatus.ACTIVE and self.is_healthy


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_LATENCY = "least_latency"
    PRIORITY = "priority"
    GEOGRAPHIC = "geographic"


class FailoverEvent:
    """Records a failover event."""

    def __init__(self, from_region: str, to_region: str, reason: str):
        self.timestamp = datetime.now(timezone.utc)
        self.from_region = from_region
        self.to_region = to_region
        self.reason = reason
        self.recovered = False
        self.recovery_time = None


class GlobalLoadBalancer:
    """Global load balancer with failover capabilities."""

    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.strategy = LoadBalancingStrategy.PRIORITY
        self.health_check_interval = int(os.getenv('HEALTH_CHECK_INTERVAL', 5))
        self.failure_threshold = int(os.getenv('FAILURE_THRESHOLD', 3))
        self.recovery_threshold = int(os.getenv('RECOVERY_THRESHOLD', 2))
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', 10))

        # State tracking
        self._round_robin_index = 0
        self._lock = threading.Lock()
        self.running = False

        # Failover tracking
        self.failover_events: List[FailoverEvent] = []
        self.active_failover = False
        self.primary_region = None
        self.fallback_region = None

        # Metrics
        self.total_requests = 0
        self.total_failovers = 0
        self.start_time = datetime.now(timezone.utc)

    def add_region(self, name: str, endpoint: str, priority: int = 1, weight: int = 100, is_primary: bool = False):
        """Add a region to the load balancer."""
        with self._lock:
            self.regions[name] = Region(
                name=name,
                endpoint=endpoint,
                priority=priority,
                weight=weight
            )
            if is_primary:
                self.primary_region = name
            # First added region becomes fallback if not set
            if self.fallback_region is None and not is_primary:
                self.fallback_region = name

        print(f"[LB] Added region: {name} (priority={priority}, weight={weight}, primary={is_primary})")

    def set_strategy(self, strategy: LoadBalancingStrategy):
        """Set the load balancing strategy."""
        self.strategy = strategy
        print(f"[LB] Strategy changed to: {strategy.value}")

    def get_available_regions(self) -> List[Region]:
        """Get list of available regions."""
        return [r for r in self.regions.values() if r.is_available]

    def select_region(self, client_ip: str = None) -> Optional[Region]:
        """Select a region based on the current strategy."""
        available = self.get_available_regions()

        if not available:
            return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED:
            return self._select_weighted(available)
        elif self.strategy == LoadBalancingStrategy.LEAST_LATENCY:
            return self._select_least_latency(available)
        elif self.strategy == LoadBalancingStrategy.PRIORITY:
            return self._select_priority(available)
        elif self.strategy == LoadBalancingStrategy.GEOGRAPHIC:
            return self._select_geographic(available, client_ip)
        else:
            return available[0]

    def _select_round_robin(self, regions: List[Region]) -> Region:
        """Round-robin selection."""
        with self._lock:
            region = regions[self._round_robin_index % len(regions)]
            self._round_robin_index += 1
            return region

    def _select_weighted(self, regions: List[Region]) -> Region:
        """Weighted random selection."""
        total_weight = sum(r.weight for r in regions)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for region in regions:
            cumulative += region.weight
            if r <= cumulative:
                return region
        return regions[-1]

    def _select_least_latency(self, regions: List[Region]) -> Region:
        """Select region with lowest latency."""
        return min(regions, key=lambda r: r.latency_ms)

    def _select_priority(self, regions: List[Region]) -> Region:
        """Select highest priority (lowest number) region."""
        return min(regions, key=lambda r: r.priority)

    def _select_geographic(self, regions: List[Region], client_ip: str) -> Region:
        """Select region based on client geography (simulated)."""
        if client_ip:
            # Simple hash-based geographic routing simulation
            hash_val = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
            idx = hash_val % len(regions)
            return list(regions)[idx]
        return self._select_priority(regions)

    def check_region_health(self, region: Region) -> bool:
        """Check health of a single region."""
        url = f"{region.endpoint}/health"
        start_time = time.time()

        try:
            req = Request(url, headers={'User-Agent': 'GlobalLB/1.0'})
            with urlopen(req, timeout=5) as response:
                latency = (time.time() - start_time) * 1000
                data = json.loads(response.read().decode())

                region.latency_ms = latency
                region.last_check = datetime.now(timezone.utc)

                if response.status == 200 and data.get('status') == 'healthy':
                    region.consecutive_failures = 0
                    if not region.is_healthy:
                        self._handle_recovery(region)
                    region.is_healthy = True
                    return True
                else:
                    region.consecutive_failures += 1
                    if region.consecutive_failures >= self.failure_threshold:
                        self._handle_failure(region)
                    return False

        except Exception as e:
            region.consecutive_failures += 1
            region.latency_ms = (time.time() - start_time) * 1000
            region.last_check = datetime.now(timezone.utc)
            print(f"[LB] Health check failed for {region.name}: {e}")

            if region.consecutive_failures >= self.failure_threshold:
                self._handle_failure(region)
            return False

    def _handle_failure(self, region: Region):
        """Handle region failure."""
        if region.is_healthy:
            region.is_healthy = False
            region.status = RegionStatus.FAILOVER

            # Find failover target
            available = self.get_available_regions()
            if available:
                target = self._select_priority(available)
                event = FailoverEvent(
                    from_region=region.name,
                    to_region=target.name,
                    reason=f"Health check failures: {region.consecutive_failures}"
                )
                self.failover_events.append(event)
                self.total_failovers += 1
                self.active_failover = True

                print(f"[LB] FAILOVER: {region.name} -> {target.name}")

    def _handle_recovery(self, region: Region):
        """Handle region recovery."""
        region.is_healthy = True
        region.status = RegionStatus.ACTIVE

        # Update failover event if applicable
        for event in reversed(self.failover_events):
            if event.from_region == region.name and not event.recovered:
                event.recovered = True
                event.recovery_time = datetime.now(timezone.utc)
                break

        # Check if all regions are healthy
        if all(r.is_healthy for r in self.regions.values()):
            self.active_failover = False

        print(f"[LB] RECOVERY: {region.name} is back online")

    def health_check_loop(self):
        """Continuous health check loop."""
        while self.running:
            for region in list(self.regions.values()):
                self.check_region_health(region)
            time.sleep(self.health_check_interval)

    def start(self):
        """Start the load balancer."""
        self.running = True
        thread = threading.Thread(target=self.health_check_loop, daemon=True)
        thread.start()
        print("[LB] Health check loop started")

    def stop(self):
        """Stop the load balancer."""
        self.running = False

    def proxy_request(self, path: str, method: str = 'GET', body: bytes = None, headers: dict = None, client_ip: str = None) -> tuple:
        """Proxy a request to a selected region."""
        region = self.select_region(client_ip)

        if not region:
            return None, {'error': 'No available regions'}

        url = f"{region.endpoint}{path}"
        req_headers = headers or {}
        req_headers['X-Forwarded-For'] = client_ip or 'unknown'
        req_headers['X-LB-Region'] = region.name

        try:
            req = Request(url, data=body, headers=req_headers, method=method)
            with urlopen(req, timeout=self.timeout) as response:
                body = response.read()
                region.total_requests += 1
                self.total_requests += 1
                return {
                    'status': response.status,
                    'headers': dict(response.headers),
                    'body': body.decode()
                }, None
        except URLError as e:
            region.failed_requests += 1
            region.consecutive_failures += 1
            return None, {'error': str(e), 'region': region.name}
        except Exception as e:
            region.failed_requests += 1
            return None, {'error': str(e), 'region': region.name}

    def get_status(self) -> dict:
        """Get load balancer status."""
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        return {
            'status': 'active',
            'uptime_seconds': int(uptime),
            'strategy': self.strategy.value,
            'total_requests': self.total_requests,
            'total_failovers': self.total_failovers,
            'active_failover': self.active_failover,
            'primary_region': self.primary_region,
            'healthy_regions': sum(1 for r in self.regions.values() if r.is_healthy),
            'total_regions': len(self.regions),
            'regions': {
                name: {
                    'endpoint': r.endpoint,
                    'priority': r.priority,
                    'weight': r.weight,
                    'status': r.status.value,
                    'is_healthy': r.is_healthy,
                    'is_available': r.is_available,
                    'latency_ms': round(r.latency_ms, 2),
                    'last_check': r.last_check.isoformat() if r.last_check else None,
                    'total_requests': r.total_requests,
                    'failed_requests': r.failed_requests,
                    'consecutive_failures': r.consecutive_failures
                }
                for name, r in self.regions.items()
            },
            'recent_failovers': [
                {
                    'timestamp': e.timestamp.isoformat(),
                    'from_region': e.from_region,
                    'to_region': e.to_region,
                    'reason': e.reason,
                    'recovered': e.recovered,
                    'recovery_time': e.recovery_time.isoformat() if e.recovery_time else None
                }
                for e in self.failover_events[-10:]
            ]
        }

    def set_region_status(self, name: str, status: RegionStatus):
        """Manually set region status (for maintenance mode)."""
        if name in self.regions:
            self.regions[name].status = status
            print(f"[LB] Region {name} status set to: {status.value}")
            return True
        return False


class LoadBalancerHandler(BaseHTTPRequestHandler):
    """HTTP handler for the load balancer."""

    lb: GlobalLoadBalancer = None

    def log_message(self, format, *args):
        """Custom logging."""
        print(f"[LB] {datetime.now().isoformat()} - {format % args}")

    def send_json_response(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('X-Served-By', 'GlobalLoadBalancer')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def get_client_ip(self) -> str:
        """Get client IP address."""
        return self.client_address[0]

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/lb/status':
            self.send_json_response(self.lb.get_status())
        elif self.path == '/lb/health':
            self.send_json_response({
                'status': 'healthy',
                'regions': len(self.lb.regions),
                'healthy': self.lb.get_status()['healthy_regions']
            })
        elif self.path == '/lb/failovers':
            self.send_json_response({
                'total_failovers': self.lb.total_failovers,
                'active_failover': self.lb.active_failover,
                'events': self.lb.get_status()['recent_failovers']
            })
        elif self.path.startswith('/lb/strategy/'):
            strategy_name = self.path.split('/')[-1]
            try:
                strategy = LoadBalancingStrategy(strategy_name)
                self.lb.set_strategy(strategy)
                self.send_json_response({'message': f'Strategy set to {strategy_name}'})
            except ValueError:
                self.send_error(400, f'Invalid strategy: {strategy_name}')
        elif self.path.startswith('/lb/region/'):
            parts = self.path.split('/')
            if len(parts) >= 4:
                region_name = parts[3]
                action = parts[4] if len(parts) > 4 else None

                if action == 'maintenance':
                    self.lb.set_region_status(region_name, RegionStatus.MAINTENANCE)
                    self.send_json_response({'message': f'{region_name} in maintenance'})
                elif action == 'activate':
                    self.lb.set_region_status(region_name, RegionStatus.ACTIVE)
                    self.send_json_response({'message': f'{region_name} activated'})
                else:
                    if region_name in self.lb.regions:
                        self.send_json_response(self.lb.get_status()['regions'][region_name])
                    else:
                        self.send_error(404, 'Region not found')
            else:
                self.send_error(400, 'Invalid path')
        else:
            # Proxy to backend
            response, error = self.lb.proxy_request(
                self.path,
                client_ip=self.get_client_ip()
            )
            if error:
                self.send_json_response(error, status=503)
            else:
                self.send_response(response['status'])
                self.send_header('Content-Type', 'application/json')
                for key, value in response['headers'].items():
                    if key.lower() not in ('transfer-encoding', 'connection'):
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response['body'].encode())

    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Proxy to backend
        response, error = self.lb.proxy_request(
            self.path,
            method='POST',
            body=body,
            headers=dict(self.headers),
            client_ip=self.get_client_ip()
        )
        if error:
            self.send_json_response(error, status=503)
        else:
            self.send_response(response['status'])
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response['body'].encode())


def main():
    """Start the global load balancer."""
    port = int(os.getenv('LB_PORT', 9000))

    # Create load balancer
    lb = GlobalLoadBalancer()
    LoadBalancerHandler.lb = lb

    # Configure regions from environment
    # Format: "name=endpoint:priority:weight:is_primary,..."
    regions_config = os.getenv('REGIONS', '')

    if regions_config:
        for region_def in regions_config.split(','):
            parts = region_def.strip().split(':')
            if len(parts) >= 2:
                name_endpoint = parts[0].split('=')
                name = name_endpoint[0]
                endpoint = name_endpoint[1] if len(name_endpoint) > 1 else parts[1]
                priority = int(parts[2]) if len(parts) > 2 else 1
                weight = int(parts[3]) if len(parts) > 3 else 100
                is_primary = parts[4].lower() == 'true' if len(parts) > 4 else False
                lb.add_region(name, endpoint, priority, weight, is_primary)
    else:
        # Default regions for demo
        lb.add_region('us-east-1', 'http://us-east-service:8000', priority=1, weight=100, is_primary=True)
        lb.add_region('eu-west-1', 'http://eu-west-service:8000', priority=2, weight=80)
        lb.add_region('ap-southeast-1', 'http://ap-southeast-service:8000', priority=3, weight=60)

    # Start load balancer
    lb.start()

    # Start HTTP server
    server = HTTPServer(('0.0.0.0', port), LoadBalancerHandler)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Global Load Balancer with Failover                          ║
╠══════════════════════════════════════════════════════════════╣
║  Port: {port:<55} ║
║  Strategy: {lb.strategy.value:<50} ║
║  Regions: {len(lb.regions):<52} ║
║  Primary: {lb.primary_region or 'N/A':<52} ║
╠══════════════════════════════════════════════════════════════╣
║  Endpoints:                                                  ║
║    /lb/status       - LB status and metrics                  ║
║    /lb/failovers    - Failover history                       ║
║    /lb/health       - LB health check                        ║
║    /lb/strategy/X   - Change strategy                        ║
║    /lb/region/X     - Region details                         ║
║    /lb/region/X/maintenance - Set region to maintenance      ║
║    /lb/region/X/activate    - Activate region                ║
║    /*               - Proxied to backend regions             ║
╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LB] Shutting down...")
        lb.stop()
        server.shutdown()


if __name__ == '__main__':
    main()
