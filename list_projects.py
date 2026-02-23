import os
from dotenv import load_dotenv
from langsmith import Client

def list_all():
    load_dotenv()
    client = Client()
    print("--- Projects in your Org ---")
    projects = list(client.list_projects())
    for p in projects:
        # P is likely a Project object or dict
        name = getattr(p, 'name', 'N/A')
        print(f"Name: '{name}'")

if __name__ == "__main__":
    list_all()
