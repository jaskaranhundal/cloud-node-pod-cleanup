import openstack
import pytz
import sys
import logging
from datetime import datetime
import time
import re
from kubernetes import client, config

# --- Configurations ---
BERLIN_TZ = pytz.timezone("Europe/Berlin")
LOG_FILE = "server_control.log"
KUBE_LOG_FILE = "k8s_cleanup.log"
PARTIAL_SERVER_NAME = "node2"
CLOUD_NAME = "otc"

NAMESPACES = ["lindera-production", "lindera-testing", "lindera-development"]

# --- Setup logging ---
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

def log(msg):
    print(msg)
    logging.info(msg)

# --- OpenStack ---
def connect():
    return openstack.connect(cloud=CLOUD_NAME)

def find_servers(conn, partial_name):
    servers_found = []
    for server in conn.compute.servers():
        if partial_name in server.name:
            servers_found.append(server)
    return servers_found

def wait_for_server_status(conn, server_id, desired_status, timeout=300, poll_interval=10):
    waited = 0
    while waited < timeout:
        server = conn.compute.get_server(server_id)
        if server.status.lower() == desired_status.lower():
            return True
        time.sleep(poll_interval)
        waited += poll_interval
    return False

def stop_server():
    conn = connect()
    servers = find_servers(conn, PARTIAL_SERVER_NAME)
    if not servers:
        log(f"No servers found with name containing '{PARTIAL_SERVER_NAME}'")
        return
    for server in servers:
        if server.status.lower() != "shutoff":
            conn.compute.stop_server(server.id)
            log(f"Stopping server: {server.name}")
        else:
            log(f"Server already stopped: {server.name}")

def get_server_ip(conn, server):
    addresses = server.addresses
    for network in addresses.values():
        for addr_info in network:
            # Usually fixed IP is private/internal IP
            if addr_info.get('OS-EXT-IPS:type') == 'fixed':
                return addr_info['addr']
    return None

def is_node_ready(node_name):
    try:
        v1 = client.CoreV1Api()
        node = v1.read_node(name=node_name)
        for condition in node.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
    except Exception as e:
        log(f"Failed to get node status for {node_name}: {e}")
    return False

def wait_for_node_ready(node_name, timeout=600, poll_interval=10):
    waited = 0
    while waited < timeout:
        if is_node_ready(node_name):
            return True
        time.sleep(poll_interval)
        waited += poll_interval
    return False

def start_server():
    conn = connect()
    servers = find_servers(conn, PARTIAL_SERVER_NAME)
    if not servers:
        log(f"No servers found with name containing '{PARTIAL_SERVER_NAME}'")
        return

    # Setup Kubernetes client once here
    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
    except Exception as e:
        log(f"Failed to load Kubernetes config: {e}")
        return

    v1 = client.CoreV1Api()

    for server in servers:
        if server.status.lower() == "shutoff":
            conn.compute.start_server(server.id)
            log(f"Starting server: {server.name} ...")
            if wait_for_server_status(conn, server.id, "active"):
                log(f"Server {server.name} is active.")
                server_ip = get_server_ip(conn, server)
                if not server_ip:
                    log(f"Could not determine IP for server {server.name}. Proceeding with pod cleanup.")
                    cleanup_duplicate_pods()
                    continue

                # Find node name by IP
                node_name = None
                try:
                    nodes = v1.list_node().items
                    for node in nodes:
                        for addr in node.status.addresses:
                            if addr.address == server_ip:
                                node_name = node.metadata.name
                                break
                        if node_name:
                            break
                except Exception as e:
                    log(f"Failed to list nodes: {e}")
                    cleanup_duplicate_pods()
                    continue

                if not node_name:
                    log(f"Node with IP {server_ip} not found in cluster. Proceeding with pod cleanup.")
                    cleanup_duplicate_pods()
                    continue

                log(f"Waiting for node '{node_name}' to become Ready...")
                if wait_for_node_ready(node_name):
                    log(f"Node '{node_name}' is Ready. Starting pod cleanup.")
                    cleanup_duplicate_pods()
                else:
                    log(f"Timeout waiting for node '{node_name}' to become Ready. Skipping pod cleanup.")
            else:
                log(f"Timeout waiting for server {server.name} to become active.")
        else:
            log(f"Server already running: {server.name}")
            cleanup_duplicate_pods()

# --- Kubernetes cleanup ---
def get_base_name(pod_name):
    parts = pod_name.split('-')
    base = parts[0]
    for i in range(1, len(parts)):
        if len(parts[i]) < 4 or not re.match(r'^[a-z0-9]+$', parts[i]):
            base += '-' + parts[i]
        else:
            break
    return base

def cleanup_duplicate_pods():
    k8s_logger = logging.getLogger("k8s_cleanup")
    k8s_logger.setLevel(logging.INFO)
    if not k8s_logger.hasHandlers():
        k8s_handler = logging.FileHandler(KUBE_LOG_FILE)
        k8s_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        k8s_logger.addHandler(k8s_handler)

    def klog(msg):
        print(msg)
        k8s_logger.info(msg)

    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
    except Exception as e:
        klog(f"Failed to load Kubernetes config: {e}")
        return

    v1 = client.CoreV1Api()
    pod_groups = {}

    for ns in NAMESPACES:
        try:
            pods = v1.list_namespaced_pod(namespace=ns).items
        except Exception as e:
            klog(f"Failed to list pods in namespace {ns}: {e}")
            continue

        for pod in pods:
            if not pod.status.start_time or not pod.status.host_ip:
                continue

            name = pod.metadata.name
            age_seconds = (datetime.now(pytz.UTC) - pod.status.start_time).total_seconds()
            node_ip = pod.status.host_ip
            base_name = get_base_name(name)
            key = f"{ns}:{base_name}"
            pod_groups.setdefault(key, []).append({
                "namespace": ns,
                "name": name,
                "node_ip": node_ip,
                "age": age_seconds
            })

    pods_to_delete = []
    for group, pod_list in pod_groups.items():
        node_ips = set(p["node_ip"] for p in pod_list)
        if len(pod_list) > 1 and len(node_ips) <= 2:
            pod_list_sorted = sorted(pod_list, key=lambda x: x["age"])
            to_delete = pod_list_sorted[0]
            pods_to_delete.append((to_delete["namespace"], to_delete["name"]))

    if not pods_to_delete:
        klog("No duplicate pods with short uptime found to delete.")
    else:
        klog("Pods to delete (namespace \t pod name):")
        for ns, pod in pods_to_delete:
            klog(f"{ns}\t{pod}")
        klog("")
        for ns, pod in pods_to_delete:
            try:
                v1.delete_namespaced_pod(name=pod, namespace=ns, grace_period_seconds=0)
                klog(f"Deleted pod {pod} successfully.")
            except Exception as e:
                klog(f"Failed to delete pod {pod}: {e}")
            klog("")

# --- Main execution ---
def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ["start", "stop"]:
        print("Usage: python control_and_cleanup.py [start|stop]")
        sys.exit(1)

    action = sys.argv[1]
    log(f"Script called with action: {action}")

    if action == "start":
        start_server()
    elif action == "stop":
        stop_server()

if __name__ == "__main__":
    main()
