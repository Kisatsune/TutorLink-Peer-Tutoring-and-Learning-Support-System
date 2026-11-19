
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from api_client import DEFAULT_BASE_URL, ApiError, TutorLinkClient


def choice_id(value):
    """'3 - maria_t'  ->  '3'  (choice boxes show 'id - name')."""
    return value.split(" - ")[0].strip()


# Reusable pieces
class FormDialog(tk.Toplevel):
   
    def __init__(self, parent, title, fields, on_submit):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.on_submit = on_submit
        self.widgets = {}

        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)

        for row, field in enumerate(fields):
            ttk.Label(body, text=field["label"]).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=4)
            kind = field.get("kind", "entry")
            default = field.get("default", "")
            if kind == "text":
                widget = tk.Text(body, width=34, height=4)
                widget.insert("1.0", default)
            elif kind == "choice":
                widget = ttk.Combobox(body, values=field["choices"], state="readonly", width=32)
                if default in field["choices"]:
                    widget.set(default)
                elif field["choices"]:
                    widget.current(0)
            else:
                widget = ttk.Entry(body, width=36)
                widget.insert(0, default)
            widget.grid(row=row, column=1, pady=4)
            self.widgets[field["key"]] = (kind, widget)

        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Save", command=self._submit).pack(side="right")

        self.transient(parent)
        self.grab_set()  # modal: the dashboard is blocked until the dialog closes

    def values(self):
        result = {}
        for key, (kind, widget) in self.widgets.items():
            result[key] = widget.get("1.0", "end").strip() if kind == "text" else widget.get().strip()
        return result

    def _submit(self):
        try:
            self.on_submit(self.values())
        except ApiError as error:
            messagebox.showerror("Could not save", str(error), parent=self)
            return
        self.destroy()


class DataTab(ttk.Frame):
    
    columns = ()  # (key, heading, width)

    def __init__(self, parent, client):
        super().__init__(parent, padding=8)
        self.client = client
        self.rows = {}

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))
        self.build_toolbar(toolbar)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="right")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        keys = [column[0] for column in self.columns]
        self.tree = ttk.Treeview(container, columns=keys, show="headings", selectmode="browse")
        for key, heading, width in self.columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def build_toolbar(self, toolbar):
        pass

    def fetch(self):
        raise NotImplementedError

    def refresh(self):
        try:
            items = self.fetch()
        except ApiError as error:
            messagebox.showerror("Could not load data", str(error))
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for item in items:
            row_id = self.tree.insert("", "end", values=[item.get(key, "") for key, _, _ in self.columns])
            self.rows[row_id] = item

    def selected(self, need="a row"):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a row", f"Please select {need} first.")
            return None
        return self.rows[selection[0]]


# Tabs
class UsersTab(DataTab):
    columns = (
        ("id", "ID", 45), ("username", "Username", 110), ("full_name", "Name", 150),
        ("email", "Email", 170), ("role", "Role", 70), ("course", "Course", 160),
        ("year_level", "Year", 45), ("approval_status", "Approval", 80),
    )
    FILTERS = {
        "All users": {},
        "Pending tutors": {"role": "tutor", "status": "pending"},
        "Tutors": {"role": "tutor"},
        "Students": {"role": "student"},
    }

    def build_toolbar(self, toolbar):
        self.filter_box = ttk.Combobox(toolbar, values=list(self.FILTERS), state="readonly", width=16)
        self.filter_box.current(0)
        self.filter_box.pack(side="left")
        self.filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Button(toolbar, text="Approve tutor", command=lambda: self.decide(True)).pack(side="left", padx=(10, 4))
        ttk.Button(toolbar, text="Reject tutor", command=lambda: self.decide(False)).pack(side="left")

    def fetch(self):
        return self.client.list_users(**self.FILTERS[self.filter_box.get()])

    def decide(self, approve):
        user = self.selected("a tutor")
        if user is None:
            return
        if user["role"] != "tutor":
            messagebox.showwarning("Not a tutor", "Only tutor applications can be approved or rejected.")
            return
        try:
            self.client.set_approval(user["id"], approve)
        except ApiError as error:
            messagebox.showerror("Error", str(error))
            return
        self.refresh()


class SubjectsTab(DataTab):
    columns = (("id", "ID", 50), ("name", "Name", 200), ("description", "Description", 520))

    def build_toolbar(self, toolbar):
        ttk.Button(toolbar, text="Add", command=self.add).pack(side="left")
        ttk.Button(toolbar, text="Edit", command=self.edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self.delete).pack(side="left")

    def fetch(self):
        return self.client.list_subjects()

    def _fields(self, subject=None):
        subject = subject or {}
        return [
            {"key": "name", "label": "Name", "default": subject.get("name", "")},
            {"key": "description", "label": "Description", "kind": "text",
             "default": subject.get("description", "")},
        ]

    def add(self):
        def save(values):
            self.client.create_subject(values)
            self.refresh()
        FormDialog(self, "Add subject", self._fields(), save)

    def edit(self):
        subject = self.selected("a subject")
        if subject is None:
            return

        def save(values):
            self.client.update_subject(subject["id"], values)
            self.refresh()
        FormDialog(self, "Edit subject", self._fields(subject), save)

    def delete(self):
        subject = self.selected("a subject")
        if subject is None:
            return
        if not messagebox.askyesno("Delete subject", f"Delete '{subject['name']}'?"):
            return
        try:
            self.client.delete_subject(subject["id"])
        except ApiError as error:
            messagebox.showerror("Could not delete", str(error))
            return
        self.refresh()


class SessionsTab(DataTab):
    columns = (
        ("id", "ID", 40), ("subject", "Subject", 110), ("tutor", "Tutor", 90), ("topic", "Topic", 170),
        ("date", "Date", 85), ("start_time", "Time", 55), ("duration_minutes", "Min", 45),
        ("booked", "Booked", 55), ("slots", "Slots", 50), ("status", "Status", 80), ("location", "Location", 110),
    )
    STATUSES = ["open", "full", "completed", "cancelled"]

    def build_toolbar(self, toolbar):
        ttk.Button(toolbar, text="Add", command=self.add).pack(side="left")
        ttk.Button(toolbar, text="Edit", command=self.edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self.delete).pack(side="left")

    def fetch(self):
        return self.client.list_sessions()

    def _fields(self, session=None):
        tutors = [f"{u['id']} - {u['username']}"
                  for u in self.client.list_users(role="tutor", status="approved")]
        subjects = [f"{s['id']} - {s['name']}" for s in self.client.list_subjects()]
        s = session or {}
        return [
            {"key": "tutor", "label": "Tutor", "kind": "choice", "choices": tutors,
             "default": f"{s.get('tutor_id')} - {s.get('tutor')}" if s else ""},
            {"key": "subject", "label": "Subject", "kind": "choice", "choices": subjects,
             "default": f"{s.get('subject_id')} - {s.get('subject')}" if s else ""},
            {"key": "topic", "label": "Topic", "default": s.get("topic", "")},
            {"key": "date", "label": "Date (YYYY-MM-DD)", "default": s.get("date", date.today().isoformat())},
            {"key": "start_time", "label": "Start time (HH:MM)", "default": s.get("start_time", "15:00")},
            {"key": "duration_minutes", "label": "Duration (minutes)", "default": s.get("duration_minutes", "60")},
            {"key": "slots", "label": "Slots", "default": s.get("slots", "3")},
            {"key": "status", "label": "Status", "kind": "choice", "choices": self.STATUSES,
             "default": s.get("status", "open")},
            {"key": "location", "label": "Location", "default": s.get("location", "")},
        ]

    @staticmethod
    def _payload(values):
        data = dict(values)
        data["tutor"] = choice_id(data["tutor"])
        data["subject"] = choice_id(data["subject"])
        return data

    def add(self):
        try:
            fields = self._fields()
        except ApiError as error:
            messagebox.showerror("Error", str(error))
            return

        def save(values):
            self.client.create_session(self._payload(values))
            self.refresh()
        FormDialog(self, "Add session", fields, save)

    def edit(self):
        session = self.selected("a session")
        if session is None:
            return
        try:
            fields = self._fields(session)
        except ApiError as error:
            messagebox.showerror("Error", str(error))
            return

        def save(values):
            self.client.update_session(session["id"], self._payload(values))
            self.refresh()
        FormDialog(self, "Edit session", fields, save)

    def delete(self):
        session = self.selected("a session")
        if session is None:
            return
        if not messagebox.askyesno(
            "Delete session", f"Delete the {session['subject']} session on {session['date']}?\n"
                              "Its bookings will be deleted too."):
            return
        try:
            self.client.delete_session(session["id"])
        except ApiError as error:
            messagebox.showerror("Could not delete", str(error))
            return
        self.refresh()


class BookingsTab(DataTab):
    columns = (
        ("id", "ID", 45), ("student", "Student", 120), ("subject", "Subject", 130),
        ("tutor", "Tutor", 110), ("date", "Session date", 100), ("status", "Status", 90), ("rating", "Rating", 60),
    )

    def fetch(self):
        return self.client.list_bookings()


class StatsTab(ttk.Frame):
    TOTAL_LABELS = [
        ("students", "Students"), ("tutors", "Approved tutors"), ("pending_tutors", "Pending tutors"),
        ("subjects", "Subjects"), ("sessions", "Sessions"), ("bookings", "Active bookings"),
        ("feedback", "Feedback entries"),
    ]

    def __init__(self, parent, client):
        super().__init__(parent, padding=8)
        self.client = client

        top = ttk.Frame(self)
        top.pack(fill="x")
        self.hours_label = ttk.Label(top, text="Total tutoring hours: -", font=("Segoe UI", 14, "bold"))
        self.hours_label.pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        self.totals_frame = ttk.LabelFrame(self, text="Overview", padding=8)
        self.totals_frame.pack(fill="x", pady=8)
        self.total_values = {}
        for index, (key, label) in enumerate(self.TOTAL_LABELS):
            ttk.Label(self.totals_frame, text=label).grid(row=0, column=index, padx=10)
            value = ttk.Label(self.totals_frame, text="-", font=("Segoe UI", 16, "bold"))
            value.grid(row=1, column=index, padx=10)
            self.total_values[key] = value

        tables = ttk.Frame(self)
        tables.pack(fill="both", expand=True)
        left = ttk.LabelFrame(tables, text="Sessions per subject", padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ttk.LabelFrame(tables, text="Top-rated tutors", padding=6)
        right.pack(side="left", fill="both", expand=True)

        self.subject_tree = ttk.Treeview(left, columns=("name", "sessions"), show="headings", height=8)
        self.subject_tree.heading("name", text="Subject")
        self.subject_tree.heading("sessions", text="Sessions")
        self.subject_tree.column("sessions", width=80, anchor="center")
        self.subject_tree.pack(fill="both", expand=True)

        self.tutor_tree = ttk.Treeview(right, columns=("name", "average_rating", "reviews"),
                                       show="headings", height=8)
        self.tutor_tree.heading("name", text="Tutor")
        self.tutor_tree.heading("average_rating", text="Avg rating")
        self.tutor_tree.heading("reviews", text="Reviews")
        self.tutor_tree.column("average_rating", width=90, anchor="center")
        self.tutor_tree.column("reviews", width=70, anchor="center")
        self.tutor_tree.pack(fill="both", expand=True)

    def refresh(self):
        try:
            data = self.client.stats()
        except ApiError as error:
            messagebox.showerror("Could not load statistics", str(error))
            return
        for key, label in self.total_values.items():
            label.config(text=data["totals"].get(key, "-"))
        hours = data["hours"]
        self.hours_label.config(
            text=f"Total tutoring hours: {hours.get('total_hours', '0')} "
                 f"({hours.get('completed_sessions', '0')} completed sessions)")
        self.subject_tree.delete(*self.subject_tree.get_children())
        for row in data["per_subject"]:
            self.subject_tree.insert("", "end", values=(row["name"], row["sessions"]))
        self.tutor_tree.delete(*self.tutor_tree.get_children())
        for row in data["top_tutors"]:
            self.tutor_tree.insert("", "end", values=(row["name"], row["average_rating"], row["reviews"]))


# Application window
class LoginFrame(ttk.Frame):
    def __init__(self, parent, client, on_success):
        super().__init__(parent, padding=30)
        self.client = client
        self.on_success = on_success

        ttk.Label(self, text="TutorLink Admin", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(self, text="Administrators only", foreground="#667085").grid(row=1, column=0, columnspan=2, pady=(0, 16))

        self.server = tk.StringVar(value=DEFAULT_BASE_URL)
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        for row, (label, variable, secret) in enumerate(
                [("Server API URL", self.server, False), ("Username", self.username, False),
                 ("Password", self.password, True)], start=2):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
            entry = ttk.Entry(self, textvariable=variable, width=34, show="*" if secret else "")
            entry.grid(row=row, column=1, pady=4)
            if label == "Username":
                entry.focus()
            entry.bind("<Return>", lambda _event: self.login())
        ttk.Button(self, text="Log in", command=self.login).grid(row=5, column=0, columnspan=2, pady=(14, 0))

    def login(self):
        self.client.base_url = self.server.get().strip().rstrip("/") + "/"
        try:
            self.client.login(self.username.get().strip(), self.password.get())
        except ApiError as error:
            messagebox.showerror("Login failed", str(error))
            return
        self.on_success()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TutorLink Admin Dashboard")
        self.geometry("1020x600")
        self.minsize(900, 520)
        self.client = TutorLinkClient()
        self.show_login()

    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def show_login(self):
        self.clear()
        LoginFrame(self, self.client, self.show_dashboard).pack(expand=True)

    def show_dashboard(self):
        self.clear()
        header = ttk.Frame(self, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="TutorLink Admin Dashboard", font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Log out", command=self.logout).pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tabs = [
            ("Statistics", StatsTab(notebook, self.client)),
            ("Users", UsersTab(notebook, self.client)),
            ("Subjects", SubjectsTab(notebook, self.client)),
            ("Sessions", SessionsTab(notebook, self.client)),
            ("Bookings", BookingsTab(notebook, self.client)),
        ]
        for title, tab in self.tabs:
            notebook.add(tab, text=title)
            tab.refresh()
        # Reload a tab's data every time it is opened, so the numbers are never stale.
        notebook.bind("<<NotebookTabChanged>>",
                      lambda _event: self.tabs[notebook.index("current")][1].refresh())

    def logout(self):
        try:
            self.client.logout()
        except ApiError:
            pass
        self.show_login()


if __name__ == "__main__":
    App().mainloop()
