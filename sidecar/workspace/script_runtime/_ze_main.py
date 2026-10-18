"""Entry point of a tool script: probe isolation, then run main.py."""

import os
import runpy
import socket
import sys


def probe(workspace, listdir=os.listdir, connect=socket.create_connection):
    """Return what the script user can still reach, or None when it is closed in."""
    try:
        listdir(workspace)
    except OSError:
        pass
    else:
        return "workspace readable"
    try:
        sock = connect(("1.1.1.1", 53), timeout=0.5)
    except OSError:
        return None
    sock.close()
    return "network reachable"


def main(argv):
    if len(argv) > 2 and argv[1] == "--probe":
        breach = probe(argv[2])
        if breach:
            with os.fdopen(int(os.environ["ZE_REQ_FD"]), "w") as pipe:
                pipe.write('{"isolation_breach": "%s"}\n' % breach)
            return
    sys.path.insert(0, os.getcwd())
    runpy.run_path("main.py", run_name="__main__")


if __name__ == "__main__":
    main(sys.argv)
