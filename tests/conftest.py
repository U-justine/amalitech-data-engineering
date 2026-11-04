import os
import sys

import pytest

# let the tests import "src" from the project folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.spark_session import get_spark


# one Spark session shared by all tests (starting Spark is slow)
@pytest.fixture(scope="session")
def spark():
    session = get_spark("tests")
    yield session
    session.stop()
