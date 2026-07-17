import frappe
from frappe.model.document import Document

class PlaybookProvider(Document):
    def on_update(self):
        if getattr(self, "is_default", 0):
            frappe.db.sql("""update `tabPlaybook Provider` set is_default=0 where name!=%s""", self.name)
