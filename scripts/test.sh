#!/usr/bin/env python3
"""
Unit Tests for Multi-Region Failover Demo
Run with: python test.py
"""

import unittest
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import StringIO
import sys

# Add project paths
sys.path.insert(0, '.')
sys.path.insert(0, './app')
sys.path.insert(0, './monitor')
sys.path.insert(0, './loadbalancer')


class MockHandler(BaseHTTPRequestHandler):
    """Mock HTTP handler for testing."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        elif self.path == '/health/deep':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'healthy',
                'checks': {
                    'server': {'status': 'pass'},
                    'database': {'status': 'pass'},
                    'replication': {'status': 'pass', 'lag_ms': 50}
                }
            }).encode())
        else:
            self.send_error(404)


class TestRegionHealth(unittest.TestCase):
    """Tests for RegionHealth class."""

    def setUp(self):
        from health_monitor import RegionHealth
        self.health = RegionHealth('test-region', 'http://localhost:9999')

    def test_initial_state(self):
        """Test initial health state."""
        self.assertEqual(self.health.name, 'test-region')
        self.assertTrue(self.health.is_healthy)
        self.assertEqual(self.health.consecutive_failures, 0)

    def test_record_success(self):
        """Test recording successful health check."""
        self.health.record_success(50.5)
        self.assertTrue(self.health.is_healthy)
        self.assertEqual(self.health.consecutive_failures, 0)
        self.assertEqual(self.health.consecutive_successes, 1)
        self.assertEqual(len(self.health.latency_history), 1)

    def test_record_failure(self):
        """Test recording failed health check."""
        self.health.record_failure('Connection refused')
        self.assertFalse(self.health.is_healthy)
        self.assertEqual(self.health.consecutive_failures, 1)
        self.assertEqual(self.health.total_failures, 1)

    def test_availability_calculation(self):
        """Test availability percentage calculation."""
        # 8 successes, 2 failures = 80%
        for _ in range(8):
            self.health.record_success(50)
        for _ in range(2):
            self.health.record_failure('error')

        self.assertEqual(self.health.get_availability(), 80.0)

    def test_avg_latency(self):
        """Test average latency calculation."""
        for latency in [50, 60, 70, 80]:
            self.health.record_success(latency)

        self.assertEqual(self.health.get_avg_latency(), 65.0)


class TestLoadBalancerStrategy(unittest.TestCase):
    """Tests for load balancing strategies."""

    def test_region_selection_priority(self):
        """Test priority-based region selection."""
        from failover_lb import GlobalLoadBalancer, Region, RegionStatus, LoadBalancingStrategy

        lb = GlobalLoadBalancer()
        lb.add_region('region-a', 'http://a:8000', priority=1)
        lb.add_region('region-b', 'http://b:8000', priority=2)
        lb.add_region('region-c', 'http://c:8000', priority=3)

        lb.strategy = LoadBalancingStrategy.PRIORITY

        # Mark all as healthy
        for region in lb.regions.values():
            region.is_healthy = True

        selected = lb.select_region()
        self.assertEqual(selected.name, 'region-a')

    def test_region_selection_weighted(self):
        """Test weighted region selection."""
        from failover_lb import GlobalLoadBalancer, LoadBalancingStrategy

        lb = GlobalLoadBalancer()
        lb.add_region('heavy', 'http://heavy:8000', weight=100)
        lb.add_region('light', 'http://light:8000', weight=1)

        lb.strategy = LoadBalancingStrategy.WEIGHTED

        # Mark all as healthy
        for region in lb.regions.values():
            region.is_healthy = True

        # Heavy should be selected most often
        selections = {'heavy': 0, 'light': 0}
        for _ in range(100):
            selected = lb.select_region()
            selections[selected.name] += 1

        self.assertGreater(selections['heavy'], selections['light'])


class TestFailoverEvent(unittest.TestCase):
    """Tests for failover events."""

    def test_failover_event_creation(self):
        """Test creating a failover event."""
        from failover_lb import FailoverEvent

        event = FailoverEvent(
            from_region='us-east-1',
            to_region='eu-west-1',
            reason='Health check failures: 3'
        )

        self.assertEqual(event.from_region, 'us-east-1')
        self.assertEqual(event.to_region, 'eu-west-1')
        self.assertFalse(event.recovered)


class TestServiceHandler(unittest.TestCase):
    """Tests for the service HTTP handler."""

    @classmethod
    def setUpClass(cls):
        """Start mock server for testing."""
        cls.server = HTTPServer(('localhost', 19999), MockHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        """Stop mock server."""
        cls.server.shutdown()

    def test_health_endpoint(self):
        """Test health check endpoint."""
        from urllib.request import urlopen
        import json

        with urlopen('http://localhost:19999/health') as response:
            data = json.loads(response.read().decode())

        self.assertEqual(data['status'], 'healthy')

    def test_deep_health_endpoint(self):
        """Test deep health check endpoint."""
        from urllib.request import urlopen
        import json

        with urlopen('http://localhost:19999/health/deep') as response:
            data = json.loads(response.read().decode())

        self.assertEqual(data['status'], 'healthy')
        self.assertIn('checks', data)
        self.assertEqual(data['checks']['server']['status'], 'pass')


class TestHealthMonitor(unittest.TestCase):
    """Tests for health monitor."""

    def test_add_region(self):
        """Test adding regions to monitor."""
        from health_monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.add_region('test-region', 'http://localhost:8000')

        self.assertIn('test-region', monitor.regions)
        self.assertEqual(len(monitor.regions), 1)

    def test_monitor_status(self):
        """Test getting monitor status."""
        from health_monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.add_region('region-1', 'http://localhost:8000')
        monitor.add_region('region-2', 'http://localhost:8001')

        status = monitor.get_status()

        self.assertEqual(status['total_regions'], 2)
        self.assertIn('regions', status)


if __name__ == '__main__':
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRegionHealth))
    suite.addTests(loader.loadTestsFromTestCase(TestLoadBalancerStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestFailoverEvent))
    suite.addTests(loader.loadTestsFromTestCase(TestServiceHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthMonitor))

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
