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

    def cancel(self):
        if self.status in ["canceled", "success", "error"]:
            return False
        
        frappe.cancel(self.name)
        
        self.status = "canceled"
        self.save(ignore_permissions=True)
        if not frappe.flags.in_test:
            frappe.db.commit()
        return True

    def delete(self):
        if self.status in ["running", "waiting", "queued"]:
            self.cancel()
        super().delete()

def cancel_bulk(frappe_filter=None):
    if frappe_filter is None:
        raise ValueError("Filter must be provided for cancel_bulk")
    
    if isinstance(frappe_filter, dict) and "status" not in frappe_filter:
        frappe_filter["status"] = ["in", ["queued", "running", "waiting"]]
        
    executions = frappe.get_all("Playbook Execution", filters=frappe_filter, fields=["name"])
    for ex in executions:
        try:
            doc = frappe.get_doc("Playbook Execution", ex.name)
            doc.cancel()
        except Exception as e:
            frappe.log_error(f"Error bulk-cancelling execution {ex.name}: {str(e)}", "Playbook Execution Bulk Cancel Error")

def delete_bulk(frappe_filter=None):
    if frappe_filter is None:
        raise ValueError("Filter must be provided for delete_bulk")
        
    executions = frappe.get_all("Playbook Execution", filters=frappe_filter, fields=["name"])
    count = 0
    for ex in executions:
        try:
            doc = frappe.get_doc("Playbook Execution", ex.name)
            doc.delete()
            count += 1
            if count % 50 == 0 and not frappe.flags.in_test:
                frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Error bulk-deleting execution {ex.name}: {str(e)}", "Playbook Execution Bulk Delete Error")
    if count > 0 and not frappe.flags.in_test:
        frappe.db.commit()

def queue_trigger_execution(playbook_doc, reference_doctype, reference_name, payload, execution_name, as_child=True, playbook_event=None):
    enqueue(
        "frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.run",
        playbook_name=playbook_doc.name,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        payload=payload,
        execution_name=execution_name,
        as_child=as_child,
        playbook_event=playbook_event
    )
    
def queue_resume_execution(execution_doc, response_body):
    if isinstance(execution_doc, str):
        execution_name = execution_doc
    else:
        execution_name = execution_doc.name
        
    if not frappe.db.exists("Playbook Execution", execution_name):
        return
    status = frappe.db.get_value("Playbook Execution", execution_name, "status")
    if status == "canceled":
        return
        
    if isinstance(execution_doc, str):
        execution_doc = frappe.get_doc("Playbook Execution", execution_name)
        
    emit_event(key=f"playbook_resume_{execution_doc.name}", argument={"response": response_body})

def run(playbook_name, reference_doctype, reference_name, payload, execution_name, playbook_event=None):
    # Native execution logic goes here
    # Idempotency check / Exists / Canceled check
    if frappe.db.exists("Playbook Execution", execution_name):
        status = frappe.db.get_value("Playbook Execution", execution_name, "status")
        if status == "canceled":
            return
        return

    # Create Playbook Execution
    execution_doc = frappe.get_doc({
        "doctype": "Playbook Execution",
        "name": execution_name,
        "playbook": playbook_name,
        "playbook_event": playbook_event,
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
