# Install Stone Crusher ERP on another Windows PC

This guide installs the application directly on Windows with a local MySQL
server. It does not use SQLite. If MySQL is missing, the included setup can
install MySQL Community Server and its required Configurator through Windows
Package Manager. It does not install MySQL Workbench.

## 1. Before copying the project

The project folder contains application code, but the business records are
stored separately in MySQL. Decide whether the new PC needs a fresh database or
an existing database copied from the old PC.

This separation is important: copying only the source-code folder does **not**
copy customers, materials, invoices, payments, users, or company Settings. The
editable shop/GST/bank Settings are database records too, so they move with a
MySQL backup and restore—not with the source code.

Do **not** copy these machine-specific or private items:

- `.env` (contains passwords and the application signing secret)
- `backend\venv`
- `backend\stone_dev.db` (preserved legacy SQLite data; the application does not use it)
- `frontend\node_modules`
- `frontend\dist`
- Python cache folders such as `__pycache__` and `.pytest_cache`

Copy the rest of the project folder using a trusted USB drive, local network, or
private archive. Keep the project in a simple writable path, for example:

```text
C:\StoneERP
```

Do not put a production copy inside a public cloud-synchronised folder.

### If existing business data must move too

On the old PC, create a MySQL dump. Do not put the password after `-p`; MySQL
will request it without showing it:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe" `
  --host=127.0.0.1 --port=3306 --user=stone_app -p `
  --single-transaction --routines --triggers `
  --result-file="C:\Backup\stone_creysher.sql" stone_creysher
```

Store the dump securely because it contains customer, invoice, and payment
information. The restore procedure is described later in this guide.

## 2. Install the prerequisites

Install Python and Node.js before running the project:

1. **64-bit Python 3.10 or newer**
   - Enable the installer option **Add Python to PATH**.
   - Keep the Python launcher (`py.exe`) enabled.
2. **Node.js 18 or newer, including npm**
   - The current Node.js LTS release is recommended.
MySQL Server 8.0 or newer can either be installed beforehand or installed by
`Setup New Computer.cmd`. The guided setup installs the official
`Oracle.MySQL` Community Server package only (plus its required Configurator);
Workbench and other optional GUI products are not installed.

During MySQL Configurator:

- use TCP port `3306` unless another local program already uses it;
- create and remember the MySQL `root` password; and
- configure MySQL as an automatically started Windows service.

The setup only supports MySQL for an installed system. MySQL Workbench is
optional but useful for backups and database inspection.

Open a new PowerShell window after installing the prerequisites so updated PATH
entries are available.

## 3. Check the new PC without changing it

From the copied project folder:

```powershell
Set-Location C:\StoneERP
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup\setup-windows.ps1 -CheckOnly
```

`-CheckOnly` is read-only. It checks Python, Node.js, npm, the MySQL command-line
client, detected MySQL Windows services, and TCP port 3306. It does not install
packages, create files, alter databases, or start/stop services. A missing MySQL
installation is reported as an error with instructions to run the guided setup.

If `mysql.exe` is installed but not found, add its `bin` directory to PATH or
use the default MySQL Server 8.0 installation location:

```text
C:\Program Files\MySQL\MySQL Server 8.0\bin
```

## 4. Fresh installation: configure and install

For the simplest guided setup, double-click:

```text
Setup New Computer.cmd
```

The wrapper opens the same PowerShell setup described below and keeps the window
open if an error needs attention. If MySQL is missing, answer **Yes** to install
MySQL Community Server, complete MySQL Configurator, and return to the setup
window. Internet access and Windows administrator approval are required for
this one-time installation.

To explicitly request the server installation from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup\setup-windows.ps1 `
  -InstallMySqlServer -ConfigureDatabase
```

Once MySQL is installed and running, execute:

```powershell
Set-Location C:\StoneERP
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup\setup-windows.ps1 -ConfigureDatabase
```

The script will:

1. verify the required software versions;
2. offer to install MySQL Community Server if it is missing;
3. request the existing MySQL administrator password in a hidden prompt;
4. request a new password for the dedicated `stone_app` database user;
5. create the `stone_creysher` database if it does not exist;
6. create or update only the dedicated local `stone_app` MySQL account;
7. request the first ERP administrator password;
8. create `.env` from the safe `.env.example`;
9. generate a random application signing secret;
10. create `backend\venv` and install Python packages;
11. install exact frontend packages from `package-lock.json`; and
12. apply all Alembic migrations to MySQL.

Passwords do not appear in command-line arguments. Database passwords with
special characters are URL-encoded automatically in `DATABASE_URL`.

The script will not overwrite an existing `.env`. If this is an intentional
reconfiguration, use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup\setup-windows.ps1 `
  -ConfigureDatabase -ForceEnvironment
```

The previous `.env` is copied to a timestamped backup under
`%LOCALAPPDATA%\StoneCrusherERP\environment-backups` first. Delete that backup
securely after verifying the replacement configuration.

### Different local names or port

The defaults are recommended, but they can be changed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup\setup-windows.ps1 `
  -ConfigureDatabase `
  -MySqlHost 127.0.0.1 `
  -MySqlPort 3307 `
  -DatabaseName stone_creysher `
  -DatabaseUser stone_app `
  -FirstAdminUsername admin
```

Database, user, and administrator names intentionally accept only simple safe
characters. The provisioning mode creates local grants for `localhost` and
`127.0.0.1`; it does not expose the database user to other computers.

## 5. Restore an existing database

Complete the fresh setup first so the database and user exist. Stop the backend
if it is running. Copy the SQL dump to a private path on the new PC, then restore
it using MySQL's `source` command:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" `
  --host=127.0.0.1 --port=3306 --user=stone_app -p `
  --database=stone_creysher `
  --execute="source C:/Backup/stone_creysher.sql"
```

Use forward slashes in the `source` path. After restoring, reapply any newer
application migrations:

```powershell
Set-Location C:\StoneERP\backend
.\venv\Scripts\python.exe -m alembic upgrade head
```

Never restore a production dump over a database containing records that must be
kept. Create and verify a current backup first.

Company Settings are included in the dump. After restoration, the shop name,
GSTIN, address, jurisdiction, and bank details should match the old PC.

## 6. Docker Desktop alternative

Docker is optional and is an alternative to the direct Windows/MySQL setup
above. Do not mix the two database methods unless you deliberately assign
different ports and understand which database contains the live records.

Install Docker Desktop, copy `.env.example` to `.env`, and replace every
placeholder secret—especially:

- `SECRET_KEY`
- `COMPOSE_MYSQL_ROOT_PASSWORD`
- `COMPOSE_MYSQL_PASSWORD`
- `FIRST_ADMIN_PASSWORD`

Then run from the project root:

```powershell
docker compose up --build
```

Open `http://localhost:5173`. Docker stores MySQL records in the named
`mysql_data` volume, not in the source files. Back up the database before
removing Docker volumes. If the local Windows MySQL service already owns port
3306, either stop it manually while Docker is in use or deliberately change the
host-side database port mapping in `docker-compose.yml`. The setup script never
stops the service for you.

To stop the containers without deleting the database volume:

```powershell
docker compose down
```

Do not add `--volumes` unless permanent deletion of the Docker MySQL data is
explicitly intended and a verified backup exists.

## 7. Start the application

Open two PowerShell windows.

In window 1, start the API:

```powershell
Set-Location C:\StoneERP\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app `
  --host 127.0.0.1 --port 8000
```

In window 2, start the web interface:

```powershell
Set-Location C:\StoneERP\frontend
npm.cmd run dev
```

Open:

- Web interface: `http://localhost:5173`
- API health check: `http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`

Sign in with the first administrator username and password entered during setup.
After login, use the gear icon in the top-right corner to configure the actual
company/shop name, address, GSTIN, state, jurisdiction, and bank details used on
PDF invoices.

For normal use after setup, the root-level launch controls are also available:

- `Start Stone Crusher.cmd` starts the local application.
- `Stone Crusher Control.cmd` opens the status/start/stop control menu.
- `Stop Stone Crusher.cmd` stops application processes started by the launcher.
- `Create Desktop Shortcuts.cmd` adds convenient Windows shortcuts.

These launchers do not replace MySQL backups.

## 8. Validate the installation

Backend tests:

```powershell
Set-Location C:\StoneERP\backend
.\venv\Scripts\python.exe -m pytest
```

Frontend checks:

```powershell
Set-Location C:\StoneERP\frontend
npm.cmd run lint
npm.cmd run build
```

Also perform this short business check:

1. create a temporary customer with a unique 10-digit mobile number;
2. add or select a material with enough stock;
3. create an invoice and open its PDF;
4. record a partial payment and confirm the remaining balance;
5. confirm the reports show the sale and outstanding amount; and
6. cancel/remove only the temporary records according to normal application
   rules.

## 9. Updating a copied installation

Before replacing application files:

1. stop the API and frontend terminals;
2. make a MySQL backup;
3. keep the current `.env` in a secure backup location;
4. copy the new code without copying another PC's `.env`, `venv`, or
   `node_modules`;
5. rerun the setup script without `-ConfigureDatabase`.

When `.env`, MySQL, and the existing dependency folders are already present:

```powershell
Set-Location C:\StoneERP
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup\setup-windows.ps1
```

This preserves `.env`, refreshes dependencies, and applies pending migrations.

## Troubleshooting

### PowerShell says script execution is disabled

Use the documented `powershell.exe -ExecutionPolicy Bypass -File ...` command.
It changes policy only for that process and does not weaken the machine-wide
execution policy.

### Python, Node.js, npm, or MySQL is not found

Close PowerShell, reopen it, and rerun `-CheckOnly`. If MySQL is not installed,
run `Setup New Computer.cmd` and accept the server-only installation. If MySQL
was installed but remains undetected, confirm that its `bin` directory contains
`mysql.exe`. The setup also checks the standard MySQL Server 8.0 and 8.4
installation folders even when they are not on PATH.

### Port 3306 is not accepting connections

Open Windows **Services**, find the MySQL service (commonly `MySQL80`), and start
it manually. If it fails, use MySQL Installer or Windows Event Viewer to inspect
the service error. The setup script intentionally does not change services.

### MySQL reports access denied

Verify the MySQL administrator username and password. They are separate from
the ERP administrator login. If the dedicated user already exists and its
password should not be reset, preserve `.env` and configure the account manually
in MySQL Workbench instead of using `-ForceEnvironment`.

### Alembic cannot connect

Confirm that `.env` contains a MySQL URL beginning with:

```text
mysql+pymysql://
```

Check the host, port, database name, user, and password. If the password was
entered manually, reserved URL characters such as `@`, `:`, `/`, `#`, and `%`
must be percent-encoded. The setup script handles this automatically.

### Frontend opens but API calls fail

Confirm the API is running at `http://localhost:8000`. For a non-default API
address, create `frontend\.env.local` containing:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart `npm.cmd run dev` after changing frontend environment values.

## Security and backups

- Never share `.env`, database dumps, or MySQL passwords in chat or email.
- Do not use the example passwords from `.env.example`.
- Give each operator their own ERP account when user management is available.
- Keep MySQL bound to the local PC unless a qualified administrator configures
  network access, firewall rules, TLS, and least-privilege grants.
- Make scheduled MySQL backups and regularly test a restore on a separate
  database.
- Protect the Windows user account with a strong password and device encryption.
