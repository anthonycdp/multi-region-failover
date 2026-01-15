#!/usr/bin/env python3
"""
Monitoring Dashboard
Web-based dashboard for visualizing multi-region health and failover status.
"""

import os
import json
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError


LB_URL = os.getenv('LB_URL', 'http://load-balancer:9000')
MONITOR_URL = os.getenv('MONITOR_URL', 'http://health-monitor:8080')
PORT = int(os.getenv('PORT', 3000))


def fetch_json(url, timeout=5):
    """Fetch JSON from URL."""
    try:
        req = Request(url, headers={'User-Agent': 'Dashboard/1.0'})
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode()), None
    except Exception as e:
        return None, str(e)


def get_lb_status():
    """Get load balancer status."""
    return fetch_json(f"{LB_URL}/lb/status")


def get_monitor_status():
    """Get health monitor status."""
    return fetch_json(f"{MONITOR_URL}/status")


def get_failover_events():
    """Get failover events."""
    return fetch_json(f"{LB_URL}/lb/failovers")


def get_alerts():
    """Get recent alerts."""
    return fetch_json(f"{MONITOR_URL}/alerts")


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the dashboard."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def send_json_response(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def send_html_response(self, html):
        """Send HTML response."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self.handle_dashboard()
        elif self.path == '/health':
            self.send_json_response({'status': 'healthy'})
        elif self.path == '/api/status':
            self.handle_api_status()
        elif self.path == '/api/regions':
            self.handle_api_regions()
        elif self.path == '/api/failovers':
            self.handle_api_failovers()
        elif self.path == '/api/alerts':
            self.handle_api_alerts()
        else:
            self.send_error(404, 'Not Found')

    def handle_dashboard(self):
        """Serve the dashboard HTML."""
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Region Failover Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 30px;
            border-bottom: 2px solid #0f3460;
        }
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #e94560, #0f3460);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header .status {
            font-size: 1.2em;
            padding: 5px 20px;
            border-radius: 20px;
            display: inline-block;
        }
        .status-healthy { background: #00b894; color: white; }
        .status-degraded { background: #fdcb6e; color: #333; }
        .status-critical { background: #e74c3c; color: white; }
        .status-failover { background: #e94560; color: white; }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }

        .card h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #e94560;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card h2::before {
            content: '';
            width: 4px;
            height: 20px;
            background: #e94560;
            border-radius: 2px;
        }

        .region-card {
            position: relative;
            overflow: hidden;
        }

        .region-card.healthy { border-left: 4px solid #00b894; }
        .region-card.unhealthy { border-left: 4px solid #e74c3c; }

        .region-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .region-name {
            font-size: 1.3em;
            font-weight: bold;
        }

        .region-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }

        .badge-primary { background: #3498db; }
        .badge-secondary { background: #95a5a6; }

        .metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .metric {
            background: rgba(0, 0, 0, 0.2);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #00b894;
        }

        .metric-label {
            font-size: 0.8em;
            color: #888;
            margin-top: 5px;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        .status-indicator.healthy { background: #00b894; }
        .status-indicator.unhealthy { background: #e74c3c; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .failover-list, .alert-list {
            max-height: 300px;
            overflow-y: auto;
        }

        .failover-item, .alert-item {
            padding: 12px;
            margin-bottom: 10px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            font-size: 0.9em;
        }

        .failover-item .time, .alert-item .time {
            font-size: 0.8em;
            color: #888;
        }

        .alert-warning { border-left: 3px solid #fdcb6e; }
        .alert-critical { border-left: 3px solid #e74c3c; }
        .alert-info { border-left: 3px solid #3498db; }

        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 15px;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            transition: transform 0.2s, opacity 0.2s;
        }

        .btn:hover { transform: translateY(-2px); }
        .btn:active { transform: translateY(0); }

        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #00b894; color: white; }
        .btn-warning { background: #fdcb6e; color: #333; }

        .last-updated {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }

        .stats-row {
            display: flex;
            justify-content: space-around;
            text-align: center;
        }

        .stat {
            padding: 10px;
        }

        .stat-value {
            font-size: 2em;
            font-weight: bold;
        }

        .stat-label {
            font-size: 0.8em;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Multi-Region Failover Dashboard</h1>
        <div id="overall-status" class="status status-healthy">All Systems Operational</div>
    </div>

    <div class="grid">
        <div id="regions-container" class="grid" style="grid-column: 1 / -1;"></div>

        <div class="card">
            <h2>Load Balancer Stats</h2>
            <div class="stats-row">
                <div class="stat">
                    <div id="total-requests" class="stat-value">0</div>
                    <div class="stat-label">Total Requests</div>
                </div>
                <div class="stat">
                    <div id="total-failovers" class="stat-value">0</div>
                    <div class="stat-label">Failovers</div>
                </div>
                <div class="stat">
                    <div id="strategy" class="stat-value">priority</div>
                    <div class="stat-label">Strategy</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Failover Events</h2>
            <div id="failovers-list" class="failover-list">
                <p style="color: #666;">No failover events</p>
            </div>
        </div>

        <div class="card">
            <h2>Recent Alerts</h2>
            <div id="alerts-list" class="alert-list">
                <p style="color: #666;">No alerts</p>
            </div>
        </div>

        <div class="card" style="grid-column: 1 / -1;">
            <h2>Simulation Controls</h2>
            <p style="margin-bottom: 15px; color: #888;">Test failover by simulating region failures:</p>
            <div class="controls">
                <button class="btn btn-danger" onclick="simulateFailure('us-east-1')">Fail US-East</button>
                <button class="btn btn-danger" onclick="simulateFailure('eu-west-1')">Fail EU-West</button>
                <button class="btn btn-danger" onclick="simulateFailure('ap-southeast-1')">Fail AP-Southeast</button>
                <button class="btn btn-success" onclick="recoverAll()">Recover All</button>
                <button class="btn btn-warning" onclick="simulateLatency()">Add Latency</button>
            </div>
        </div>
    </div>

    <div id="last-updated" class="last-updated"></div>

    <script>
        const regions = ['us-east-1', 'eu-west-1', 'ap-southeast-1'];
        const regionPorts = { 'us-east-1': 8001, 'eu-west-1': 8002, 'ap-southeast-1': 8003 };

        async function fetchData() {
            try {
                const [lbStatus, monitorStatus, failovers, alerts] = await Promise.all([
                    fetch('/api/status').then(r => r.json()),
                    fetch('/api/regions').then(r => r.json()),
                    fetch('/api/failovers').then(r => r.json()),
                    fetch('/api/alerts').then(r => r.json())
                ]);

                updateDashboard(lbStatus, monitorStatus, failovers, alerts);
            } catch (error) {
                console.error('Failed to fetch data:', error);
            }
        }

        function updateDashboard(lbStatus, monitorStatus, failovers, alerts) {
            // Update overall status
            const statusEl = document.getElementById('overall-status');
            if (lbStatus.active_failover) {
                statusEl.textContent = 'Failover Active';
                statusEl.className = 'status status-failover';
            } else if (lbStatus.healthy_regions === lbStatus.total_regions) {
                statusEl.textContent = 'All Systems Operational';
                statusEl.className = 'status status-healthy';
            } else {
                statusEl.textContent = 'Degraded - ' + lbStatus.healthy_regions + '/' + lbStatus.total_regions + ' Regions Healthy';
                statusEl.className = 'status status-degraded';
            }

            // Update stats
            document.getElementById('total-requests').textContent = lbStatus.total_requests || 0;
            document.getElementById('total-failovers').textContent = lbStatus.total_failovers || 0;
            document.getElementById('strategy').textContent = lbStatus.strategy || 'priority';

            // Update region cards
            const regionsContainer = document.getElementById('regions-container');
            regionsContainer.innerHTML = '';

            for (const [name, region] of Object.entries(lbStatus.regions || {})) {
                const card = document.createElement('div');
                card.className = `card region-card ${region.is_healthy ? 'healthy' : 'unhealthy'}`;

                const role = name === lbStatus.primary_region ? 'Primary' : 'Secondary';
                const roleBadge = role === 'Primary' ? 'badge-primary' : 'badge-secondary';

                card.innerHTML = `
                    <div class="region-header">
                        <span class="region-name">
                            <span class="status-indicator ${region.is_healthy ? 'healthy' : 'unhealthy'}"></span>
                            ${name}
                        </span>
                        <span class="region-badge ${roleBadge}">${role}</span>
                    </div>
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value">${Math.round(region.latency_ms || 0)}ms</div>
                            <div class="metric-label">Latency</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${region.total_requests || 0}</div>
                            <div class="metric-label">Requests</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${region.status || 'active'}</div>
                            <div class="metric-label">Status</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${region.priority}</div>
                            <div class="metric-label">Priority</div>
                        </div>
                    </div>
                `;
                regionsContainer.appendChild(card);
            }

            // Update failovers
            const failoversList = document.getElementById('failovers-list');
            if (failovers.events && failovers.events.length > 0) {
                failoversList.innerHTML = failovers.events.slice(-5).reverse().map(e => `
                    <div class="failover-item">
                        <strong>${e.from_region}</strong> → <strong>${e.to_region}</strong>
                        <br><span class="time">${new Date(e.timestamp).toLocaleString()}</span>
                        <br><small>${e.reason}</small>
                        ${e.recovered ? '<br><span style="color: #00b894;">✓ Recovered</span>' : ''}
                    </div>
                `).join('');
            }

            // Update alerts
            const alertsList = document.getElementById('alerts-list');
            if (alerts.alerts && alerts.alerts.length > 0) {
                alertsList.innerHTML = alerts.alerts.slice(-10).reverse().map(a => `
                    <div class="alert-item alert-${a.level.toLowerCase()}">
                        <strong>[${a.level}]</strong> ${a.region}: ${a.message}
                        <br><span class="time">${new Date(a.timestamp).toLocaleString()}</span>
                    </div>
                `).join('');
            }

            // Update timestamp
            document.getElementById('last-updated').textContent =
                'Last updated: ' + new Date().toLocaleString();
        }

        async function simulateFailure(region) {
            try {
                const port = regionPorts[region];
                await fetch(`http://localhost:${port}/admin/fail`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: 'general', duration: 60 })
                });
                alert(`Simulated failure for ${region}`);
            } catch (error) {
                alert('Failed to simulate failure: ' + error.message);
            }
        }

        async function recoverAll() {
            for (const region of regions) {
                try {
                    const port = regionPorts[region];
                    await fetch(`http://localhost:${port}/admin/recover`, {
                        method: 'POST'
                    });
                } catch (error) {
                    console.error(`Failed to recover ${region}:`, error);
                }
            }
            alert('Recovery triggered for all regions');
        }

        async function simulateLatency() {
            try {
                await fetch(`http://localhost:8001/admin/latency`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ latency_ms: 2000 })
                });
                alert('Added latency to US-East');
            } catch (error) {
                alert('Failed to add latency: ' + error.message);
            }
        }

        // Initial load and refresh interval
        fetchData();
        setInterval(fetchData, 3000);
    </script>
</body>
</html>'''
        self.send_html_response(html)

    def handle_api_status(self):
        """API endpoint for combined status."""
        lb_data, lb_err = get_lb_status()
        monitor_data, monitor_err = get_monitor_status()

        response = {
            'load_balancer': lb_data or {'error': lb_err},
            'monitor': monitor_data or {'error': monitor_err},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.send_json_response(response)

    def handle_api_regions(self):
        """API endpoint for region status."""
        data, error = get_lb_status()
        if data:
            self.send_json_response({'regions': data.get('regions', {})})
        else:
            self.send_json_response({'error': error}, status=503)

    def handle_api_failovers(self):
        """API endpoint for failover events."""
        data, error = get_failover_events()
        if data:
            self.send_json_response(data)
        else:
            self.send_json_response({'error': error}, status=503)

    def handle_api_alerts(self):
        """API endpoint for alerts."""
        data, error = get_alerts()
        if data:
            self.send_json_response(data)
        else:
            self.send_json_response({'error': error}, status=503)


def main():
    """Start the dashboard server."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Multi-Region Failover Dashboard                              ║
╠══════════════════════════════════════════════════════════════╣
║  Port: {PORT:<55} ║
║  LB URL: {LB_URL:<51} ║
║  Monitor URL: {MONITOR_URL:<46} ║
╚══════════════════════════════════════════════════════════════╝
    """)

    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"[Dashboard] Running at http://localhost:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dashboard] Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
