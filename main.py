# main.py

import logging
import os
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
from langchain import OpenAI
from utils import (
    aggregate_info,
    get_agent_response
)
from prompt import generate_prompt

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s - %(message)s',
                    filename='agent.log', filemode='a')

app = Flask(__name__)

openai_key_api = os.environ.get('OPENAI_API_KEY')


class QueryResponse(BaseModel):
    query: str
    answer: str


@app.route('/query', methods=['POST'])
def create_query():
    try:
        request_data = request.json
        query = request_data.get('query')
        logging.info(f"Received query: {query}")

        # Call the agent to get the response
        answer = get_agent_response(query, openai_key_api)
        logging.info(f"Generated answer: {answer}")

        response = QueryResponse(query=query, answer=answer)
        return jsonify(response.dict())

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
