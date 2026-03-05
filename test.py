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
import sys
import os

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'monitor'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'loadbalancer'))


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

    def test_latency_history_limit(self):
        """Test latency history is limited to 100 samples."""
        for _ in range(150):
            self.health.record_success(50)

        self.assertEqual(len(self.health.latency_history), 100)


class TestLoadBalancerStrategy(unittest.TestCase):
    """Tests for load balancing strategies."""

    def test_region_selection_priority(self):
        """Test priority-based region selection."""
        from failover_lb import GlobalLoadBalancer, LoadBalancingStrategy

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

    def test_region_selection_with_unhealthy(self):
        """Test selection skips unhealthy regions."""
        from failover_lb import GlobalLoadBalancer, LoadBalancingStrategy

        lb = GlobalLoadBalancer()
        lb.add_region('region-a', 'http://a:8000', priority=1)
        lb.add_region('region-b', 'http://b:8000', priority=2)

        lb.strategy = LoadBalancingStrategy.PRIORITY

        # Mark primary as unhealthy
        lb.regions['region-a'].is_healthy = False
        lb.regions['region-b'].is_healthy = True

        selected = lb.select_region()
        self.assertEqual(selected.name, 'region-b')

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

    def test_no_available_regions(self):
        """Test behavior when no regions are available."""
        from failover_lb import GlobalLoadBalancer

        lb = GlobalLoadBalancer()
        lb.add_region('region-a', 'http://a:8000')

        # Mark as unhealthy
        lb.regions['region-a'].is_healthy = False

        selected = lb.select_region()
        self.assertIsNone(selected)


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
        self.assertEqual(event.reason, 'Health check failures: 3')
        self.assertFalse(event.recovered)
        self.assertIsNone(event.recovery_time)


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
        self.assertIn('region-1', status['regions'])
        self.assertIn('region-2', status['regions'])

    def test_alert_management(self):
        """Test alert creation and retrieval."""
        from health_monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor._add_alert('WARNING', 'test-region', 'Test alert')

        self.assertEqual(len(monitor.alerts), 1)
        self.assertEqual(monitor.alerts[0]['level'], 'WARNING')
        self.assertEqual(monitor.alerts[0]['region'], 'test-region')

    def test_alert_limit(self):
        """Test that alerts are limited to max_alerts."""
        from health_monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.max_alerts = 10

        for i in range(20):
            monitor._add_alert('INFO', 'region', f'Alert {i}')

        self.assertEqual(len(monitor.alerts), 10)


class TestServiceHandler(unittest.TestCase):
    """Tests for HTTP handlers with mock server."""

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

        with urlopen('http://localhost:19999/health') as response:
            data = json.loads(response.read().decode())

        self.assertEqual(data['status'], 'healthy')

    def test_deep_health_endpoint(self):
        """Test deep health check endpoint."""
        from urllib.request import urlopen

        with urlopen('http://localhost:19999/health/deep') as response:
            data = json.loads(response.read().decode())

        self.assertEqual(data['status'], 'healthy')
        self.assertIn('checks', data)
        self.assertEqual(data['checks']['server']['status'], 'pass')


class TestGlobalLoadBalancer(unittest.TestCase):
    """Tests for the global load balancer."""

    def test_add_region(self):
        """Test adding regions to load balancer."""
        from failover_lb import GlobalLoadBalancer

        lb = GlobalLoadBalancer()
        lb.add_region('us-east-1', 'http://us-east:8000', is_primary=True)

        self.assertIn('us-east-1', lb.regions)
        self.assertEqual(lb.primary_region, 'us-east-1')

    def test_get_status(self):
        """Test getting load balancer status."""
        from failover_lb import GlobalLoadBalancer

        lb = GlobalLoadBalancer()
        lb.add_region('region-a', 'http://a:8000')

        status = lb.get_status()

        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['total_regions'], 1)
        self.assertIn('regions', status)

    def test_set_region_status(self):
        """Test manually setting region status."""
        from failover_lb import GlobalLoadBalancer, RegionStatus

        lb = GlobalLoadBalancer()
        lb.add_region('region-a', 'http://a:8000')

        result = lb.set_region_status('region-a', RegionStatus.MAINTENANCE)
        self.assertTrue(result)
        self.assertEqual(lb.regions['region-a'].status, RegionStatus.MAINTENANCE)

    def test_set_nonexistent_region_status(self):
        """Test setting status for non-existent region."""
        from failover_lb import GlobalLoadBalancer, RegionStatus

        lb = GlobalLoadBalancer()
        result = lb.set_region_status('nonexistent', RegionStatus.MAINTENANCE)
        self.assertFalse(result)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRegionHealth))
    suite.addTests(loader.loadTestsFromTestCase(TestLoadBalancerStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestFailoverEvent))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestServiceHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestGlobalLoadBalancer))

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
