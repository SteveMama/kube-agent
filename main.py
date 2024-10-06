import logging
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
from kubernetes import client, config
import openai
from langchain import OpenAI, LLMChain, PromptTemplate

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s - %(message)s',
                    filename='agent.log', filemode='a')

app = Flask(__name__)

#openapi_key = 0# '42Cx_URr5M_1eaFkDWu4SmmvqVungkQ-k-OkxlGke81VUKvEm6WlZGtjKmljMLBO0nkA'


# Define the Pydantic response model
class QueryResponse(BaseModel):
    query: str
    answer: str


def get_all_namespaces_and_pods():
    """
    Function to return a JSON with all namespaces and their respective pods and status.
    """
    try:

        config.load_kube_config()
        v1 = client.CoreV1Api()
        namespaces = v1.list_namespace()
        namespace_pod_status = {}

        for namespace in namespaces.items:
            namespace_name = namespace.metadata.name

            # Get all pods in the current namespace
            pods = v1.list_namespaced_pod(namespace=namespace_name)

            # Store the pod names and their status
            namespace_pod_status[namespace_name] = {"pods": []}

            # Collect pod details for each pod in the namespace
            for pod in pods.items:
                pod_name = pod.metadata.name
                pod_status = pod.status.phase

                # Append each pod's details to the corresponding namespace
                namespace_pod_status[namespace_name]["pods"].append({
                    "pod_name": pod_name,
                    "status": pod_status
                })

        return namespace_pod_status

    except Exception as e:
        logging.error(f"Error retrieving namespace and pod details: {e}")
        return {"error": str(e)}


def get_langchain_response(namespace_details, query):
    """
    Function to generate a response using LangChain and OpenAI.
    """
    # Convert the namespace details to a readable format for the prompt
    namespace_info = "\n".join([
        f"Namespace: {namespace}\nPods: {', '.join([pod['pod_name'] for pod in details['pods']])}\nStatus: {', '.join([pod['status'] for pod in details['pods']])}"
        for namespace, details in namespace_details.items()
    ])

    # Define the prompt template
    prompt_template = """
    You are a Kubernetes expert. Below are the details of the namespaces and pods in a Kubernetes cluster.
    Use the information provided to answer the query accurately.

    Namespace and Pod Details:
    {namespace_info}

    Query: {query}
    Answer:
    """

    formatted_prompt = prompt_template.format(namespace_info=namespace_info, query=query)

    openai_llm = OpenAI(openai_api_key=)#openapi_key, temperature=0.3)

    prompt = PromptTemplate(template=formatted_prompt, input_variables=[])

    llm_chain = LLMChain(prompt=prompt, llm=openai_llm)

    return llm_chain.run({})


@app.route('/query', methods=['POST'])
def create_query():
    try:
        request_data = request.json
        query = request_data.get('query')

        logging.info(f"Received query: {query}")

        namespace_details = get_all_namespaces_and_pods()

        answer = get_langchain_response(namespace_details, query)

        logging.info(f"Generated answer: {answer}")

        response = QueryResponse(query=query, answer=answer)

        return jsonify(response.dict())

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
