import logging
import re, os
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
from kubernetes.client import CustomObjectsApi, ApiextensionsV1Api
from kubernetes import client, config
from langchain import OpenAI

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s - %(message)s',
                    filename='agent.log', filemode='a')

app = Flask(__name__)

openai_key_api = ''


class QueryResponse(BaseModel):
    query: str
    answer: str


def get_kubeconfig_path():
    """
    Determines the location of the kubeconfig file.
    Checks if the kubeconfig file exists at the default path and logs its location.
    """
    kubeconfig_path = os.path.expanduser("~/.kube/config")

    if os.path.exists(kubeconfig_path):
        logging.info(f"Kubeconfig found at: {kubeconfig_path}")
    else:
        logging.warning(f"Kubeconfig file not found at: {kubeconfig_path}")

    return kubeconfig_path


def load_kube_config():
    """Load kubeconfig using the dynamically determined path."""
    config_path = get_kubeconfig_path()
    config.load_kube_config(config_file=config_path)


def get_cluster_info():
    load_kube_config()
    version_info = client.VersionApi().get_code()
    clientv1 = client.CoreV1Api()
    return {
        "kubernetes_version": version_info.git_version,
        "api_server_endpoint": config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION,
        "number_of_nodes": len(clientv1.list_node().items),
    }


def get_node_info():
    load_kube_config()
    clientv1 = client.CoreV1Api()
    nodes_info = {}
    nodes = clientv1.list_node()
    for node in nodes.items:
        node_name = node.metadata.name
        node_ip = node.status.addresses[0].address if node.status.addresses else "N/A"
        node_capacity = {k: v for k, v in node.status.capacity.items()}
        node_conditions = {condition.type: condition.status for condition in node.status.conditions}
        node_labels = node.metadata.labels
        nodes_info[node_name] = {
            "node_ip": node_ip,
            "node_maximum_capacity": node_capacity,
            "node_conditions": node_conditions,
            "node_labels": node_labels
        }
    return nodes_info


def get_namespace_info():
    load_kube_config()
    clientv1 = client.CoreV1Api()
    namespaces = clientv1.list_namespace()
    namespace_details = {}
    for ns in namespaces.items:
        name = ns.metadata.name
        quota = clientv1.list_namespaced_resource_quota(namespace=name)
        limits = clientv1.list_namespaced_limit_range(namespace=name)
        namespace_details[name] = {
            "resource_quotas": quota.items,
            "limits": limits.items,
        }
    return namespace_details


def get_workload_info():
    load_kube_config()
    apps_v1 = client.AppsV1Api()
    batch_v1 = client.BatchV1Api()
    workloads = {
        "deployments": apps_v1.list_deployment_for_all_namespaces().items,
        "statefulsets": apps_v1.list_stateful_set_for_all_namespaces().items,
        "daemonsets": apps_v1.list_daemon_set_for_all_namespaces().items,
        "jobs": batch_v1.list_job_for_all_namespaces().items,
        "cronjobs": batch_v1.list_cron_job_for_all_namespaces().items,
    }
    return workloads


def get_service_info():
    load_kube_config()
    clientv1 = client.CoreV1Api()
    services = clientv1.list_service_for_all_namespaces()
    service_details = {}
    for service in services.items:
        name = service.metadata.name
        namespace = service.metadata.namespace
        service_type = service.spec.type
        cluster_ip = service.spec.cluster_ip
        if namespace not in service_details:
            service_details[namespace] = []
        service_details[namespace].append({
            "service_name": name,
            "service_type": service_type,
            "cluster_ip": cluster_ip
        })
    return service_details


def get_pod_info():
    load_kube_config()
    clientv1 = client.CoreV1Api()
    pods = clientv1.list_pod_for_all_namespaces()
    pod_details = {}

    for pod in pods.items:
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name
        qos_class = pod.status.qos_class
        restart_policy = pod.spec.restart_policy
        init_containers = len(pod.spec.init_containers) if pod.spec.init_containers else 0

        env_vars = []
        volume_mounts = []

        for container in pod.spec.containers:
            if container.env:
                env_vars.extend([{env_var.name: env_var.value} for env_var in container.env])
            if container.volume_mounts:
                volume_mounts.extend([{
                    "container_name": container.name,
                    "mount_path": mount.mount_path
                } for mount in container.volume_mounts])

        if namespace not in pod_details:
            pod_details[namespace] = []

        pod_details[namespace].append({
            "pod_name": pod_name,
            "qos_class": qos_class,
            "restart_policy": restart_policy,
            "init_containers": init_containers,
            "env_vars": env_vars,
            "volume_mounts": volume_mounts
        })

    return pod_details


def get_container_info(pod_info):
    load_kube_config()
    container_details = {}
    for namespace, pods in pod_info.items():
        for pod in pods:
            pod_name = pod["pod_name"]
            containers = client.CoreV1Api().read_namespaced_pod(name=pod_name, namespace=namespace).spec.containers
            container_details[pod_name] = [{
                "container_name": container.name,
                "image": container.image,
                "ports": [port.container_port for port in container.ports] if container.ports else []
            } for container in containers]

    return container_details


def get_pod_env_vars():
    load_kube_config()
    clientv1 = client.CoreV1Api()
    pods = clientv1.list_pod_for_all_namespaces()
    env_details = {}

    for pod in pods.items:
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name

        if namespace not in env_details:
            env_details[namespace] = []

        env_vars = {}
        for container in pod.spec.containers:
            if container.env:
                for env_var in container.env:
                    env_vars[env_var.name] = env_var.value

        env_details[namespace].append({
            "pod_name": pod_name,
            "env_vars": env_vars
        })

    return env_details


def aggregate_info():
    cluster_info = get_cluster_info()
    node_info = get_node_info()
    namespace_info = get_namespace_info()
    workload_info = get_workload_info()
    service_info = get_service_info()
    pod_info = get_pod_info()
    container_info = get_container_info(pod_info)
    env_info = get_pod_env_vars()

    combined_info = {
        "Cluster Information": cluster_info,
        "Node Information": node_info,
        "Namespace Information": namespace_info,
        "Workload Information": workload_info,
        "Service Information": service_info,
        "Pod Information": pod_info,
        "Container Information": container_info,
        "Environment Variables": env_info
    }

    return combined_info


def generate_prompt(combined_info, query):
    cluster_info = combined_info.get("Cluster Information", {})
    node_info = combined_info.get("Node Information", {})
    namespace_info = combined_info.get("Namespace Information", {})
    workload_info = combined_info.get("Workload Information", {})
    service_info = combined_info.get("Service Information", {})
    pod_info = combined_info.get("Pod Information", {})
    container_info = combined_info.get("Container Information", {})
    hpa_info = combined_info.get("HPA Information", "N/A")
    storage_driver = combined_info.get("Storage Driver", "N/A")
    scheduler_info = combined_info.get("Scheduler Information", "N/A")

    node_info_str = "\n".join([f"- {node}: {details}" for node, details in node_info.items()])
    namespace_info_str = "\n".join([f"- {namespace}: {details}" for namespace, details in namespace_info.items()])
    workload_info_str = "\n".join([f"- {workload_type}: {len(items)} items" for workload_type, items in workload_info.items()])
    service_info_str = "\n".join([f"- {namespace}: {services}" for namespace, services in service_info.items()])
    pod_info_str = "\n".join([f"- {namespace}: {pods}" for namespace, pods in pod_info.items()])
    container_info_str = "\n".join([f"- {pod}: {containers}" for pod, containers in container_info.items()])

    prompt_template = f"""
    You are a Kubernetes expert. Here is the detailed cluster information:

    Cluster Information:
    - Kubernetes Version: {cluster_info.get('kubernetes_version')}
    - API Server Endpoint: {cluster_info.get('api_server_endpoint')}
    - Number of Nodes: {cluster_info.get('number_of_nodes')}

    Node Information:
    {node_info_str}

    Namespace Information:
    {namespace_info_str}

    Workload Information:
    {workload_info_str}

    Service Information:
    {service_info_str}

    Pod Information:
    {pod_info_str}

    Container Information:
    {container_info_str}

    HPA Information:
    {hpa_info}

    Storage Driver:
    {storage_driver}

    Scheduler Information:
    {scheduler_info}

    Query: {query}
    Answer:
    """

    return prompt_template


def get_agent_response(query):
    combined_info = aggregate_info()
    formatted_prompt = generate_prompt(combined_info, query)
    logging.info(f"Formatted Prompt: {formatted_prompt}")

    openai_llm = OpenAI(temperature=0.3, openai_api_key=openai_key_api)
    llm_response = openai_llm(formatted_prompt)
    return llm_response.strip()


@app.route('/query', methods=['POST'])
def create_query():
    try:
        request_data = request.json
        query = request_data.get('query')
        logging.info(f"Received query: {query}")

        answer = get_agent_response(query)
        logging.info(f"Generated answer: {answer}")

        response = QueryResponse(query=query, answer=answer)
        return jsonify(response.dict())

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
