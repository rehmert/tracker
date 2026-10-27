# Tracker Eastern Time startup patch

Based on the working **projection exclusions** release. Changes only `app/main.py`.

- Sets the Uvicorn application process local timezone to `America/New_York` at import/startup.
- Existing `datetime.now()` and `date.today()` calls use Eastern Time (EST/EDT) on Linux.
- Does **not** modify or migrate the SQLite database or rewrite existing event times.
- Does **not** modify dashboard, calendar, protocol exclusion, dose, or PK source code.
- Explicit UTC backup timestamps and SQLite `CURRENT_TIMESTAMP` remain UTC.
- Does **not** make PK elapsed-time arithmetic across daylight-saving transitions timezone-aware; that requires a separate change.

## Install

Stop service and back up the entire installation including database first:

    sudo systemctl stop tracker
    sudo tar -czf /root/tracker-before-eastern-$(date +%Y%m%d-%H%M%S).tar.gz -C /opt tracker

Extract the patch from within `/opt/tracker`:

    cd /opt/tracker
    sudo unzip -o /path/to/tracker-eastern-time-minimal-patch.zip -d /opt/tracker
    sudo chown tracker:tracker /opt/tracker/app/main.py
    sudo systemctl start tracker

Verify timezone in the service process (replace PID as needed):

    PID=$(systemctl show -p MainPID --value tracker)
    sudo tr '\0' '\n' < /proc/$PID/environ | grep '^TZ=' || true

Note: `/proc/$PID/environ` can show the initial environment rather than Python's
runtime `os.environ` modifications. The reliable functional check is to compare
Tracker's current date/time default fields to the current Eastern clock.
