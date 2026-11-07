# Cancelling abandoned searches

When a visitor changes a melody or leaves a search page, Nginx closes its connection to Gunicorn. `CancelDisconnectedSearchMiddleware` watches that connection while PostgreSQL executes a search query and asks PostgreSQL to cancel it. Melody search already aborts its previous browser request when a new note is drawn, so it needs no new cancellation endpoint or request identifier.

Cancellation applies to GET and HEAD requests under `/chant-search/`, `/CanadianChantDB/chant-search/`, `/searchms/`, `/ci-search/`, `/id/`, `/ajax/melody-search/` and `/ajax/search-bar/`. The middleware monitors SELECT statements, including the parenthesized SELECTs generated for unions. Editing requests, transaction cleanup and other routes retain their existing behavior. Search results and source permissions are unchanged.

Each running query has a short-lived watcher that checks for a disconnect every 50 ms. The watcher uses that database connection's libpq cancellation handle, which includes its backend secret. After detecting a disconnect, it polls the nonblocking cancellation connection with a shared one-second deadline, including retries if the query has not yet reached PostgreSQL. If SQL finishes first, the watcher stops without waiting for cancellation to be acknowledged. The request waits for the watcher to stop and release its handle before continuing; a disconnected request's database connection is then closed so a late cancellation cannot affect a subsequent request. Expected cancellation produces status 499 instead of an application error.

Django logs that response once at INFO through `main_app.middleware`, which has a console handler enabled in production; it does not also emit a 499 warning. Other request warnings and errors retain their normal logging. A successful cancellation dispatch does not prove that PostgreSQL stopped the query, so retries continue within the deadline. Reaching that deadline after a successful dispatch is logged at INFO; failures to send cancellation remain warnings.

## Deployment requirements

- Linux, Gunicorn and the locked Psycopg 3.3.6 binary package with libpq 17 or newer. Gunicorn supplies `gunicorn.socket`; Linux supplies `POLLRDHUP`. The Nginx prerequisite check rejects a driver without nonblocking cancellation support.
- Nginx must keep `proxy_ignore_client_abort off` (its default) so it closes the upstream connection when the browser leaves. Do not combine this feature with a configuration that deliberately keeps abandoned upstream requests alive.
- Rebuild the application image to install the updated driver from `poetry.lock`. No database migration, PostgreSQL server upgrade or additional service is required. Deploy the application through the usual develop → staging → production workflow.

Deployment updates the mounted source before rebuilding the image. During that window, a replacement worker may still have the old driver. It logs a warning and serves requests with this middleware disabled, without falling back to blocking cancellation. Recreated workers enable cancellation once the updated driver is installed. The Nginx prerequisite check calls `require_search_cancellation_support()` and refuses to enable the shared limit on the temporary unsupported runtime.

The development server does not expose the Gunicorn socket and passes requests through normally. The one-second deadline only limits cancellation after a disconnect; connected searches have no new time limit. Cancellation remains best effort: if it cannot reach PostgreSQL before its deadline, the original SQL can keep running until it finishes or Gunicorn's existing worker timeout intervenes. The cancellation sender itself no longer holds a worker after SQL finishes.

This stops abandoned SQL work; it does not limit requests from clients that remain connected, make deep pagination cheap, or interrupt Python code after a database query has completed. The separate chant-search pagination issue remains relevant.

The companion Nginx change allows two active expensive search requests across all clients and retains `proxy_ignore_client_abort off`. Its slot is released when the client leaves, before PostgreSQL necessarily finishes cancelling, so it is not a strict database concurrency bound. Deploy the application changes before enabling that limit. Melody search displays a busy message and a **Try again** button on HTTP 429, and handles server/network errors without leaving its loading prompt visible. It continues to send the newest melody immediately and abort the previous request; it does not queue or retry automatically.

The deployment playbook collects static files before updating Nginx. Both normal deployment and the standalone Nginx update refuse to replace the configuration unless the application enables this middleware and the collected melody script matches the current application file. The melody page uses a new script URL to bypass older cached copies. Already-open tabs still need a reload to load the new script.

A visitor loading the page during the application rollout, before static collection completes, can also receive the previous script under that URL and need a reload afterward. This short deployment window remains; the script URL change covers fresh page loads after collection.

Cancellation is not instantaneous. While another visitor occupies the other slot, repeated note/filter changes can receive 429 if the new request arrives before Nginx processes the previous request's disconnect. That search fails with the busy message; it does not complete after a short delay. The visitor must click **Try again** or change the search once capacity is available.

## Verification

Run the PostgreSQL regression tests in the local Docker stack:

```bash
docker compose up -d
docker compose exec -T django python manage.py test main_app.tests.test_search_cancellation
```

The tests cancel an active ten-second query, verify that an unrelated connection and the next request still work, exercise disconnects before execution and transaction cleanup, and check completed search results and source access. A local TCP proxy deliberately holds cancellation open while forwarding real SQL: tests verify that the sender closes when SQL finishes or the deadline expires, without leaving a watcher or reusing the abandoned database connection. A connected search also runs beyond the cancellation deadline and returns its result. An actual proxy test must also use Gunicorn: abort a slow browser XHR over HTTP/2 and confirm a new request reaches the same worker promptly. Cancelling a browser request without checking the server's work does not establish that database cancellation worked.
