#!/usr/bin/env python3

import setproctitle
import uvicorn


setproctitle.setproctitle("SmallFolks DEV API")

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        "app:create_app",
        factory=True,
        host="127.0.0.1",
        port=5340,
        reload=True,
        log_level="info",
    )
