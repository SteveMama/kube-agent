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


