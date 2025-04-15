import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import ttkbootstrap as tb
import pandas as pd
import json
import os
import subprocess
from datetime import datetime

DATA_FILE = "data.json"
LAST_UPDATED_FIELD = "Last Updated"
TENANT_FIELD = "Tenant"
PROJECT_FIELD = "Project"
ADMIN = "administrator"

# Define current user (could be set at login)
current_user = simpledialog.askstring("Login", "Enter username (tenant or administrator):")
if not current_user:
    exit()

# Git commit after changes
def git_commit(file_path, message):
    if os.path.exists(".git"):
        subprocess.run(["git", "add", file_path])
        subprocess.run(["git", "commit", "-m", message])

# Initialize from Excel if no JSON exists
def initialize_from_excel():
    excel_file = filedialog.askopenfilename(title="Select initial Excel file", filetypes=[["Excel files", "*.xlsx"]])
    if excel_file:
        df = pd.read_excel(excel_file)
        data = df.to_dict(orient="records")
        for row in data:
            row[LAST_UPDATED_FIELD] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row[TENANT_FIELD] = row.get(TENANT_FIELD, current_user if current_user != ADMIN else "")
        save_data(data)
        return data
    return []

# Load all data from the single JSON file
def load_data():
    if not os.path.exists(DATA_FILE):
        return initialize_from_excel()
    with open(DATA_FILE, "r") as f:
        return json.load(f)

# Save all data to the single JSON file
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    git_commit(DATA_FILE, f"Data updated by {current_user}")

# Filter data for current user (unless admin)
def get_filtered_data():
    all_data = load_data()
    if current_user == ADMIN:
        return all_data
    return [row for row in all_data if row.get(TENANT_FIELD) == current_user]

def get_available_projects(data):
    if current_user == ADMIN:
        return sorted(set(row.get(PROJECT_FIELD, "") for row in data if row.get(PROJECT_FIELD)))
    return sorted(set(row.get(PROJECT_FIELD, "") for row in data if row.get(TENANT_FIELD) == current_user and row.get(PROJECT_FIELD)))


# Export to multiple formats
def export_data(data):
    if not data:
        messagebox.showinfo("Export", "No data to export.")
        return

    export_type = tk.simpledialog.askstring("Export Format", "Enter format: json, html, txt, xlsx")
    if not export_type:
        return

    filetypes = {
        "json": ["JSON files", "*.json"],
        "html": ["HTML files", "*.html"],
        "txt": ["Text files", "*.txt"],
        "xlsx": ["Excel files", "*.xlsx"]
    }

    ext = export_type.lower()
    if ext not in filetypes:
        messagebox.showerror("Export Error", f"Unsupported format: {ext}")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=f".{ext}", filetypes=[filetypes[ext]])
    if not file_path:
        return

    df = pd.DataFrame(data)
    try:
        if ext == "json":
            df.to_json(file_path, orient="records", indent=2)
        elif ext == "html":
            df.to_html(file_path, index=False)
        elif ext == "txt":
            with open(file_path, "w") as f:
                f.write(df.to_string(index=False))
        elif ext == "xlsx":
            df.to_excel(file_path, index=False)
        messagebox.showinfo("Export", f"Data exported to {file_path}")
    except Exception as e:
        messagebox.showerror("Export Error", str(e))

class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Inventory Manager")
        self.style = tb.Style("flatly")
     #  self.style = tb.Style("darkly")
        self.data = get_filtered_data()
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.refresh_table())

        self.tenant_filter = tk.StringVar(value=current_user if current_user != ADMIN else "")
        self.project_filter = tk.StringVar()

        self.full_data = load_data()
        self.columns = list(self.full_data[0].keys()) if self.full_data else ["Item", "Quantity", "Description", PROJECT_FIELD, TENANT_FIELD, LAST_UPDATED_FIELD]

        self.search_box = ttk.Entry(root, textvariable=self.search_var)
        self.search_box.pack(fill="x", padx=5, pady=5, expand=True)

        filter_frame = ttk.Frame(root, padding=5)
        filter_frame.pack(fill="x", padx=5, expand=True)

        if current_user == ADMIN:
            ttk.Label(filter_frame, text="Tenant:").pack(side="left")
            self.tenant_entry = ttk.Combobox(filter_frame, textvariable=self.tenant_filter, values=self.get_unique_values(TENANT_FIELD))
            self.tenant_entry.pack(side="left", padx=5)

        ttk.Label(filter_frame, text="Project:").pack(side="left")
        self.project_entry = ttk.Combobox(filter_frame, textvariable=self.project_filter, values=self.get_unique_values(PROJECT_FIELD))
        self.project_entry.pack(side="left", padx=5)

        self.tree = ttk.Treeview(root, columns=self.columns, show="headings")
        for col in self.columns:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<Double-1>", self.edit_entry)

        self.update_treeview()

        self.add_controls()
        self.refresh_table()

    def sort_by_column(self, col, reverse):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        data.sort(reverse=reverse)
        for index, (val, k) in enumerate(data):
            self.tree.move(k, "", index)
        self.tree.heading(col, command=lambda: self.sort_by_column(col, not reverse))
      

    def update_treeview(self):
        query = self.search_var.get().lower().strip()
        self.tree.delete(*self.tree.get_children())
        for row in self.data:
            if any(query in str(value).lower() for value in row.values()):
                self.tree.insert("", "end", values=[row[col] for col in self.tree["columns"]])        

    def get_unique_values(self, key):
        return sorted(list(set(row.get(key, "") for row in self.full_data if row.get(key))))

    def refresh_table(self):
        query = self.search_var.get().lower()
        tenant_query = self.tenant_filter.get().strip().lower()
        project_query = self.project_filter.get().strip().lower()

        self.tree.delete(*self.tree.get_children())
        filtered = []
        for row in self.full_data:
            row_str = json.dumps(row).lower()
            tenant_match = (current_user == ADMIN and (not tenant_query or row.get(TENANT_FIELD, "").lower() == tenant_query)) or (row.get(TENANT_FIELD) == current_user)
            project_match = project_query in row.get(PROJECT_FIELD, "").lower()
            if query in row_str and tenant_match and project_match:
                filtered.append(row)

        for row in filtered:
            self.tree.insert("", "end", values=[row.get(col, "") for col in self.columns])

    def add_controls(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="x")

        ttk.Button(frame, text="Add/Edit Entry", command=self.add_or_edit_entry).pack(side="left", padx=5, pady=5)
        ttk.Button(frame, text="Delete Selected", command=self.delete_entry).pack(side="left", padx=5, pady=5)
        ttk.Button(frame, text="Export Data", command=lambda: export_data(self.get_displayed_data())).pack(side="left", padx=5, pady=5)

    def add_or_edit_entry(self):
        self.entry_window(None)
        
    def edit_entry(self, event):
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])["values"]
            self.entry_window(item)

    def entry_window(self, existing_entry):
        entry_data = {}
        popup = tk.Toplevel(self.root)
        popup.title("Entry Details")

        entries = {}
        for col in self.columns:
            frame = ttk.Frame(popup)
            frame.pack(fill="x", padx=5, pady=2)
            ttk.Label(frame, text=col, width=15).pack(side="left")
            var = tk.StringVar(value=existing_entry[self.columns.index(col)] if existing_entry else "")
            entry = ttk.Entry(frame, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)
            entries[col] = var

        def save():
            for col, var in entries.items():
                entry_data[col] = var.get()
            entry_data[LAST_UPDATED_FIELD] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if current_user != ADMIN:
                entry_data[TENANT_FIELD] = current_user

            for i, row in enumerate(self.full_data):
                if existing_entry and [row.get(col, "") for col in self.columns] == list(existing_entry):
                    if current_user == ADMIN or row.get(TENANT_FIELD) == current_user:
                        self.full_data[i] = entry_data
                    break
            else:
                self.full_data.append(entry_data)

            save_data(self.full_data)
            popup.destroy()
            self.refresh_table()

        ttk.Button(popup, text="Save", command=save).pack(pady=5)

    def delete_entry(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Delete", "No item selected")
            return

        values_to_delete = [self.tree.item(i)["values"] for i in selected]
        new_data = []
        for row in self.full_data:
            if [row.get(col, "") for col in self.columns] in values_to_delete:
                if current_user == ADMIN or row.get(TENANT_FIELD) == current_user:
                    continue
            new_data.append(row)

        self.full_data = new_data
        save_data(self.full_data)
        self.refresh_table()

    def get_displayed_data(self):
        displayed = []
        for child in self.tree.get_children():
            values = self.tree.item(child)["values"]
            displayed.append(dict(zip(self.columns, values)))
        return displayed

root = tb.Window(themename="flatly")
app = InventoryApp(root)
root.mainloop()
