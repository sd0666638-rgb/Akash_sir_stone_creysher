# Stone Crusher Windows Launcher

The project root contains four one-click Windows files:

- `Start Stone Crusher.cmd` checks MySQL, applies database migrations, starts
  the backend and frontend, waits for both health checks, and opens the app.
- `Stop Stone Crusher.cmd` stops only processes previously started by this
  launcher. It never stops MySQL because the database service may be shared.
- `Stone Crusher Control.cmd` opens a menu for start, stop, status, browser,
  logs, and Desktop shortcut actions.
- `Create Desktop Shortcuts.cmd` adds Start, Stop, and Control shortcuts to
  the current Windows user's Desktop.

Keep the `.cmd` files in the project root. To put controls on the Desktop,
double-click `Create Desktop Shortcuts.cmd`; use the generated shortcuts
instead of copying an individual `.cmd` file away from the project.

## Safety and state

Runtime PID metadata and logs are stored under `.stone-runtime`. Before a
process is stopped, its PID, creation time, executable, command token, and
project location are verified. A reused PID or an application already using
ports 8000/5173 is reported and left untouched. The launcher never kills all
Node.js or Python processes.

If another terminal started the project, the status screen labels those
ports as `untracked`. Close that original terminal/process first; the launcher
will not adopt or terminate it.

## Requirements

Before the first start, complete the main installation guide so these exist:

- `.env` with a `DATABASE_URL` beginning with `mysql+pymysql://`
- `backend\venv\Scripts\python.exe` and installed backend requirements
- Node.js in `PATH`
- `frontend\node_modules` from `npm.cmd install`
- MySQL 8.0 and the configured database/user

For a local database, the launcher checks the MySQL Windows service and tries
to start it. Windows may show an Administrator approval prompt when required.
For a remote MySQL host, start the database separately.

## Logs and troubleshooting

Choose **Open logs** from the control menu, or open:

```text
.stone-runtime\logs
```

Each start has separate backend/frontend output and error logs. The controller
also writes `controller.log`. If a start fails after launching one component,
the launcher safely rolls back only the components that it just started.
