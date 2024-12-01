from utils import convert_bytes_to_base64_with_prefix, load_config, convert_bytes_to_base64, convert_ns_to_seconds
from vectordb_handler import load_vectordb
from dotenv import load_dotenv
import streamlit as st
import requests
import json
import os
load_dotenv()
config = load_config()
openai_api_key = os.getenv('OPENAI_API_KEY')

class OpenAIChatAPIHandler:
    def __init__(self):
        pass

    @classmethod
    def api_call(cls, chat_history, stream=False):
        data = {
            "model": st.session_state["model_to_use"],
            "messages": chat_history,
            "stream": stream
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_api_key}"
        }

        if stream:
            response = requests.post(
                url="https://api.openai.com/v1/chat/completions",
                json=data,
                headers=headers,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = response.json().get("error", {}).get("message", "Unknown error")
                yield f"OpenAI Error: {error_msg}"
                return

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        if line.startswith('data: [DONE]'):
                            break
                        try:
                            json_object = json.loads(line[6:])
                            content = json_object['choices'][0]['delta'].get('content', '')
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        else:
            response = requests.post(
                url="https://api.openai.com/v1/chat/completions",
                json=data,
                headers=headers
            )
            json_response = response.json()
            if "error" in json_response.keys():
                return json_response["error"]["message"]
            else:
                return response.json()["choices"][0]["message"]["content"]

    @classmethod
    def image_chat(cls, user_input, chat_history, image):
        chat_history.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_input},
                {"type": "image_url", "image_url": {"url": convert_bytes_to_base64_with_prefix(image)}}
            ]
        })
        return cls.api_call(chat_history)

class OllamaChatAPIHandler:
    def __init__(self):
        pass

    @classmethod
    def api_call(cls, chat_history, stream=False):
        data = {
            "model": st.session_state["model_to_use"],
            "messages": chat_history,
            "stream": stream
        }

        if stream:
            response = requests.post(
                url=config["ollama"]["base_url"] + "/api/chat",
                json=data,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = response.json().get("error", "Unknown error")
                yield f"OLLAMA ERROR: {error_msg}"
                return

            for line in response.iter_lines():
                if line:
                    try:
                        json_response = json.loads(line)
                        if 'message' in json_response:
                            content = json_response['message'].get('content', '')
                            if content:
                                yield content
                        if json_response.get('done', False):
                            cls.print_times(json_response)
                            break
                    except json.JSONDecodeError:
                        continue
        else:
            response = requests.post(
                url=config["ollama"]["base_url"] + "/api/chat",
                json=data
            )
            json_response = response.json()
            if "error" in json_response.keys():
                return "OLLAMA ERROR: " + json_response["error"]
            cls.print_times(json_response)
            return json_response["message"]["content"]

    @classmethod
    def image_chat(cls, user_input, chat_history, image):
        chat_history.append({
            "role": "user",
            "content": user_input,
            "images": [convert_bytes_to_base64(image)]
        })
        return cls.api_call(chat_history)

    @classmethod
    def print_times(cls, json_response):
        total_duration_ns = json_response.get("total_duration", 0)
        load_duration_ns = json_response.get("load_duration", 0)
        prompt_eval_duration_ns = json_response.get("prompt_eval_duration", 0)
        eval_duration_ns = json_response.get("eval_duration", 0)

        total_duration_seconds = convert_ns_to_seconds(total_duration_ns)
        load_duration_seconds = convert_ns_to_seconds(load_duration_ns)
        prompt_eval_duration_seconds = convert_ns_to_seconds(prompt_eval_duration_ns)
        eval_duration_seconds = convert_ns_to_seconds(eval_duration_ns)

        print(f"Total duration: {total_duration_seconds:.4f} seconds")
        print(f"Load duration: {load_duration_seconds:.4f} seconds")
        print(f"Prompt eval duration: {prompt_eval_duration_seconds:.4f} seconds")
        print(f"Eval duration: {eval_duration_seconds:.4f} seconds")

class ChatAPIHandler:
    def __init__(self):
        pass

    @classmethod
    def chat(cls, user_input, chat_history, image=None, stream=True):
        endpoint = st.session_state["endpoint_to_use"]
        print(f"Endpoint to use: {endpoint}")
        print(f"Model to use: {st.session_state['model_to_use']}")
        
        if endpoint == "openai":
            handler = OpenAIChatAPIHandler
        elif endpoint == "ollama":
            handler = OllamaChatAPIHandler
        else:
            raise ValueError(f"Unknown endpoint: {endpoint}")

        if st.session_state.get("pdf_chat", False):
            vector_db = load_vectordb()
            retrieved_documents = vector_db.similarity_search(
                user_input,
                k=config["chat_config"]["number_of_retrieved_documents"]
            )
            context = "\n".join([item.page_content for item in retrieved_documents])
            template = f"Answer the user question based on this context: {context}\nUser Question: {user_input}"
            chat_history.append({"role": "user", "content": template})
            return handler.api_call(chat_history, stream=stream)

        if image:
            return handler.image_chat(user_input, chat_history, image)

        chat_history.append({"role": "user", "content": user_input})
        return handler.api_call(chat_history, stream=stream)