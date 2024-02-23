import pytest


@pytest.fixture(autouse=True)
# using aaa in name to make sure this fixture always runs first due to some alphabetical order in certain cases
def aaa_db(db):
    pass
