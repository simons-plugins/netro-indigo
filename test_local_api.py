#!/usr/bin/env python3
"""Local API Testing Script for Netro Plugin

This script allows testing Netro API integration without Indigo.
Use your real Netro serial number to test against actual hardware.

SAFETY: This script only tests read operations by default.
        Write operations (watering, standby) require explicit flags.

Usage:
    python3 test_local_api.py --serial YOUR_SERIAL_NUMBER
    python3 test_local_api.py --serial YOUR_SERIAL_NUMBER --full
    python3 test_local_api.py --help
"""

import argparse
import json
import sys
from datetime import datetime
import requests


class NetroAPITester:
    """Standalone Netro API tester."""

    def __init__(self, serial_number, timeout=5):
        self.serial_number = serial_number
        self.timeout = timeout
        self.api_base = "http://api.netrohome.com/npa/v1/"

    def _make_request(self, endpoint, method="GET", data=None):
        """Make API request and return response."""
        url = f"{self.api_base}{endpoint}"

        print(f"\n{'='*70}")
        print(f"Request: {method} {url}")
        if data:
            print(f"Data: {json.dumps(data, indent=2)}")

        try:
            if method == "GET":
                response = requests.get(url, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(
                    url,
                    data=json.dumps(data),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )
            elif method == "PUT":
                response = requests.put(
                    url,
                    data=json.dumps(data),
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Response Status: {result.get('status', 'UNKNOWN')}")

                # Print token info
                if 'meta' in result:
                    meta = result['meta']
                    print(f"Tokens Remaining: {meta.get('token_remaining', 'N/A')}")
                    print(f"Token Reset: {meta.get('token_reset', 'N/A')}")

                return result
            else:
                print(f"Error: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                return None

        except requests.exceptions.Timeout:
            print(f"ERROR: Request timed out after {self.timeout} seconds")
            return None
        except requests.exceptions.ConnectionError:
            print(f"ERROR: Connection failed - check network")
            return None
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            return None

    def test_device_info(self):
        """Test getting device info (READ-ONLY)."""
        print("\n" + "="*70)
        print("TEST: Device Info")
        print("="*70)

        response = self._make_request(f"info.json?key={self.serial_number}")

        if response and response.get('status') == 'OK':
            data = response.get('data', {})
            devices = data.get('devices', [])

            print(f"\n✓ Success - Found {len(devices)} device(s)")

            for i, device in enumerate(devices):
                print(f"\nDevice {i+1}:")
                print(f"  Name: {device.get('name', 'N/A')}")
                print(f"  Model: {device.get('model', 'N/A')}")
                print(f"  Serial: {device.get('serial', 'N/A')}")
                print(f"  Status: {device.get('status', 'N/A')}")
                print(f"  Standby: {device.get('in_standby', 'N/A')}")
                print(f"  Paused: {device.get('paused', 'N/A')}")

                zones = device.get('zones', [])
                print(f"  Zones: {len(zones)}")
                for zone in zones:
                    enabled = "✓" if zone.get('enabled') else "✗"
                    smart = "SMART" if zone.get('smart') else "MANUAL"
                    print(f"    {enabled} Zone {zone.get('ith')}: {zone.get('name')} [{smart}]")

            return True
        else:
            print(f"\n✗ Failed to get device info")
            return False

    def test_schedules(self):
        """Test getting schedules (READ-ONLY)."""
        print("\n" + "="*70)
        print("TEST: Schedules")
        print("="*70)

        response = self._make_request(f"schedules.json?key={self.serial_number}")

        if response and response.get('status') == 'OK':
            data = response.get('data', {})
            schedules = data.get('schedules', [])

            print(f"\n✓ Success - Found {len(schedules)} schedule(s)")

            executing = [s for s in schedules if s.get('status') == 'EXECUTING']
            valid = [s for s in schedules if s.get('status') == 'VALID']

            if executing:
                print(f"\nCurrently Executing:")
                for sched in executing:
                    print(f"  Zone {sched.get('zone')}: {sched.get('zone_name')}")
                    print(f"    Source: {sched.get('source')}")
                    print(f"    Duration: {sched.get('duration')}s")

            if valid:
                print(f"\nUpcoming Schedules:")
                for sched in valid[:3]:  # Show first 3
                    start_time = datetime.fromtimestamp(sched.get('start_time', 0) / 1000.0)
                    print(f"  Zone {sched.get('zone')}: {sched.get('zone_name')}")
                    print(f"    Source: {sched.get('source')}")
                    print(f"    Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"    Duration: {sched.get('duration')}s")

            return True
        else:
            print(f"\n✗ Failed to get schedules")
            return False

    def test_moistures(self):
        """Test getting moisture levels (READ-ONLY)."""
        print("\n" + "="*70)
        print("TEST: Moisture Levels")
        print("="*70)

        response = self._make_request(f"moistures.json?key={self.serial_number}")

        if response and response.get('status') == 'OK':
            data = response.get('data', {})
            moistures = data.get('moistures', [])

            print(f"\n✓ Success - Found moisture data for {len(moistures)} zone(s)")

            for moisture in moistures:
                zone = moisture.get('zone')
                level = moisture.get('moisture')
                date = moisture.get('date', 'N/A')
                print(f"  Zone {zone}: {level}% (as of {date})")

            return True
        else:
            print(f"\n✗ Failed to get moisture data")
            return False

    def test_sensor_data(self, sensor_serial=None):
        """Test getting sensor data (READ-ONLY)."""
        if not sensor_serial:
            print("\nSkipping sensor test - no sensor serial provided")
            return True

        print("\n" + "="*70)
        print("TEST: Sensor Data")
        print("="*70)

        response = self._make_request(f"sensor_data.json?key={sensor_serial}")

        if response and response.get('status') == 'OK':
            data = response.get('data', {})
            sensors = data.get('sensors', [])

            print(f"\n✓ Success - Found {len(sensors)} sensor(s)")

            for sensor in sensors:
                print(f"\nSensor: {sensor.get('name', 'N/A')}")
                readings = sensor.get('readings', [])
                if readings:
                    reading = readings[0]  # Latest reading
                    print(f"  Temperature: {reading.get('fahrenheit')}°F / {reading.get('celsius')}°C")
                    print(f"  Moisture: {reading.get('moisture')}%")
                    print(f"  Sunlight: {reading.get('sunlight')} lux")
                    print(f"  Battery: {reading.get('battery')}%")

            return True
        else:
            print(f"\n✗ Failed to get sensor data")
            return False

    def test_report_weather(self):
        """Test weather reporting (WRITE - requires --full flag)."""
        print("\n" + "="*70)
        print("TEST: Report Weather (WRITE OPERATION)")
        print("="*70)
        print("This will send test weather data to Netro")

        data = {
            "key": self.serial_number,
            "condition": 0,  # Clear
            "t": 72,  # Current temp
            "t_max": 80,
            "t_min": 65,
            "humidity": 60,
            "date": datetime.now().strftime("%Y-%m-%d")
        }

        response = self._make_request("report_weather.json", method="POST", data=data)

        if response and response.get('status') == 'OK':
            print(f"\n✓ Success - Weather data reported")
            return True
        else:
            print(f"\n✗ Failed to report weather")
            return False

    def run_safe_tests(self):
        """Run only read-only tests."""
        print("\n" + "="*70)
        print("RUNNING SAFE (READ-ONLY) TESTS")
        print("="*70)
        print(f"Serial Number: {self.serial_number}")
        print(f"API Base URL: {self.api_base}")

        results = {
            "device_info": self.test_device_info(),
            "schedules": self.test_schedules(),
            "moistures": self.test_moistures()
        }

        self.print_summary(results)
        return all(results.values())

    def run_full_tests(self, sensor_serial=None):
        """Run all tests including write operations."""
        print("\n" + "="*70)
        print("RUNNING FULL TESTS (INCLUDING WRITE OPERATIONS)")
        print("="*70)
        print(f"Serial Number: {self.serial_number}")
        print(f"API Base URL: {self.api_base}")
        print("\nWARNING: This will send test data to your Netro system")

        results = {
            "device_info": self.test_device_info(),
            "schedules": self.test_schedules(),
            "moistures": self.test_moistures(),
            "report_weather": self.test_report_weather()
        }

        if sensor_serial:
            results["sensor_data"] = self.test_sensor_data(sensor_serial)

        self.print_summary(results)
        return all(results.values())

    def print_summary(self, results):
        """Print test summary."""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {test_name}")

        print(f"\nTotal: {passed}/{total} tests passed")

        if passed == total:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")


def main():
    parser = argparse.ArgumentParser(
        description="Test Netro API integration locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run safe (read-only) tests
  python3 test_local_api.py --serial a4cf12b8d5e2

  # Run full tests (including writes)
  python3 test_local_api.py --serial a4cf12b8d5e2 --full

  # Test with sensor
  python3 test_local_api.py --serial a4cf12b8d5e2 --sensor whisperer123

  # Use custom timeout
  python3 test_local_api.py --serial a4cf12b8d5e2 --timeout 10

Safety:
  - Default mode only runs READ operations (safe)
  - Use --full flag to test WRITE operations
  - Weather reporting sends test data but won't trigger watering
        """
    )

    parser.add_argument(
        '--serial',
        required=True,
        help='Netro controller serial number (required)'
    )

    parser.add_argument(
        '--sensor',
        help='Whisperer sensor serial number (optional)'
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full tests including write operations'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=5,
        help='API request timeout in seconds (default: 5)'
    )

    args = parser.parse_args()

    # Create tester
    tester = NetroAPITester(args.serial, args.timeout)

    # Run tests
    try:
        if args.full:
            print("\n⚠️  FULL TEST MODE - Will send write operations to Netro")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted")
                sys.exit(0)

            success = tester.run_full_tests(args.sensor)
        else:
            print("\n✓ SAFE TEST MODE - Read-only operations")
            success = tester.run_safe_tests()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
