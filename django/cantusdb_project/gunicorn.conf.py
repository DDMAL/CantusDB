"""
Gunicorn server hooks. Gunicorn loads ./gunicorn.conf.py from its working
directory automatically; deployments also pass it explicitly with ``-c``.
Binds and worker counts stay on the command line.

When PROMETHEUS_MULTIPROC_DIR is set, every worker writes its request metrics
to files in that directory so /metrics can aggregate across workers (see
docs/monitoring.md). Without it, these hooks do nothing.
"""

import os


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
    # Imported lazily so the master never loads it when metrics are disabled.
    # pylint: disable-next=import-outside-toplevel
    from prometheus_client import multiprocess

    multiprocess.mark_process_dead(worker.pid)
