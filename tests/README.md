# Load Balancer Test Suite

This directory contains tests for the load balancer system. The tests are organized by module, corresponding to the main components of the system.

## Test Structure

- `tests/algorithms/` - Tests for load balancing algorithms
- `tests/api/` - Tests for the API endpoints
- `tests/core/` - Tests for core components like the load balancer, health checker, etc.
- `conftest.py` - Common test fixtures

## Running Tests

To run all tests:

```bash
pytest
```

To run tests for a specific module:

```bash
pytest tests/algorithms/
pytest tests/api/
pytest tests/core/
```

To run a specific test file:

```bash
pytest tests/algorithms/test_round_robin.py
```

To run tests with verbose output:

```bash
pytest -v
```

## Test Coverage

To check test coverage:

```bash
pytest --cov=src
```

## Adding New Tests

When adding new tests:

1. Follow the existing pattern of `test_*.py` files
2. Use appropriate fixtures from `conftest.py`
3. Focus on unit testing individual components
4. Mock external dependencies

For integration tests involving multiple components, create separate test files that end with `_integration_test.py`. 