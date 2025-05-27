# 🖥️ OpenStack Server Control & Kubernetes Pod Cleanup

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)

This script allows controlled **start/stop of OpenStack servers** and performs **Kubernetes pod cleanup** to ensure only valid instances are retained after node transitions.

---

## 📌 Features

- ✅ Start or stop OpenStack servers (by partial name match, e.g., `node2`)
- ✅ Wait for server to reach desired status (`ACTIVE`/`SHUTOFF`)
- ✅ Clean up short-lived duplicate pods in specified Kubernetes namespaces
- ✅ Logs all actions for audit and debugging
- ✅ Cron-friendly CLI interface

---

## ⚙️ Setup

### 🔧 Prerequisites

Ensure the following are installed:

- Python 3.6+
- `openstacksdk`, `kubernetes`, `pytz`
- Access to:
  - An OpenStack environment via `clouds.yaml`
  - A Kubernetes cluster (in-cluster or via kubeconfig)

Install dependencies:

```bash
pip install -r requirements.txt
```

## 📝 Configuration
Edit `control_and_cleanup.py`:
```bash
PARTIAL_SERVER_NAME = "node2"
CLOUD_NAME = "otc"
NAMESPACES = ["lindera-production", "lindera-testing", "lindera-development"]
```
---
## 🚀 Usage
- Start Server + Clean Up Pods

```bash
python control_and_cleanup.py start
```

- Stop Server

```bash
python control_and_cleanup.py stop
```
- Help

```bash
python control_and_cleanup.py 
# Output: Usage: python control_and_cleanup.py [start|stop]
```
---
## 🧼 Kubernetes Cleanup Logic
- Identifies pods with the same "base name"
- Checks pods on duplicate nodes or across node transitions
- Deletes the youngest duplicate pod (based on age)
---

## 📝 Crontab Example
To automate server control (Berlin timezone example):
```bash
# Start server Mon–Fri at 07:00
0 7 * * 1-5 /usr/bin/python3 /path/to/control_and_cleanup.py start

# Stop server Mon–Fri at 19:00
0 19 * * 1-5 /usr/bin/python3 /path/to/control_and_cleanup.py stop

```
---
## 📂 Project Structure

```bash
.
├── control_and_cleanup.py     # Main script
├── README.md                  # This file
├── requirements.txt           # Dependencies
├── server_control.log         # Server operations log (runtime)
└── k8s_cleanup.log            # Kubernetes cleanup log (runtime)

```
---
