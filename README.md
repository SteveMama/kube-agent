# Kube Agent:
 GPT4 powered Q&A bot to enquire the status of you Kubebetes cluster and get simple answers


 ## Requirements

### Setup your Kubernetes cluster
1. Install [Minikube](https://minikube.sigs.k8s.io/docs/start/)
2. Set up a local Kubernetes cluster
3. Deploy sample applications
4. Create deployments, nodes and pods as you desire. (Diverse<-->Better)
5. For starters, you can start your cluster as follows:
```
minikube start
```

### Dependencies

- `Flask`
- `pydantic`
- `kubernetes`
- `langchain`
- `OpenAI`
- `os`, `logging`, `re` (Python built-in libraries)
   

### Installation

- Use Python 3.10
- The kubeconfig file will be located at `~/.kube/config`
- Make sure install the required packages as follows:
```python
pip install -r requirements.txt
```

- Make sure you set you OpenAI API KEY in the environment as follows:

```python
export OPENAI_API_KEY="<YOUR API KEY>"
```
- Or you can choose to explicitly pass your API KEY in main.py.

## Usage

- Once your cluster is active and running, run
```
python main.py
```
- Thereafter you must pass your question as follows
  
```python
curl -X POST http://localhost:8000/query \
-H "Content-Type: application/json" \
-d '{"query": "how many pods are running?"}'
  ```


## Function Descriptions

#### `get_kubeconfig_path()`
- **Description**: Determines the location of the kubeconfig file, typically found in `~/.kube/config`.
- **Returns**: Path to the kubeconfig file.

#### `load_kube_config()`
- **Description**: Loads the Kubernetes configuration file using the dynamically determined path.
- **Returns**: None

#### `get_cluster_info()`
- **Description**: Retrieves general information about the Kubernetes cluster, such as version and number of nodes.
- **Returns**: A dictionary containing Kubernetes version, API server endpoint, and the number of nodes.

#### `get_node_info()`
- **Description**: Retrieves detailed information about each node in the cluster, including IP address, capacity, conditions, and labels.
- **Returns**: A dictionary mapping node names to their respective information.

#### `get_namespace_info()`
- **Description**: Collects details about each namespace in the cluster, including resource quotas and limits.
- **Returns**: A dictionary of namespace names to their quotas and limits.

#### `get_workload_info()`
- **Description**: Fetches workload-related details for deployments, stateful sets, daemon sets, jobs, and cron jobs across all namespaces.
- **Returns**: A dictionary of workload types and their corresponding items.

#### `get_service_info()`
- **Description**: Gathers information on services running in the cluster, including service name, type, and cluster IP.
- **Returns**: A dictionary of namespaces and their associated services.

#### `get_pod_info()`
- **Description**: Retrieves details on each pod in the cluster, such as name, QoS class, restart policy, and environment variables.
- **Returns**: A dictionary of namespaces and their respective pods' details.

#### `get_container_info(pod_info)`
- **Description**: Extracts container-level information, including image, ports, and mount paths for all containers in the given pod information.
- **Parameters**: 
  - `pod_info`: A dictionary of pod information to extract container details from.
- **Returns**: A dictionary of pod names to their container details.

#### `get_pod_env_vars()`
- **Description**: Retrieves environment variables for each pod across all namespaces.
- **Returns**: A dictionary of namespaces and their pods' environment variables.

#### `aggregate_info()`
- **Description**: Aggregates all the cluster, node, namespace, workload, service, pod, container, and environment variable information into a single data structure.
- **Returns**: A combined dictionary containing all the above information.

#### `generate_prompt(combined_info, query)`
- **Description**: Generates a concise prompt using the combined cluster information for querying Kubernetes cluster state.
- **Parameters**:
  - `combined_info`: Aggregated cluster information.
  - `query`: User query string.
- **Returns**: A formatted prompt for querying the Kubernetes cluster.

#### `get_agent_response(query)`
- **Description**: Generates a concise response to a user query based on Kubernetes cluster information using OpenAI's language model.
- **Parameters**: 
  - `query`: User query string.
- **Returns**: A concise response to the query.
