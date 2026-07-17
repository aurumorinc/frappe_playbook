import frappe
from frappe.model.document import Document
from frappe_controller.utils.background_jobs import enqueue
from frappe_controller.utils.controller import emit_event

class PlaybookExecution(Document):
    def validate(self):
        old_doc = self.get_doc_before_save()
        if old_doc:
            valid_transitions = {
                "queued": ["running", "canceled"],
                "running": ["waiting", "success", "error", "canceled"],
                "waiting": ["running", "canceled"],
                "success": [],
                "error": [],
                "canceled": []
            }
            if self.status != old_doc.status and self.status not in valid_transitions.get(old_doc.status, []):
                frappe.throw(f"Invalid status transition from {old_doc.status} to {self.status}")

    def on_update(self):
        pass

def queue_trigger_execution(playbook_doc, reference_doctype, reference_name, payload, execution_name, as_child=True):
    enqueue(
        "frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.run",
        playbook_name=playbook_doc.name,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        payload=payload,
        execution_name=execution_name,
        as_child=as_child
    )
    
def queue_resume_execution(execution_doc, response_body):
    emit_event(key=f"playbook_resume_{execution_doc.name}", argument={"response": response_body})

def run(playbook_name, reference_doctype, reference_name, payload, execution_name):
    # Native execution logic goes here
    # Idempotency check
    if frappe.db.exists("Playbook Execution", execution_name):
        return

    # Create Playbook Execution
    execution_doc = frappe.get_doc({
        "doctype": "Playbook Execution",
        "name": execution_name,
        "playbook": playbook_name,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "status": "queued",
        "execution_data": frappe.as_json(payload)
    })
    execution_doc.insert(ignore_permissions=True)
    if not frappe.flags.in_test:
        frappe.db.commit()

def test_run(playbook_name, reference_doctype, reference_name, payload, execution_name):
    # Native test execution acts as a no-op and does not create a Playbook Execution document
    pass

@frappe.whitelist()
def get_debug_url(execution_name):
    return None

@frappe.whitelist()
def replay(execution_name):
    pass
