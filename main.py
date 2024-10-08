import logging
import re
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
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


def get_all_cluster_info():
    """
    Function to return a JSON with detailed information including nodes, namespaces,
    their pods, pod status, services, logs, and resource information.
    """
    try:
        config.load_kube_config()
        clientv1 = client.CoreV1Api()
        node_details = {}

        # Fetch Nodes and their Status
        try:
            nodes = clientv1.list_node()
            for node in nodes.items:
                node_name = node.metadata.name
                node_status = {condition.type: condition.status for condition in node.status.conditions}
                node_details[node_name] = {"namespaces": {}, "node_status": node_status}
        except client.exceptions.ApiException as e:
            if e.status == 403:
                logging.warning(f"Permission denied when accessing nodes. Error: {e}")
                node_details = None

        # Fetch Pods
        try:
            all_pods = clientv1.list_pod_for_all_namespaces()
        except client.exceptions.ApiException as e:
            if e.status == 403:
                logging.warning(f"Permission denied when accessing pods. Error: {e}")
                return {"nodes": node_details, "pods": None}

        for pod in all_pods.items:
            pod_name = pod.metadata.name
            pod_status = pod.status.phase
            namespace = pod.metadata.namespace
            node_name = pod.spec.node_name

            if not node_name:
                continue

            try:
                pod_logs = clientv1.read_namespaced_pod_log(name=pod_name, namespace=namespace)
            except client.exceptions.ApiException as e:
                if e.status == 403:
                    logging.warning(f"Permission denied when accessing logs for pod {pod_name} in namespace {namespace}.")
                    pod_logs = None

            resource_info = []
            for container in pod.spec.containers:
                resources = container.resources
                requests = resources.requests if resources.requests else {}
                limits = resources.limits if resources.limits else {}
                resource_info.append({
                    "container_name": container.name,
                    "requests": requests,
                    "limits": limits
                })

            if node_name in node_details:
                if namespace not in node_details[node_name]["namespaces"]:
                    node_details[node_name]["namespaces"][namespace] = []

                node_details[node_name]["namespaces"][namespace].append({
                    "pod_name": pod_name,
                    "status": pod_status,
                    "logs": pod_logs,
                    "resources": resource_info
                })

        # Fetch Services
        services_details = {}
        try:
            services = clientv1.list_service_for_all_namespaces()
            for service in services.items:
                service_name = service.metadata.name
                namespace = service.metadata.namespace
                cluster_ip = service.spec.cluster_ip

                if namespace not in services_details:
                    services_details[namespace] = []

                services_details[namespace].append({
                    "service_name": service_name,
                    "cluster_ip": cluster_ip
                })

            node_details['services'] = services_details

        except client.exceptions.ApiException as e:
            if e.status == 403:
                logging.warning(f"Permission denied when accessing services. Error: {e}")
                node_details['services'] = None

        return node_details

    except Exception as e:
        logging.error(f"Error retrieving detailed cluster information: {e}")
        return {"error": str(e)}


def get_agent_response(cluster_details, query):
    """
    Function to generate a response using LangChain and OpenAI.
    """
    try:
        node_info = "\n".join([
            f"Node: {node}\nStatus: {', '.join([f'{k}: {v}' for k, v in node_data['node_status'].items()])}"
            for node, node_data in cluster_details.items()
            if isinstance(node_data, dict) and "node_status" in node_data
        ])

        namespace_info = "\n".join([
            f"Namespace: {namespace}\nPods: {', '.join([pod['pod_name'].split('-')[0] for pod in details])}\nStatus: {', '.join([pod['status'] for pod in details])}"
            for node, namespaces in cluster_details.items()
            if isinstance(namespaces, dict) and "namespaces" in namespaces
            for namespace, details in namespaces["namespaces"].items()
            if isinstance(details, list)
        ])

        service_info = "\n".join([
            f"Namespace: {namespace}\nServices: {', '.join(['{0} (IP: {1})'.format(service['service_name'], service['cluster_ip']) for service in services])}"
            for namespace, services in cluster_details.get("services", {}).items()
        ])




    except KeyError as e:
        logging.error(f"KeyError encountered in processing: {e}")
        namespace_info = "Invalid cluster structure."
        node_info = "Invalid node structure."

    prompt_template = """
    You are a Kubernetes expert. Below are the details of the nodes, namespaces, pods, and services in a Kubernetes cluster. You will answer queries related to the kubernetes details provided. 
    You are prohibited from answering any questions or queries about anything else apart from the information provided below.
    Use the information provided to answer the query accurately. Remember to return only the answer without any unique identifiers.
    You must use return the answer in a single word without any unique identifiers or explainations with it. Here are examples to follow the format of answering. 
    These examples are completely fictional and do not reflect the actual status of the cluster:
    Q: "Which pod is spawned by my-deployment?" A: "my-pod"
    Q: "What is the status of the pod named 'example-pod'?" A: "Running"
    
    
    Node Status:
    {node_info}

    Namespace and Pod Details:
    {namespace_info}

    Service Details:
    {service_info}

    Query: {query}
    Answer:
    """

    formatted_prompt = prompt_template.format(node_info=node_info, namespace_info=namespace_info, service_info=service_info, query=query)

    openai_llm = OpenAI(temperature=0.3, openai_api_key=openai_key_api)

    prompt = PromptTemplate(template=formatted_prompt, input_variables=[])

    llm_chain = LLMChain(prompt=prompt, llm=openai_llm)

    llm_response = llm_chain.run({})

    # Use regex to preserve essential characters and remove unwanted ones
    clean_response = re.sub(r'[^A-Za-z0-9\s\.\:\-/]', '', llm_response).strip()

    return clean_response


@app.route('/query', methods=['POST'])
def create_query():
    try:
        request_data = request.json
        query = request_data.get('query')

        logging.info(f"Received query: {query}")

        cluster_details = get_all_cluster_info()
        print(cluster_details)
        answer = get_agent_response(cluster_details, query)

        logging.info(f"Generated answer: {answer}")

        response = QueryResponse(query=query, answer=answer)

        return jsonify(response.dict())

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
