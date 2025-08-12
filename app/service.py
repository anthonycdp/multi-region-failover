#!/usr/bin/env python3
"""
Multi-Region Service Application
Simulates a regional service instance with health endpoints and metrics.
"""

import os
import time
import json
import random
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

# Configuration from environment
REGION = os.getenv('REGION', 'us-east-1')
PORT = int(os.getenv('PORT', 8000))
PRIMARY = os.getenv('PRIMARY', 'true').lower() == 'true'
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# Simulated service state
service_state = {
    'healthy': True,
    'requests_served': 0,
    'start_time': datetime.now(timezone.utc).isoformat(),
    'db_connected': True,
    'latency_ms': 50,
    'cpu_usage': 25.0,
    'memory_usage': 40.0,
    'replication_lag': 0
}


class ServiceHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the regional service."""

    def log_message(self, format, *args):
        """Custom logging with region prefix."""
        print(f"[{REGION}] {datetime.now().isoformat()} - {format % args}")

    def send_json_response(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('X-Region', REGION)
        self.send_header('X-Server-Time', datetime.now(timezone.utc).isoformat())
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        """Handle GET requests."""
        service_state['requests_served'] += 1

        if self.path == '/health':
            self.handle_health()
        elif self.path == '/health/deep':
            self.handle_deep_health()
        elif self.path == '/metrics':
            self.handle_metrics()
        elif self.path == '/status':
            self.handle_status()
        elif self.path == '/api/data':
            self.handle_api_data()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/admin/fail':
            self.handle_simulate_failure()
        elif self.path == '/admin/recover':
            self.handle_simulate_recovery()
        elif self.path == '/admin/latency':
            self.handle_simulate_latency()
        else:
            self.send_error(404, 'Not Found')

    def handle_health(self):
        """Basic health check endpoint."""
        if service_state['healthy']:
            self.send_json_response({
                'status': 'healthy',
                'region': REGION,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        else:
            self.send_json_response({
                'status': 'unhealthy',
                'region': REGION,
                'reason': 'simulated_failure',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, status=503)

    def handle_deep_health(self):
        """Deep health check with all dependencies."""
        checks = {
            'server': service_state['healthy'],
            'database': service_state['db_connected'],
            'replication': service_state['replication_lag'] < 5000
        }

        all_healthy = all(checks.values())

        response = {
            'status': 'healthy' if all_healthy else 'degraded',
            'region': REGION,
            'primary': PRIMARY,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': {
                'server': {'status': 'pass' if checks['server'] else 'fail'},
                'database': {
                    'status': 'pass' if checks['database'] else 'fail',
                    'host': DB_HOST,
                    'port': DB_PORT
                },
                'replication': {
                    'status': 'pass' if checks['replication'] else 'warning',
                    'lag_ms': service_state['replication_lag']
                }
            },
            'metrics': {
                'requests_served': service_state['requests_served'],
                'uptime_seconds': self._get_uptime(),
                'latency_ms': service_state['latency_ms'],
                'cpu_usage': service_state['cpu_usage'],
                'memory_usage': service_state['memory_usage']
            }
        }

        self.send_json_response(response, status=200 if all_healthy else 503)

    def handle_metrics(self):
        """Prometheus-style metrics endpoint."""
        metrics = f"""# HELP service_requests_total Total requests served
# TYPE service_requests_total counter
service_requests_total{{region="{REGION}"}} {service_state['requests_served']}

# HELP service_healthy Whether the service is healthy
# TYPE service_healthy gauge
service_healthy{{region="{REGION}"}} {1 if service_state['healthy'] else 0}

# HELP service_latency_ms Request latency in milliseconds
# TYPE service_latency_ms gauge
service_latency_ms{{region="{REGION}"}} {service_state['latency_ms']}

# HELP service_cpu_usage CPU usage percentage
# TYPE service_cpu_usage gauge
service_cpu_usage{{region="{REGION}"}} {service_state['cpu_usage']}

# HELP service_memory_usage Memory usage percentage
# TYPE service_memory_usage gauge
service_memory_usage{{region="{REGION}"}} {service_state['memory_usage']}

# HELP service_replication_lag_ms Database replication lag
# TYPE service_replication_lag_ms gauge
service_replication_lag_ms{{region="{REGION}"}} {service_state['replication_lag']}

# HELP service_primary Whether this instance is primary
# TYPE service_primary gauge
service_primary{{region="{REGION}"}} {1 if PRIMARY else 0}
"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(metrics.encode())

    def handle_status(self):
        """Detailed service status."""
        response = {
            'service': 'multi-region-demo',
            'version': '1.0.0',
            'region': REGION,
            'role': 'primary' if PRIMARY else 'secondary',
            'state': {
                'healthy': service_state['healthy'],
                'start_time': service_state['start_time'],
                'uptime_seconds': self._get_uptime(),
                'requests_served': service_state['requests_served']
            },
            'configuration': {
                'port': PORT,
                'database': f'{DB_HOST}:{DB_PORT}'
            },
            'performance': {
                'latency_ms': service_state['latency_ms'],
                'cpu_usage': service_state['cpu_usage'],
                'memory_usage': service_state['memory_usage']
            }
        }
        self.send_json_response(response)

    def handle_api_data(self):
        """Sample API endpoint returning data."""
        if not service_state['healthy']:
            self.send_json_response({
                'error': 'Service unavailable',
                'region': REGION
            }, status=503)
            return

        # Simulate some processing latency
        time.sleep(service_state['latency_ms'] / 1000)

        self.send_json_response({
            'data': {
                'id': random.randint(1, 1000),
                'name': f'sample-data-{REGION}',
                'value': random.random() * 100,
                'created_at': datetime.now(timezone.utc).isoformat()
            },
            'region': REGION,
            'served_by': 'primary' if PRIMARY else 'secondary'
        })

    def handle_simulate_failure(self):
        """Admin endpoint to simulate failure."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        failure_type = body.get('type', 'general')
        duration = body.get('duration', 60)

        service_state['healthy'] = False
        if failure_type == 'database':
            service_state['db_connected'] = False
        elif failure_type == 'latency':
            service_state['latency_ms'] = body.get('latency_ms', 2000)

        print(f"[{REGION}] SIMULATED FAILURE: {failure_type} for {duration}s")

        # Schedule recovery
        def recover():
            time.sleep(duration)
            service_state['healthy'] = True
            service_state['db_connected'] = True
            service_state['latency_ms'] = 50
            print(f"[{REGION}] RECOVERED from simulated failure")

        threading.Thread(target=recover, daemon=True).start()

        self.send_json_response({
            'message': f'Failure simulated: {failure_type}',
            'duration': duration,
            'region': REGION
        })

    def handle_simulate_recovery(self):
        """Admin endpoint to recover from simulated failure."""
        service_state['healthy'] = True
        service_state['db_connected'] = True
        service_state['latency_ms'] = 50

        print(f"[{REGION}] MANUAL RECOVERY triggered")

        self.send_json_response({
            'message': 'Service recovered',
            'region': REGION
        })

    def handle_simulate_latency(self):
        """Admin endpoint to simulate latency."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        latency = body.get('latency_ms', 500)
        service_state['latency_ms'] = latency

        self.send_json_response({
            'message': f'Latency set to {latency}ms',
            'region': REGION
        })

    def _get_uptime(self):
        """Calculate uptime in seconds."""
        start = datetime.fromisoformat(service_state['start_time'].replace('Z', '+00:00'))
        return int((datetime.now(timezone.utc) - start).total_seconds())


def simulate_load():
    """Background thread to simulate varying load."""
    while True:
        time.sleep(5)
        # Simulate CPU and memory fluctuation
        service_state['cpu_usage'] = min(95, max(10,
            service_state['cpu_usage'] + random.uniform(-5, 5)))
        service_state['memory_usage'] = min(90, max(30,
            service_state['memory_usage'] + random.uniform(-2, 2)))

        # Simulate replication lag for secondary
        if not PRIMARY:
            service_state['replication_lag'] = random.randint(10, 100)


def main():
    """Start the regional service."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Multi-Region Failover Demo - Regional Service               ║
╠══════════════════════════════════════════════════════════════╣
║  Region: {REGION:<52} ║
║  Role:   {'PRIMARY' if PRIMARY else 'SECONDARY':<52} ║
║  Port:   {PORT:<52} ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Start load simulation thread
    load_thread = threading.Thread(target=simulate_load, daemon=True)
    load_thread.start()

    # Start HTTP server
    server = HTTPServer(('0.0.0.0', PORT), ServiceHandler)
    print(f"[{REGION}] Service listening on port {PORT}")
    print(f"[{REGION}] Endpoints: /health, /health/deep, /metrics, /status, /api/data")
    print(f"[{REGION}] Admin endpoints: /admin/fail, /admin/recover, /admin/latency")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{REGION}] Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
