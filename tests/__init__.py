"""Netro Plugin Test Suite.

This package contains comprehensive tests for the Netro Indigo plugin.

Test Categories:
- test_api_client.py: API client and HTTP request handling
- test_validation.py: Configuration and action validation
- test_actions.py: Action callback methods and payloads

Run all tests:
    pytest tests/

Run specific category:
    pytest tests/test_api_client.py -v
    pytest -m api
    pytest -m validation
    pytest -m actions

Generate coverage report:
    pytest --cov --cov-report=html
"""
