import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Listbox, Scrollbar, RIGHT, Y, LEFT, BOTH, Frame, Radiobutton, IntVar
import requests
import threading

# Status mapping between Azure DevOps and NetSuite
status_mapping = {
    "New": "Open",
    "Active": "In Progress",
    "Resolved": "Resolved",
    "Closed": "Closed"
}

# Reverse mapping for syncing in the opposite direction
reverse_status_mapping = {v: k for k, v in status_mapping.items()}

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
selected_cases = []

def fetch_netsuite_cases():
    url = f'https://YOUR_ACCOUNT.suitetalk.api.netsuite.com/services/rest/record/v1/supportCase'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config["netsuite_token_key"]}'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        cases = response.json().get('items', [])
        return [{"id": case["id"], "title": case["title"], "status": case["status"]["name"]} for case in cases]
    else:
        print(f"Failed to fetch NetSuite cases: {response.status_code}, {response.text}")
        return []

def fetch_azure_work_items():
    url = f'https://dev.azure.com/{config["azure_org"]}/{config["azure_project"]}/_apis/wit/workitems?api-version=6.0'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {config["azure_pat"]}'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        work_items = response.json().get('value', [])
        return [{"id": item["id"], "title": item["fields"]["System.Title"], "status": item["fields"]["System.State"]} for item in work_items]
    else:
        print(f"Failed to fetch work items: {response.status_code}, {response.text}")
        return []

def create_or_update_azure_work_item(case):
    work_item = None
    azure_work_items = fetch_azure_work_items()
    for item in azure_work_items:
        if item['title'] == case['title']:
            work_item = item
            break

    mapped_status = reverse_status_mapping.get(case['status'], "New")

    if work_item:
        if case['status'] == 'Closed' and work_item['status'] != 'Closed':
            original_state = work_item['status']
            update_azure_work_item_status(work_item['id'], mapped_status)
            undo_actions.append(("azure", work_item['id'], "System.State", original_state))
            sync_log.append(f"Azure Work Item {work_item['id']} updated to {mapped_status} due to NetSuite case {case['id']} status change.")
    else:
        create_azure_work_item(case)

def create_azure_work_item(case):
    url = f'https://dev.azure.com/{config["azure_org"]}/{config["azure_project"]}/_apis/wit/workitems?api-version=6.0'
    headers = {
        'Content-Type': 'application/json-patch+json',
        'Authorization': f'Basic {config["azure_pat"]}'
    }

    mapped_status = reverse_status_mapping.get(case['status'], "New")

    data = [
        {"op": "add", "path": "/fields/System.Title", "value": case['title']},
        {"op": "add", "path": "/fields/System.State", "value": mapped_status}
    ]
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        work_item_id = response.json().get('id')
        undo_actions.append(("azure_delete", work_item_id))  # Track creation for possible deletion
        sync_log.append(f"Azure Work Item {work_item_id} created with status {mapped_status} for NetSuite case {case['id']}.")
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
    mapped_status = status_mapping.get(status, "Open")
    
    url = f'https://YOUR_ACCOUNT.suitetalk.api.netsuite.com/services/rest/record/v1/supportCase/{case_id}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config["netsuite_token_key"]}'
    }
    
    data = {"status": {"name": mapped_status}}
    
    response = requests.patch(url, json=data, headers=headers)
    if response.status_code == 200:
        undo_actions.append(("netsuite", case_id, "status", "Open" if mapped_status == "Closed" else "Closed"))
        sync_log.append(f"NetSuite case {case_id} updated to {mapped_status} due to Azure Work Item status change.")
    else:
        print(f"Failed to update NetSuite case {case_id}: {response.status_code}, {response.text}")

def sync_cases():
    try:
        sync_log.clear()  # Clear the log before starting a new sync
        undo_actions.clear()  # Clear undo actions list before a new sync
        
        if sync_direction.get() == 1:  # NetSuite to DevOps
            netsuite_cases = fetch_netsuite_cases()
            for case in netsuite_cases:
                create_or_update_azure_work_item(case)
        elif sync_direction.get() == 2:  # DevOps to NetSuite
            azure_work_items = fetch_azure_work_items()
            for work_item in azure_work_items:
                corresponding_case = next((c for c in selected_cases if c['title'] == work_item['title']), None)
                if corresponding_case:
                    if work_item['status'] == 'Closed' and corresponding_case['status'] != 'Closed':
                        update_netsuite_case_status(corresponding_case['id'], work_item['status'])

        show_sync_result("Sync Complete", "The sync process has completed successfully.")
    except Exception as e:
        show_sync_result("Sync Failed", f"An error occurred during sync: {str(e)}")

def sync_selected_cases():
    try:
        sync_log.clear()  # Clear the log before starting a new sync
        undo_actions.clear()  # Clear undo actions list before a new sync

        show_loading_screen()  # Show loading screen only after selection

        if sync_direction.get() == 1:  # NetSuite to DevOps
            for case in selected_cases:
                create_or_update_azure_work_item(case)
        elif sync_direction.get() == 2:  # DevOps to NetSuite
            for case in selected_cases:
                update_netsuite_case_status(case['id'], 'Closed')  # Example logic, adjust as needed

        show_sync_result("Sync Complete", "The selected cases have been synced successfully.")
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

def start_sync(auto_sync=True):
    if auto_sync:
        show_loading_screen()
        threading.Thread(target=sync_cases).start()
    else:
        open_case_selection_window()

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

def open_case_selection_window():
    global cases  # Declare cases as a global variable
    cases = []  # Initialize cases as an empty list

    def fetch_cases():
        global cases  # Refer to the global cases variable
        # Fetch cases based on the selected source
        if fetch_source.get() == 1:  # NetSuite
            cases = fetch_netsuite_cases()
        else:  # Azure DevOps
            cases = fetch_azure_work_items()

        if not cases:  # Check if no cases were fetched
            messagebox.showerror("Fetch Failed", "No cases were found from the selected source.")
            return

        # Clear the listbox and repopulate it with the fetched cases
        case_listbox.delete(0, tk.END)
        for i, case in enumerate(cases):
            case_listbox.insert(tk.END, f"Case {case['id']}: {case['title']} ({case['status']})")

        # Update the total cases label
        total_cases_label.config(text=f"Total Cases Fetched: {len(cases)}")
        selected_count_var.set(f"Selected: 0")

    # Window setup
    selection_window = Toplevel()
    selection_window.title("Select Cases to Sync")
    selection_window.geometry("500x600")
    selection_window.configure(bg="#34495e")

    # Radio buttons to select fetch source
    fetch_source = IntVar(value=1)  # Default to NetSuite

    source_frame = Frame(selection_window, bg="#34495e")
    source_frame.pack(pady=10)

    tk.Label(source_frame, text="Select Source:", bg="#34495e", fg="white", font=("Arial", 14)).pack()

    netsuite_rb = Radiobutton(source_frame, text="NetSuite", variable=fetch_source, value=1, bg="#34495e", fg="white", font=("Arial", 12))
    netsuite_rb.pack(side=tk.LEFT, padx=10, pady=10)

    azure_rb = Radiobutton(source_frame, text="Azure DevOps", variable=fetch_source, value=2, bg="#34495e", fg="white", font=("Arial", 12))
    azure_rb.pack(side=tk.LEFT, padx=10, pady=10)

    # Fetch Cases Button
    fetch_button = tk.Button(selection_window, text="Fetch Cases", command=fetch_cases, bg="#2980b9", fg="white", font=("Arial", 14))
    fetch_button.pack(pady=10)

    # Add a label to display the total number of cases fetched
    total_cases_label = Label(selection_window, text="Total Cases Fetched: 0", bg="#34495e", fg="white", font=("Arial", 12))
    total_cases_label.pack(pady=10)

    # Add a label to display the number of selected cases
    selected_count_var = tk.StringVar()
    selected_count_var.set(f"Selected: 0")
    selected_count_label = Label(selection_window, textvariable=selected_count_var, bg="#34495e", fg="white", font=("Arial", 12))
    selected_count_label.pack(pady=5)

    # Create a frame to hold the listbox and scrollbar
    list_frame = Frame(selection_window)
    list_frame.pack(pady=10, fill=BOTH, expand=True)

    # Add a scrollbar and listbox for displaying the cases
    scrollbar = Scrollbar(list_frame)
    scrollbar.pack(side=RIGHT, fill=Y)

    case_listbox = Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, font=("Arial", 12), bg="#ecf0f1", fg="#2c3e50", height=20)
    case_listbox.pack(side=LEFT, fill=BOTH, expand=True)

    scrollbar.config(command=case_listbox.yview)

    # Populate the listbox with the case information
    def update_selected_count(event):
        selected_count_var.set(f"Selected: {len(case_listbox.curselection())}")

    case_listbox.bind('<<ListboxSelect>>', update_selected_count)

    # Function to confirm selection and start the sync
    def confirm_selection():
        global selected_cases
        selected_cases = [cases[i] for i in case_listbox.curselection()]
        selection_window.destroy()
        threading.Thread(target=sync_selected_cases).start()

    tk.Button(selection_window, text="Sync Selected Cases", command=confirm_selection, bg="#2980b9", fg="white", font=("Arial", 14)).pack(pady=20)

# Function to open the report generation window
def open_report_window():
    report_window = Toplevel()
    report_window.title("Generate Company Report")
    report_window.geometry("500x400")
    report_window.configure(bg="#34495e")

    Label(report_window, text="Select Companies:", bg="#34495e", fg="white", font=("Arial", 14)).pack(pady=10)

    # Listbox for selecting companies
    company_listbox = Listbox(report_window, selectmode=tk.MULTIPLE, font=("Arial", 12), bg="#ecf0f1", fg="#2c3e50")
    company_listbox.pack(pady=10, fill=BOTH, expand=True)

    # Example companies - replace with actual data
    companies = ["Company A", "Company B", "Company C", "Company D"]
    for company in companies:
        company_listbox.insert(tk.END, company)

    def generate_report():
        selected_companies = [company_listbox.get(i) for i in company_listbox.curselection()]
        if not selected_companies:
            messagebox.showerror("Error", "Please select at least one company.")
            return

        tickets = fetch_netsuite_tickets_by_companies(selected_companies)
        if not tickets:
            messagebox.showinfo("No Tickets", "No open tickets found for the selected companies.")
            return

        display_tickets(tickets)

    generate_button = tk.Button(report_window, text="Generate Report", command=generate_report, bg="#2980b9", fg="white", font=("Arial", 14))
    generate_button.pack(pady=20)


def fetch_netsuite_tickets_by_companies(selected_companies):
    # Replace with real API calls to NetSuite
    all_tickets = [
        {"id": 123, "company": "Company A", "title": "Sample Case 1", "status": "Open"},
        {"id": 124, "company": "Company B", "title": "Sample Case 2", "status": "Open"},
        {"id": 125, "company": "Company A", "title": "Sample Case 3", "status": "Closed"},
        {"id": 126, "company": "Company C", "title": "Sample Case 4", "status": "Open"}
    ]

    return [ticket for ticket in all_tickets if ticket['company'] in selected_companies and ticket['status'] == "Open"]

def display_tickets(tickets):
    report_display_window = Toplevel()
    report_display_window.title("Open Tickets Report")
    report_display_window.geometry("600x400")
    report_display_window.configure(bg="#34495e")

    Label(report_display_window, text="Open Tickets", bg="#34495e", fg="white", font=("Arial", 14)).pack(pady=10)

    listbox = Listbox(report_display_window, font=("Arial", 12), bg="#ecf0f1", fg="#2c3e50")
    listbox.pack(fill=BOTH, expand=True)

    for ticket in tickets:
        listbox.insert(tk.END, f"ID: {ticket['id']} | Company: {ticket['company']} | Title: {ticket['title']}")

    def export_to_csv():
        import csv
        with open("company_tickets_report.csv", "w", newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Company", "Title", "Status"])
            for ticket in tickets:
                writer.writerow([ticket['id'], ticket['company'], ticket['title'], ticket['status']])
        messagebox.showinfo("Export Successful", "Report exported to company_tickets_report.csv")

    export_button = tk.Button(report_display_window, text="Export to CSV", command=export_to_csv, bg="green", fg="white", font=("Arial", 14))
    export_button.pack(pady=10)

# New Function: View Sync Log
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

# Main Application Window
def create_main_window():
    global sync_direction

    window = tk.Tk()
    window.title("NetSuite & Azure DevOps Sync")
    window.geometry("500x500")  # Adjusted window size
    window.configure(bg="#34495e")

    sync_direction = IntVar(value=1)  # Default to NetSuite to DevOps

    tk.Label(window, text="NetSuite & Azure DevOps Sync Tool", font=("Arial", 18, "bold"), bg="#34495e", fg="white").pack(pady=20)

    button_frame = Frame(window, bg="#34495e")
    button_frame.pack(pady=10)

    # Sync Direction Radiobuttons
    direction_frame = Frame(window, bg="#34495e")
    direction_frame.pack(pady=10)
    tk.Label(direction_frame, text="Select Sync Direction:", bg="#34495e", fg="white", font=("Arial", 14)).grid(row=0, column=0, columnspan=2, pady=5)

    netsuite_to_devops_rb = Radiobutton(direction_frame, text="NetSuite to Azure DevOps", variable=sync_direction, value=1, bg="#34495e", fg="white", font=("Arial", 12))
    netsuite_to_devops_rb.grid(row=1, column=0, padx=5, pady=5)

    devops_to_netsuite_rb = Radiobutton(direction_frame, text="Azure DevOps to NetSuite", variable=sync_direction, value=2, bg="#34495e", fg="white", font=("Arial", 12))
    devops_to_netsuite_rb.grid(row=1, column=1, padx=5, pady=5)

    settings_button = tk.Button(button_frame, text="API Settings", command=open_api_settings, font=("Arial", 14), bg="orange", fg="white", width=18)
    settings_button.grid(row=0, column=0, padx=10, pady=10)

    sync_button = tk.Button(button_frame, text="Auto Sync All Cases", command=lambda: start_sync(auto_sync=True), font=("Arial", 14), bg="green", fg="white", width=18)
    sync_button.grid(row=0, column=1, padx=10, pady=10)

    select_sync_button = tk.Button(button_frame, text="Select and Sync Cases", command=lambda: start_sync(auto_sync=False), font=("Arial", 14), bg="blue", fg="white", width=18)
    select_sync_button.grid(row=1, column=0, padx=10, pady=10)

    view_log_button = tk.Button(button_frame, text="View Sync Log", command=view_sync_log, font=("Arial", 14), bg="purple", fg="white", width=18)
    view_log_button.grid(row=1, column=1, padx=10, pady=10)

    report_button = tk.Button(button_frame, text="Generate Report", command=open_report_window, font=("Arial", 14), bg="gold", fg="black", width=18)
    report_button.grid(row=2, column=0, padx=10, pady=10)

    undo_button = tk.Button(button_frame, text="Undo Last Sync", command=undo_sync, font=("Arial", 14), bg="red", fg="white", width=18)
    undo_button.grid(row=2, column=1, padx=10, pady=10)

    exit_button = tk.Button(window, text="Exit", command=window.quit, font=("Arial", 14), bg="red", fg="white", width=18)
    exit_button.pack(pady=20)
    
    window.mainloop()

if __name__ == '__main__':
    create_main_window()
