import os

import uvicorn

from apps.quarantine_gateway import create_app
from packages.govmesh_common import ApiAuthPolicy


if __name__ == "__main__":
    uvicorn.run(
        create_app(
            auth_policy=ApiAuthPolicy.from_env(required=True),
            audit_signing_key=os.environ.get("GOVMESH_AUDIT_SIGNING_KEY"),
        ),
        host="127.0.0.1",
        port=8790,
    )
