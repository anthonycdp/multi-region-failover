#!/usr/bin/env python3
"""
Health Monitor Service
Monitors all regional services and tracks their health status.
"""

import os
import time
import json
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
from collections import defaultdict
import statistics


class RegionHealth:
    """Tracks health metrics for a single region."""

    def __init__(self, name, endpoint):
        self.name = name
        self.endpoint = endpoint
        self.is_healthy = True
        self.last_check = None
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_checks = 0
        self.total_failures = 0
        self.latency_history = []
        self.last_error = None
        self.response_time_ms = 0

    def record_success(self, latency_ms):
        """Record a successful health check."""
        self.is_healthy = True
        self.last_check = datetime.now(timezone.utc)
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.total_checks += 1
        self.latency_history.append(latency_ms)
        self.last_error = None
        self.response_time_ms = latency_ms

        # Keep only last 100 latency samples
        if len(self.latency_history) > 100:
            self.latency_history = self.latency_history[-100:]

    def record_failure(self, error):
        """Record a failed health check."""
        self.is_healthy = False
        self.last_check = datetime.now(timezone.utc)
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.total_checks += 1
        self.total_failures += 1
        self.last_error = str(error)

    def get_availability(self):
        """Calculate availability percentage."""
        if self.total_checks == 0:
            return 100.0
        return ((self.total_checks - self.total_failures) / self.total_checks) * 100

    def get_avg_latency(self):
        """Get average latency from history."""
        if not self.latency_history:
            return 0
        return statistics.mean(self.latency_history)

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'endpoint': self.endpoint,
            'is_healthy': self.is_healthy,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'consecutive_failures': self.consecutive_failures,
            'consecutive_successes': self.consecutive_successes,
            'total_checks': self.total_checks,
            'total_failures': self.total_failures,
            'availability_pct': round(self.get_availability(), 2),
            'avg_latency_ms': round(self.get_avg_latency(), 2),
            'last_response_ms': round(self.response_time_ms, 2),
            'last_error': self.last_error
        }


class HealthMonitor:
    """Main health monitoring service."""

    def __init__(self):
        self.regions = {}
        self.failover_callback = None
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 5))
        self.failure_threshold = int(os.getenv('FAILURE_THRESHOLD', 3))
        self.recovery_threshold = int(os.getenv('RECOVERY_THRESHOLD', 2))
        self.timeout = int(os.getenv('CHECK_TIMEOUT', 5))
        self.running = False
        self.alerts = []
        self.max_alerts = 100
        self._lock = threading.Lock()

    def add_region(self, name, endpoint):
        """Add a region to monitor."""
        with self._lock:
            self.regions[name] = RegionHealth(name, endpoint)
        print(f"[Monitor] Added region: {name} ({endpoint})")

    def set_failover_callback(self, callback):
        """Set callback function for failover events."""
        self.failover_callback = callback

    def check_region(self, region):
        """Perform health check on a single region."""
        url = f"{region.endpoint}/health/deep"
        start_time = time.time()

        try:
            req = Request(url, headers={'User-Agent': 'HealthMonitor/1.0'})
            with urlopen(req, timeout=self.timeout) as response:
                latency_ms = (time.time() - start_time) * 1000
                data = json.loads(response.read().decode())

                if response.status == 200 and data.get('status') in ('healthy', 'degraded'):
                    region.record_success(latency_ms)
                    return True
                else:
                    region.record_failure(f"Unhealthy status: {data.get('status')}")
                    return False

        except URLError as e:
            latency_ms = (time.time() - start_time) * 1000
            region.record_failure(f"Connection error: {e.reason}")
            return False
        except json.JSONDecodeError as e:
            region.record_failure(f"Invalid JSON response: {e}")
            return False
        except Exception as e:
            region.record_failure(f"Unexpected error: {e}")
            return False

    def check_all_regions(self):
        """Check health of all regions."""
        results = {}

        for name, region in self.regions.items():
            was_healthy = region.is_healthy
            is_healthy = self.check_region(region)
            results[name] = is_healthy

            # Check for state transitions
            if was_healthy and not is_healthy:
                self._add_alert('WARNING', name,
                    f"Region {name} is now UNHEALTHY (failures: {region.consecutive_failures})")

                # Check if failover threshold reached
                if region.consecutive_failures >= self.failure_threshold:
                    self._trigger_failover(name)

            elif not was_healthy and is_healthy:
                self._add_alert('INFO', name,
                    f"Region {name} has RECOVERED (successes: {region.consecutive_successes})")

        return results

    def _add_alert(self, level, region, message):
        """Add an alert to the history."""
        alert = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': level,
            'region': region,
            'message': message
        }
        self.alerts.append(alert)

        # Keep only recent alerts
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]

        # Print to console
        print(f"[{level}] {alert['timestamp']} - {message}")

    def _trigger_failover(self, failed_region):
        """Trigger failover for a failed region."""
        self._add_alert('CRITICAL', failed_region,
            f"FAILOVER TRIGGERED for region {failed_region}")

        if self.failover_callback:
            self.failover_callback(failed_region)

    def start(self):
        """Start the monitoring loop."""
        self.running = True
        print(f"[Monitor] Starting health monitoring (interval: {self.check_interval}s)")
        print(f"[Monitor] Failure threshold: {self.failure_threshold} consecutive failures")
        print(f"[Monitor] Recovery threshold: {self.recovery_threshold} consecutive successes")

        def monitor_loop():
            while self.running:
                self.check_all_regions()
                time.sleep(self.check_interval)

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False

    def get_status(self):
        """Get overall monitoring status."""
        healthy_count = sum(1 for r in self.regions.values() if r.is_healthy)
        total_count = len(self.regions)

        return {
            'monitor_status': 'running' if self.running else 'stopped',
            'check_interval': self.check_interval,
            'failure_threshold': self.failure_threshold,
            'recovery_threshold': self.recovery_threshold,
            'healthy_regions': healthy_count,
            'total_regions': total_count,
            'overall_health': 'healthy' if healthy_count == total_count else 'degraded' if healthy_count > 0 else 'critical',
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'regions': {name: region.to_dict() for name, region in self.regions.items()},
            'recent_alerts': self.alerts[-10:] if self.alerts else []
        }


class MonitorHandler(BaseHTTPRequestHandler):
    """HTTP handler for monitor API."""

    monitor = None

    def log_message(self, format, *args):
        """Custom logging."""
        print(f"[Monitor API] {datetime.now().isoformat()} - {format % args}")

    def send_json_response(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/status':
            self.send_json_response(self.monitor.get_status())
        elif self.path == '/health':
            status = self.monitor.get_status()
            self.send_json_response({
                'status': 'healthy',
                'regions_monitored': status['total_regions'],
                'healthy_regions': status['healthy_regions']
            })
        elif self.path == '/alerts':
            self.send_json_response({
                'alerts': self.monitor.alerts[-50:],
                'total_alerts': len(self.monitor.alerts)
            })
        elif self.path.startswith('/region/'):
            region_name = self.path.split('/')[-1]
            if region_name in self.monitor.regions:
                self.send_json_response(self.monitor.regions[region_name].to_dict())
            else:
                self.send_error(404, 'Region not found')
        else:
            self.send_error(404, 'Not Found')


def main():
    """Start the health monitor service."""
    port = int(os.getenv('MONITOR_PORT', 8080))

    # Create monitor instance
    monitor = HealthMonitor()
    MonitorHandler.monitor = monitor

    # Configure regions from environment
    regions_config = os.getenv('REGIONS', '')
    if regions_config:
        # Format: "region1=http://host:port,region2=http://host:port"
        for region_def in regions_config.split(','):
            if '=' in region_def:
                name, endpoint = region_def.strip().split('=', 1)
                monitor.add_region(name, endpoint)
    else:
        # Default regions for demo
        monitor.add_region('us-east-1', 'http://us-east-service:8000')
        monitor.add_region('eu-west-1', 'http://eu-west-service:8000')
        monitor.add_region('ap-southeast-1', 'http://ap-southeast-service:8000')

    # Start monitoring
    monitor.start()

    # Start HTTP server
    server = HTTPServer(('0.0.0.0', port), MonitorHandler)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Health Monitor Service                                      ║
╠══════════════════════════════════════════════════════════════╣
║  Port: {port:<55} ║
║  Regions: {len(monitor.regions):<52} ║
║  Check Interval: {monitor.check_interval}s{' ' * (43 - len(str(monitor.check_interval)))} ║
╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Monitor] Shutting down...")
        monitor.stop()
        server.shutdown()


if __name__ == '__main__':
    main()
