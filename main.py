import logging
import re
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
from kubernetes.client import CustomObjectsApi, ApiextensionsV1Api
from kubernetes import client, config
from langchain import OpenAI, LLMChain, PromptTemplate

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s - %(message)s',
                    filename='agent.log', filemode='a')

app = Flask(__name__)

openai_key_api = ''


class QueryResponse(BaseModel):
    query: str
    answer: str


def get_cluster_info():
    config.load_kube_config()
    version_info = client.VersionApi().get_code()
    clientv1 = client.CoreV1Api()
    return {
        "kubernetes_version": version_info.git_version,
        "api_server_endpoint": config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION,
        "number_of_nodes": len(clientv1.list_node().items),
    }


def get_node_info():
    config.load_kube_config()
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
            "node_capacity": node_capacity,
            "node_conditions": node_conditions,
            "node_labels": node_labels
        }
    return nodes_info


def get_namespace_info():
    config.load_kube_config()
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
    config.load_kube_config()
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
    config.load_kube_config()
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


def aggregate_info():
    """
    Collect information from all the different functions and return a combined single string.
    """

    cluster_info = get_cluster_info() or {"kubernetes_version": "N/A", "api_server_endpoint": "N/A",
                                          "number_of_nodes": "N/A"}
    node_info = get_node_info() or {}
    namespace_info = get_namespace_info() or {}
    #workload_info = get_workload_info() or {}
    service_info = get_service_info() or {}
    # storage_info = get_storage_info() or {}
    # rbac_info = get_rbac_info() or {}
    # config_secrets_info = get_config_secrets_info() or {}
    # custom_resource_info = get_custom_resource_info() or {}

    combined_info = f"""
    Cluster Information:
    - Kubernetes Version: {cluster_info.get('kubernetes_version')}
    - API Server Endpoint: {cluster_info.get('api_server_endpoint')}
    - Number of Nodes: {cluster_info.get('number_of_nodes')}

    Node Information:
    {node_info}

    Namespace Information:
    {namespace_info}


    Service Information:
    {service_info}

    """
    return combined_info


def get_agent_response(query):
    combined_info = aggregate_info()

    print("---combined info-----", combined_info)
    prompt_template = f"""
        You are a Kubernetes expert. Here is the detailed cluster information:
        {combined_info}

        Query: {query}
        Answer:
    """

    openai_llm = OpenAI(temperature=0.3, openai_api_key=openai_key_api)

    llm_response = openai_llm(prompt_template)

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
