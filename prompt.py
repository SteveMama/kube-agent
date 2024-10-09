
def generate_prompt(combined_info, query):
    """
    Generates a concise prompt for querying Kubernetes cluster information.
    Returns a concise answer without identifiers or justifications.
    """
    # Extract necessary details from the combined cluster information
    cluster_info = combined_info.get("Cluster Information", {})
    node_info = combined_info.get("Node Information", {})
    namespace_info = combined_info.get("Namespace Information", {})
    workload_info = combined_info.get("Workload Information", {})
    service_info = combined_info.get("Service Information", {})
    pod_info = combined_info.get("Pod Information", {})
    container_info = combined_info.get("Container Information", {})

    node_info_str = "\n".join([f"- {node}" for node in node_info.keys()])
    namespace_info_str = "\n".join([f"- {namespace}" for namespace in namespace_info.keys()])
    workload_info_str = "\n".join(
        [f"- {workload_type}: {len(items)} items" for workload_type, items in workload_info.items()])
    service_info_str = "\n".join(
        [f"- {namespace}: {', '.join([svc['service_name'] for svc in services])}" for namespace, services in
         service_info.items()])
    pod_info_str = "\n".join(
        [f"- {namespace}: {', '.join([pod['pod_name'] for pod in pods])}" for namespace, pods in pod_info.items()])
    container_info_str = "\n".join(
        [f"- {pod}: {', '.join([container['container_name'] for container in containers])}" for pod, containers in
         container_info.items()])

    prompt_template = f"""
    You are a Kubernetes assistant. The user asked: '{query}'. You must answer the query based on the information without any explainations.
    Here is the cluster information:
    - Kubernetes Version: {cluster_info.get('kubernetes_version')}
    - Number of Nodes: {cluster_info.get('number_of_nodes')}
    - Nodes: {node_info_str}
    - Namespaces: {namespace_info_str}
    - Workloads: {workload_info_str}
    - Services: {service_info_str}
    - Pods: {pod_info_str}
    - Containers: {container_info_str}

    Answer the query in just one word. Provide only the necessary information without any technical identifiers, suffixes, or justifications. Return only the answer.

    Query:
    Answer: only the answer.
    """

    return prompt_template
