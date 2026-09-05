"""
Pytest configuration and deterministic database seeding fixtures.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from database.seed.seed_demo import seed_database

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure database has pristine deterministic demo data before running test suite."""
    seed_database()
    yield
