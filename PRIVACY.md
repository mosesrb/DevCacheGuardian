# Privacy & Data Transparency Notice

> **Last Updated:** 2026-08-20  
> **Applicable Software:** DevCache Guardian (Desktop Application)

DevCache Guardian is an open-source, local-first utility built specifically for software developers. We believe privacy is not just a policy—it is an architectural guarantee.

---

## 1. Zero Telemetry & 100% Offline Operation

- **No Remote Servers**: DevCache Guardian does not connect to any remote server or third-party service during normal operation.
- **No Analytics or Tracking**: We do not collect, track, or transmit usage metrics, click analytics, hardware IDs, IP addresses, or personal identifiers.
- **No Account Required**: The application does not require user registration, logins, or authentication tokens.

---

## 2. Local Data Storage

All data created or managed by DevCache Guardian resides strictly on your local machine under your user directory (`~/.devcache_guardian/`):

- **`guardian.db`**: Local SQLite database storing your scan snapshots, cleanup history, and local UI preferences.
- **`backups/`**: Pre-deletion backup archives of preserved configuration files (created only when you request a backup).
- **`logs/`**: Rotating local application logs kept for troubleshooting (retained for 30 days locally, never transmitted).

---

## 3. Filesystem & Cache Scanning

When scanning your system, DevCache Guardian only inspects specific known cache directories and build artifacts. It adheres to strict safety boundaries:

- **No File Content Harvesting**: The application never reads, stores, or transmits the contents of your source code, environment secrets, private keys, or personal files.
- **Content Analyzer Guardrail**: Pre-deletion analysis only checks file names and file headers locally to detect and prevent accidental deletion of sensitive configuration files (`gradle.properties`, `config.json`, `.pem`, etc.).

---

## 4. Software License & Liability

DevCache Guardian is released as free software under the **GNU General Public License v3.0 (GPLv3)**.

- As outlined in Sections 15 and 16 of the GPLv3, the software is provided **"AS IS" WITHOUT WARRANTY OF ANY KIND**, either expressed or implied.
- You maintain complete control over all deletion operations. Always review the itemized cleanup forecast before executing any cleanup.

---

## 5. Contact & Source Code

Because DevCache Guardian is fully open source, the entire codebase and build pipeline are open for inspection:

- **Source Code**: [https://github.com/mosesrb/DevCacheGuardian](https://github.com/mosesrb/DevCacheGuardian)
- **License**: [GPLv3 License](LICENSE)
