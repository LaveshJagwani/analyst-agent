import os
from dotenv import load_dotenv
from langsmith import Client
from langchain_groq import ChatGroq

def get_details():
    load_dotenv()
    # Explicitly set env vars just in case
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "agent-analysis-v1")
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
    
    project_name = os.environ["LANGCHAIN_PROJECT"]
    print(f"Project Name: {project_name}")
    
    try:
        print("\n--- Sending a small trace ---")
        llm = ChatGroq(model_name="llama-3.3-70b-versatile")
        llm.invoke("Hi")
        
        print("Waiting for trace to sync (5s)...")
        import time
        time.sleep(5)
        
        client = Client()
        runs = list(client.list_runs(project_name=project_name, limit=1))
        if runs:
            url = client.get_run_url(run=runs[0])
            print(f"SUCCESS! Direct link to your latest run in project '{project_name}':")
            print(url)
        else:
            print(f"No runs found in project '{project_name}'. Trying to list all projects to see where it went...")
            projects = list(client.list_projects())
            print(f"Your Projects: {[p.name for p in projects]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_details()
