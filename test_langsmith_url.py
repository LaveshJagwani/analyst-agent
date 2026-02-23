import os
from dotenv import load_dotenv
from langsmith import Client
from langchain_groq import ChatGroq

def test_trace():
    load_dotenv()
    
    # Do NOT hardcode the project name here
    project = os.getenv("LANGCHAIN_PROJECT", "default-project")
    print(f"Using Project: {project}")
    
    groq_key = os.getenv("GROQ_API_KEY")
    client = Client()
    
    llm = ChatGroq(groq_api_key=groq_key, model_name="llama-3.3-70b-versatile")
    
    print("Sending a test trace...")
    try:
        response = llm.invoke("Hi")
        print(f"LLM Response: {response.content}")
        
        print("Waiting for trace to sync...")
        import time
        time.sleep(3)
        
        runs = list(client.list_runs(project_name=project, limit=1))
        if runs:
            url = client.get_run_url(run=runs[0])
            print(f"SUCCESS! Found run in '{project}'")
            print(f"Run URL: {url}")
        else:
            print(f"No runs found in project '{project}'.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_trace()
