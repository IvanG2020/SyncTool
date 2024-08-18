import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Listbox, Scrollbar, RIGHT, Y, LEFT, BOTH, Frame
import requests
import threading

# Default configurations (replace with your actual values or leave blank)
config = {
    "netsuite_account": '',
    "netsuite_consumer_key": '',
    "netsuite_consumer_secret": '',
    "netsuite_token_key": '',
    "netsuite_token_secret": '',
    "azure_org": '',
    "azure_project": '',
    "azure_pat": ''
}

# Global log list to track sync changes and their original states for undo
sync_log = []
undo_actions = []

def fetch_netsuite_cases():
    # Your code to fetch cases from NetSuite
    return [
        {"id": 123, "title": "Sample Case", "status": "Open"}
    ]

def fetch_azure_work_items():
    url = f'https://dev.azure.com/{config["azure_org"]}/{config["azure_project"]}/_apis/wit/workitems?api-version=6.0'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {config["azure_pat"]}'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        print(f"Failed to fetch work items: {response.status_code}, {response.text}")
        return []

def create_or_update_azure_work_item(case):
    work_item = None
    azure_work_items = fetch_azure_work_items()
    for item in azure_work_items:
        if item['fields']['System.Title'] == case['title']:
            work_item = item
            break

    if work_item:
        if case['status'] == 'Closed' and work_item['fields']['System.State'] != 'Closed':
            original_state = work_item['fields']['System.State']
            update_azure_work_item_status(work_item['id'], 'Closed')
            undo_actions.append(("azure", work_item['id'], "System.State", original_state))
            sync_log.append(f"Azure Work Item {work_item['id']} closed due to NetSuite case {case['id']} being closed.")
    else:
        create_azure_work_item(case)

def create_azure_work_item(case):
    url = f'https://dev.azure.com/{config["azure_org"]}/{config["azure_project"]}/_apis/wit/workitems?api-version=6.0'
    headers = {
        'Content-Type': 'application/json-patch+json',
        'Authorization': f'Basic {config["azure_pat"]}'
    }
    
    data = [
        {"op": "add", "path": "/fields/System.Title", "value": case['title']},
        {"op": "add", "path": "/fields/System.State", "value": "New"}
    ]
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        work_item_id = response.json().get('id')
        undo_actions.append(("azure_delete", work_item_id))  # Track creation for possible deletion
        sync_log.append(f"Azure Work Item {work_item_id} created for NetSuite case {case['id']}.")
    else:
        print(f"Failed to create work item: {response.status_code}, {response.text}")

def update_azure_work_item_status(work_item_id, status):
    url = f'https://dev.azure.com/{config["azure_org"]}/{config["azure_project"]}/_apis/wit/workitems/{work_item_id}?api-version=6.0'
    headers = {
        'Content-Type': 'application/json-patch+json',
        'Authorization': f'Basic {config["azure_pat"]}'
    }
    
    data = [
        {"op": "add", "path": "/fields/System.State", "value": status}
    ]
    
    response = requests.patch(url, json=data, headers=headers)
    if response.status_code == 200:
        sync_log.append(f"Azure Work Item {work_item_id} updated to {status}.")
    else:
        print(f"Failed to update work item {work_item_id}: {response.status_code}, {response.text}")

def update_netsuite_case_status(case_id, status):
    url = f'https://YOUR_ACCOUNT.suitetalk.api.netsuite.com/services/rest/record/v1/supportCase/{case_id}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config["netsuite_token_key"]}'
    }
    
    data = {"status": {"name": status}}
    
    response = requests.patch(url, json=data, headers=headers)
    if response.status_code == 200:
        undo_actions.append(("netsuite", case_id, "status", "Open" if status == "Closed" else "Closed"))
        sync_log.append(f"NetSuite case {case_id} updated to {status} due to Azure Work Item.")
    else:
        print(f"Failed to update NetSuite case {case_id}: {response.status_code}, {response.text}")

def sync_cases():
    try:
        sync_log.clear()  # Clear the log before starting a new sync
        undo_actions.clear()  # Clear undo actions list before a new sync
        netsuite_cases = fetch_netsuite_cases()
        azure_work_items = fetch_azure_work_items()
        
        for case in netsuite_cases:
            create_or_update_azure_work_item(case)

        for work_item in azure_work_items:
            corresponding_case = next((c for c in netsuite_cases if c['title'] == work_item['fields']['System.Title']), None)
            if corresponding_case:
                if work_item['fields']['System.State'] == 'Closed' and corresponding_case['status'] != 'Closed':
                    update_netsuite_case_status(corresponding_case['id'], 'Closed')

        show_sync_result("Sync Complete", "The sync process has completed successfully.")
    except Exception as e:
        show_sync_result("Sync Failed", f"An error occurred during sync: {str(e)}")

def undo_sync():
    try:
        for action in reversed(undo_actions):  # Undo in reverse order
            if action[0] == "azure":
                update_azure_work_item_status(action[1], action[3])
            elif action[0] == "azure_delete":
                delete_azure_work_item(action[1])
            elif action[0] == "netsuite":
                update_netsuite_case_status(action[1], action[3])
        undo_actions.clear()
        messagebox.showinfo("Undo Successful", "The sync changes have been successfully undone.")
    except Exception as e:
        messagebox.showerror("Undo Failed", f"An error occurred while undoing sync: {str(e)}")

def delete_azure_work_item(work_item_id):
    url = f'https://dev.azure.com/{config["azure_org"]}/{config["azure_project"]}/_apis/wit/workitems/{work_item_id}?api-version=6.0'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {config["azure_pat"]}'
    }
    
    response = requests.delete(url, headers=headers)
    if response.status_code == 204:
        sync_log.append(f"Azure Work Item {work_item_id} deleted.")
    else:
        print(f"Failed to delete work item {work_item_id}: {response.status_code}, {response.text}")

def show_loading_screen():
    global loading_screen
    loading_screen = Toplevel()
    loading_screen.title("Sync in Progress")
    loading_screen.geometry("300x100")
    loading_screen.configure(bg="#34495e")
    Label(loading_screen, text="Sync in progress, please wait...", font=("Arial", 14), bg="#34495e", fg="white").pack(pady=20)

def hide_loading_screen():
    if loading_screen:
        loading_screen.destroy()

def show_sync_result(title, message):
    hide_loading_screen()
    messagebox.showinfo(title, message)

def start_sync():
    show_loading_screen()
    threading.Thread(target=sync_cases).start()

def save_config():
    global config
    config["netsuite_account"] = netsuite_account_entry.get()
    config["netsuite_consumer_key"] = netsuite_consumer_key_entry.get()
    config["netsuite_consumer_secret"] = netsuite_consumer_secret_entry.get()
    config["netsuite_token_key"] = netsuite_token_key_entry.get()
    config["netsuite_token_secret"] = netsuite_token_secret_entry.get()
    config["azure_org"] = azure_org_entry.get()
    config["azure_project"] = azure_project_entry.get()
    config["azure_pat"] = azure_pat_entry.get()

    messagebox.showinfo("Configuration Saved", "API Keys and configuration have been saved.")

def open_api_settings():
    settings_window = Toplevel()
    settings_window.title("API Settings")
    settings_window.geometry("500x500")
    settings_window.configure(bg="#2c3e50")

    global netsuite_account_entry, netsuite_consumer_key_entry, netsuite_consumer_secret_entry, netsuite_token_key_entry, netsuite_token_secret_entry
    global azure_org_entry, azure_project_entry, azure_pat_entry

    Label(settings_window, text="NetSuite Account ID:", fg="white", bg="#2c3e50").pack(pady=5)
    netsuite_account_entry = tk.Entry(settings_window, width=40)
    netsuite_account_entry.pack()
    netsuite_account_entry.insert(0, config["netsuite_account"])

    Label(settings_window, text="NetSuite Consumer Key:", fg="white", bg="#2c3e50").pack(pady=5)
    netsuite_consumer_key_entry = tk.Entry(settings_window, width=40)
    netsuite_consumer_key_entry.pack()
    netsuite_consumer_key_entry.insert(0, config["netsuite_consumer_key"])

    Label(settings_window, text="NetSuite Consumer Secret:", fg="white", bg="#2c3e50").pack(pady=5)
    netsuite_consumer_secret_entry = tk.Entry(settings_window, width=40)
    netsuite_consumer_secret_entry.pack()
    netsuite_consumer_secret_entry.insert(0, config["netsuite_consumer_secret"])

    Label(settings_window, text="NetSuite Token Key:", fg="white", bg="#2c3e50").pack(pady=5)
    netsuite_token_key_entry = tk.Entry(settings_window, width=40)
    netsuite_token_key_entry.pack()
    netsuite_token_key_entry.insert(0, config["netsuite_token_key"])

    Label(settings_window, text="NetSuite Token Secret:", fg="white", bg="#2c3e50").pack(pady=5)
    netsuite_token_secret_entry = tk.Entry(settings_window, width=40)
    netsuite_token_secret_entry.pack()
    netsuite_token_secret_entry.insert(0, config["netsuite_token_secret"])

    Label(settings_window, text="Azure DevOps Organization:", fg="white", bg="#2c3e50").pack(pady=5)
    azure_org_entry = tk.Entry(settings_window, width=40)
    azure_org_entry.pack()
    azure_org_entry.insert(0, config["azure_org"])

    Label(settings_window, text="Azure DevOps Project:", fg="white", bg="#2c3e50").pack(pady=5)
    azure_project_entry = tk.Entry(settings_window, width=40)
    azure_project_entry.pack()
    azure_project_entry.insert(0, config["azure_project"])

    Label(settings_window, text="Azure DevOps Personal Access Token (PAT):", fg="white", bg="#2c3e50").pack(pady=5)
    azure_pat_entry = tk.Entry(settings_window, width=40, show="*")
    azure_pat_entry.pack()
    azure_pat_entry.insert(0, config["azure_pat"])

    save_button = tk.Button(settings_window, text="Save", command=save_config, font=("Arial", 14), bg="green", fg="white")
    save_button.pack(pady=20)

def view_sync_log():
    log_window = Toplevel()
    log_window.title("Sync Changes Log")
    log_window.geometry("600x400")
    log_window.configure(bg="#34495e")

    log_label = Label(log_window, text="Sync Changes Log", font=("Arial", 16), bg="#34495e", fg="white")
    log_label.pack(pady=10)

    scrollbar = Scrollbar(log_window)
    scrollbar.pack(side=RIGHT, fill=Y)

    log_listbox = Listbox(log_window, yscrollcommand=scrollbar.set, font=("Arial", 12), bg="#ecf0f1", fg="#2c3e50")
    log_listbox.pack(side=LEFT, fill=BOTH, expand=True)

    scrollbar.config(command=log_listbox.yview)

    for log_entry in sync_log:
        log_listbox.insert(tk.END, log_entry)

def create_main_window():
    window = tk.Tk()
    window.title("NetSuite & Azure DevOps Sync")
    window.geometry("400x400")
    window.configure(bg="#34495e")

    tk.Label(window, text="NetSuite & Azure DevOps Sync Tool", font=("Arial", 16, "bold"), bg="#34495e", fg="white").pack(pady=20)

    button_frame = Frame(window, bg="#34495e")
    button_frame.pack(pady=10)

    settings_button = tk.Button(button_frame, text="API Settings", command=open_api_settings, font=("Arial", 14), bg="orange", fg="white")
    settings_button.grid(row=0, column=0, padx=10, pady=10)

    sync_button = tk.Button(button_frame, text="Start Sync", command=start_sync, font=("Arial", 14), bg="green", fg="white")
    sync_button.grid(row=0, column=1, padx=10, pady=10)

    view_log_button = tk.Button(button_frame, text="View Sync Log", command=view_sync_log, font=("Arial", 14), bg="purple", fg="white")
    view_log_button.grid(row=1, column=0, padx=10, pady=10)

    undo_button = tk.Button(button_frame, text="Undo Last Sync", command=undo_sync, font=("Arial", 14), bg="red", fg="white")
    undo_button.grid(row=1, column=1, padx=10, pady=10)

    exit_button = tk.Button(window, text="Exit", command=window.quit, font=("Arial", 14), bg="red", fg="white")
    exit_button.pack(pady=20)
    
    window.mainloop()

if __name__ == '__main__':
    create_main_window()
