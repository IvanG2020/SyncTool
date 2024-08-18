### **Tutorial: How to Set Up and Use the NetSuite & Azure DevOps Sync Tool**

This tutorial will guide you through the steps needed to set up, configure, and use the Python-based NetSuite & Azure DevOps Sync Tool.
![image](https://github.com/user-attachments/assets/d3d4247c-6f33-4500-86eb-ac4b11a082b7)


---

### **Table of Contents**
1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Using the Sync Tool](#using-the-sync-tool)
   - [API Settings Configuration](#api-settings-configuration)
   - [Starting the Sync Process](#starting-the-sync-process)
   - [Viewing Sync Logs](#viewing-sync-logs)
   - [Undoing the Last Sync](#undoing-the-last-sync)
5. [Troubleshooting](#troubleshooting)

---

### **Requirements**

Before you begin, ensure you have the following:

- **Python 3.8 or higher**: Make sure Python is installed on your system. You can download it from [python.org](https://www.python.org/downloads/).
- **Pip (Python Package Installer)**: Pip should be installed with Python. Verify by running `pip --version` in your terminal.
- **Internet Access**: Required to install packages and access APIs.

### **Installation**

1. **Clone or Download the Project:**
   - If you have Git installed, clone the repository:
     ```bash
     git clone https://github.com/your-repository/netsuite-azure-sync.git
     ```
   - Alternatively, download the ZIP file from the repository and extract it.

2. **Install Required Packages:**
   - Navigate to the project directory:
     ```bash
     cd netsuite-azure-sync
     ```
   - Install the necessary Python packages:
     ```bash
     pip install requests
     pip install tkinter
     ```

### **Configuration**

Before running the tool, you need to configure your NetSuite and Azure DevOps API credentials.

1. **API Keys and Credentials:**
   - Obtain your NetSuite and Azure DevOps credentials:
     - **NetSuite**: You’ll need Account ID, Consumer Key, Consumer Secret, Token Key, and Token Secret.
     - **Azure DevOps**: You’ll need your Organization Name, Project Name, and Personal Access Token (PAT).
  
2. **Storing Credentials:**
   - Open the tool and navigate to the "API Settings" view to input your credentials (see below for detailed instructions).

### **Using the Sync Tool**

#### **1. API Settings Configuration**

1. **Open the Sync Tool:**
   - Run the Python script to start the tool:
     ```bash
     python sync_tool.py
     ```
   - The main window will appear with options to configure API settings, start the sync, view logs, and undo the last sync.

2. **Configure API Settings:**
   - Click on the "API Settings" button.
   - A new window will open where you can enter your NetSuite and Azure DevOps API credentials:
     - **NetSuite Account ID**
     - **NetSuite Consumer Key**
     - **NetSuite Consumer Secret**
     - **NetSuite Token Key**
     - **NetSuite Token Secret**
     - **Azure DevOps Organization Name**
     - **Azure DevOps Project Name**
     - **Azure DevOps Personal Access Token (PAT)**
   - After entering the information, click "Save" to store the credentials. You will see a confirmation message.

#### **2. Starting the Sync Process**

1. **Start Syncing:**
   - From the main window, click the "Start Sync" button.
   - A loading screen will appear, indicating the sync is in progress.
   - The tool will compare NetSuite cases with Azure DevOps work items, create new items where necessary, and update statuses as needed.
   - Upon completion, you’ll receive a notification indicating success or failure.

#### **3. Viewing Sync Logs**

1. **View Log of Changes:**
   - Click on the "View Sync Log" button in the main window.
   - A new window will open displaying a list of changes made during the sync process.
   - You can scroll through the log to see details about which cases were synced or updated.

#### **4. Undoing the Last Sync**

1. **Revert the Last Sync:**
   - If you need to undo the last sync operation, click on the "Undo Last Sync" button in the main window.
   - The tool will reverse any changes made during the most recent sync (e.g., closing reopened cases, deleting created work items).
   - A confirmation message will appear once the undo operation is successful.

### **Troubleshooting**

If you encounter issues while using the sync tool, consider the following troubleshooting steps:

1. **Connection Errors:**
   - Verify that your API credentials are correct and that your internet connection is stable.
   - Ensure your firewall or security settings aren’t blocking API requests.

2. **ModuleNotFoundError:**
   - If you encounter an error saying a module is not found (e.g., `ModuleNotFoundError: No module named 'requests'`), make sure you have installed all required packages using `pip install -r requirements.txt`.

3. **Sync Issues:**
   - If syncs are not behaving as expected, double-check your API credentials and logs to see if there were any errors during the process.

4. **Updating Credentials:**
   - You can update your API credentials anytime through the "API Settings" view.

---

By following this guide, you should be able to set up and use the NetSuite & Azure DevOps Sync Tool effectively. The tool is designed to simplify the process of keeping your cases in sync across both platforms. If you need further customization or encounter any issues, feel free to consult the tool’s documentation or seek assistance from the developer community.
