"""Release 523: explicit per-instance feature parity activation.

DEV remains the test environment, PROD the production environment. Both run
the same application and private user features when provisioned.

Existing PROD hosts do not switch authentication just by updating code:
TRACKER_PROD_PARITY523 must be exactly "1", and the private session-auth
store/marker must already be present. A guarded local cutover utility is
responsible for creating that store and enabling the flag.

Never use the instance name to grant administrator privileges or route data.
"""
import os

from . import config


def interactive_parity523():
    instance = config.instance_label()
    return instance == "DEV" or (
        instance == "PROD"
        and os.getenv("TRACKER_PROD_PARITY523", "0") == "1"
    )
