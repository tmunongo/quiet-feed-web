import logging
import os

import uvicorn

from .app import create_app
from .config import Config


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = Config.from_env()
    config.validate()
    uvicorn.run(
        create_app(config),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "3000")),
        workers=1,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        timeout_graceful_shutdown=300,
    )


if __name__ == "__main__":
    main()
