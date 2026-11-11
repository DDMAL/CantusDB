"""
Gunicorn server hooks. Gunicorn loads ./gunicorn.conf.py from its working
directory automatically; deployments also pass it explicitly with ``-c``.
Binds and worker counts stay on the command line.

When PROMETHEUS_MULTIPROC_DIR is set, every worker writes its request metrics
to files in that directory so /metrics can aggregate across workers (see
docs/monitoring.md). Without it, these hooks do nothing.
"""

import os

# Imported here, not inside child_exit: the master runs that hook while
# reaping workers from a signal handler, and an import started there can be
# re-entered when several workers exit at once (e.g. on shutdown), failing
# with "partially initialized module".
from prometheus_client import multiprocess


def on_starting(server):  # pylint: disable=unused-argument
    """Discard metric files left over from a previous run of the server."""
    metrics_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not metrics_dir:
        return
    os.makedirs(metrics_dir, exist_ok=True)
    for entry in os.scandir(metrics_dir):
        if entry.is_file():
            os.remove(entry.path)


def child_exit(server, worker):  # pylint: disable=unused-argument
    """Drop live gauges of a worker that exited, so they are not reported."""
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return
    multiprocess.mark_process_dead(worker.pid)
