import logging
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
    their pods, pod status, logs, and resource information. If a permission issue
    is encountered for a namespace or resource, the function will exclude it and
    set the value to `None`.
    """
    try:
        config.load_kube_config()

        clientv1 = client.CoreV1Api()

        node_details = {}

        try:
            nodes = clientv1.list_node()
            for node in nodes.items:
                node_name = node.metadata.name
                node_details[node_name] = {"namespaces": {}, "status": node.status.conditions}
        except client.exceptions.ApiException as e:
            if e.status == 403:
                logging.warning(f"Permission denied when accessing nodes. Error: {e}")
                node_details = None
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
                    logging.warning(
                        f"Permission denied when accessing logs for pod {pod_name} in namespace {namespace}.")
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

        return node_details

    except Exception as e:
        logging.error(f"Error retrieving detailed cluster information: {e}")
        return {"error": str(e)}


def get_langchain_response(cluster_details, query):
    """
    Function to generate a response using LangChain and OpenAI.
    """
    print(f"Cluster Details Structure: {cluster_details}")

    try:
        namespace_info = "\n".join([
            f"Namespace: {namespace}\nPods: {', '.join([pod['pod_name'].split('-')[0] for pod in details['pods']])}\nStatus: {', '.join([pod['status'] for pod in details['pods']])}"
            for node, namespaces in cluster_details.items()
            if isinstance(namespaces, dict) and "namespaces" in namespaces
            for namespace, details in namespaces["namespaces"].items()
            if isinstance(details, dict) and "pods" in details
        ])
    except KeyError as e:
        print(f"KeyError encountered in processing: {e}")
        namespace_info = "Invalid cluster structure."

    print(f"Formatted Namespace Info: {namespace_info}")

    prompt_template = """
    You are a Kubernetes expert. Below are the details of the namespaces and pods in a Kubernetes cluster.
    Use the information provided to answer the query accurately. Remember to return only the answer without any unique identifiers.

    Namespace and Pod Details:
    {namespace_info}

    Query: {query}
    Answer:
    """

    formatted_prompt = prompt_template.format(namespace_info=namespace_info, query=query)

    openai_llm = OpenAI(temperature=0.3, openai_api_key=openai_key_api)

    prompt = PromptTemplate(template=formatted_prompt, input_variables=[])

    llm_chain = LLMChain(prompt=prompt, llm=openai_llm)

    llm_response = llm_chain.run({})

    simplified_response = " ".join([word.split('-')[0] for word in llm_response.split()])
    return simplified_response



@app.route('/query', methods=['POST'])
def create_query():
    try:
        request_data = request.json
        query = request_data.get('query')

        logging.info(f"Received query: {query}")

        cluster_details = get_all_cluster_info()
        answer = get_langchain_response(cluster_details, query)

        logging.info(f"Generated answer: {answer}")

        response = QueryResponse(query=query, answer=answer)

        return jsonify(response.dict())

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
