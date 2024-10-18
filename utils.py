import logging
import os
from kubernetes import client, config
from prompt import generate_prompt
import openai 

logging.basicConfig(level=logging.DEBUG)


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


def get_agent_response(query):
    combined_info = aggregate_info()
    formatted_prompt = generate_prompt(combined_info, query)
    logging.info(f"Formatted Prompt: {formatted_prompt}")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": "You are a Kubernetes assistant. Answer the query based on the given information without any explanations."},
                {"role": "user", "content": formatted_prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        logging.error(f"Error in OpenAI API call: {str(e)}")
        return "Sorry, I encountered an error while processing your request."
