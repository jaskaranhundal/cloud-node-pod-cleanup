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

##📝 Configuration**
  
Edit control_and_cleanup.py:
```bash
PARTIAL_SERVER_NAME = "node2"
CLOUD_NAME = "otc"
NAMESPACES = ["lindera-production", "lindera-testing", "lindera-development"]
```



