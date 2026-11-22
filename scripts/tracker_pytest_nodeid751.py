"""Full pytest collection nodeid in private Release 751 JUnit evidence.

This pinned plugin is loaded into both the untouched 750 baseline and
candidate 751 test workers, avoiding ambiguous JUnit display identities.
"""


def pytest_collection_modifyitems(items):
    for item in items:
        item.user_properties.append(("tracker_pytest_nodeid_751", item.nodeid))
