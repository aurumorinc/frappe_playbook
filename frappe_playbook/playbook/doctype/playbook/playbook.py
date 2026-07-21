import frappe
from frappe.model.document import Document
from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_trigger_execution
from frappe_controller.utils.background_jobs import enqueue

class Playbook(Document):
    def validate(self):
        if not self.provider:
            default_provider = frappe.db.get_value("Playbook Provider", {"is_default": 1, "enabled": 1}, "name")
            if default_provider:
                self.provider = default_provider

        if self.condition_type == "Python" and self.condition:
            import ast
            try:
                ast.parse(self.condition)
            except SyntaxError as e:
                frappe.throw(f"Invalid Python condition: {str(e)}")
        elif self.condition_type == "Filters" and self.filters:
            from frappe.model import default_fields
            for f in self.filters:
                if not frappe.get_meta(self.document_type).has_field(f.fieldname) and f.fieldname not in default_fields:
                    frappe.throw(f"Field {f.fieldname} does not exist in DocType {self.document_type}")
        
        if self.status == "Draft":
            self.enabled = 0
        elif self.status in ["Enabled", "Disabled"]:
            self.status = "Enabled" if self.enabled else "Disabled"

    def before_save(self):
        if not self.is_new():
            doc_before_save = self.get_doc_before_save()
            if doc_before_save and doc_before_save.provider and doc_before_save.provider == self.provider:
                field_name = f"{self.provider.lower()}_workflow_id"
                if self.meta.has_field(field_name):
                    old_val = frappe.db.get_value("Playbook", self.name, field_name)
                    if old_val and not self.get(field_name):
                        self.set(field_name, old_val)

    def after_insert(self):
        pass

    def on_update(self):
        pass

    def meets_condition(self, doc: Document) -> bool:
        if self.condition_type == "Python" and self.condition:
            try:
                return frappe.safe_eval(self.condition, eval_locals={"doc": doc})
            except Exception as e:
                frappe.log_error(f"Failed to evaluate Python condition for Playbook {self.name}: {str(e)}", "Playbook Condition Error")
                return False
        elif self.condition_type == "Filters" and self.filters:
            from frappe.utils.data import evaluate_filters
            try:
                parsed_filters = {f.fieldname: [f.operator, f.value] for f in self.filters}
                return evaluate_filters(doc, parsed_filters)
            except Exception as e:
                frappe.log_error(f"Failed to evaluate Filters condition for Playbook {self.name}: {str(e)}", "Playbook Condition Error")
                return False
        return True

    def on_trash(self):
        # Delete associated Playbook Events which cascades to delete Playbook Executions
        events = frappe.get_all("Playbook Event", filters={"playbook": self.name}, fields=["name"])
        for ev in events:
            try:
                frappe.delete_doc("Playbook Event", ev.name, ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Error cascade deleting playbook event {ev.name} from playbook {self.name}: {str(e)}", "Playbook Cascade Delete Event Error")

        # Fallback/Guard: Delete any remaining executions for this playbook
        from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import delete_bulk
        try:
            delete_bulk({"playbook": self.name})
        except Exception as e:
            frappe.log_error(f"Error fallback cascade deleting executions for playbook {self.name}: {str(e)}", "Playbook Cascade Delete Execution Fallback Error")

def create_playbook_event(doc, method):
    if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
        return
        
    if doc.doctype in ("FS Job", "FS Event", "FS Match Condition", "Error Log", "Controller Job Log", "Controller Job Type", "Playbook Execution", "Playbook Event"):
        return

    # Find all matching enabled playbooks
    playbooks = frappe.get_all(
        "Playbook",
        filters={
            "document_type": doc.doctype,
            "doc_event": method,
            "enabled": 1
        },
        fields=["name"]
    )
    
    for pb in playbooks:
        try:
            event_doc = frappe.get_doc({
                "doctype": "Playbook Event",
                "playbook": pb.name,
                "reference_doctype": doc.doctype,
                "reference_name": doc.name,
                "event_type": method
            })
            event_doc.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error creating playbook event for playbook {pb.name}: {str(e)}", "Create Playbook Event Error")

@frappe.whitelist()
def get_builder_url(playbook_name):
    return None

@frappe.whitelist()
def trigger_test_execution(playbook_name):
    pass
