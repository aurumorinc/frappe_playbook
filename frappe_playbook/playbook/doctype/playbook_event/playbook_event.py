import frappe
from frappe.model.document import Document
from frappe_controller.utils.background_jobs import enqueue

class PlaybookEvent(Document):
    def after_insert(self):
        enqueue("frappe_playbook.playbook.doctype.playbook_event.playbook_event.queue_trigger_execution", event_name=self.name, as_child=False)

    def on_trash(self):
        executions = frappe.get_all("Playbook Execution", filters={"playbook_event": self.name}, fields=["name"])
        for ex in executions:
            try:
                doc = frappe.get_doc("Playbook Execution", ex.name)
                doc.delete()
            except Exception as e:
                frappe.log_error(f"Error deleting cascade execution {ex.name} from event {self.name}: {str(e)}", "Playbook Event Cascade Delete Error")

def queue_trigger_execution(event_name):
    if not frappe.db.exists("Playbook Event", event_name):
        return
        
    event_doc = frappe.get_doc("Playbook Event", event_name)
    
    if not frappe.db.exists(event_doc.reference_doctype, event_doc.reference_name):
        return
        
    doc = frappe.get_doc(event_doc.reference_doctype, event_doc.reference_name)
    
    playbooks = []
    if event_doc.playbook:
        if frappe.db.exists("Playbook", event_doc.playbook):
            pb_doc = frappe.get_doc("Playbook", event_doc.playbook)
            if not pb_doc.enabled:
                from frappe_controller.utils.controller import wait_for_event
                wait_for_event(
                    event_key=f"doc:Playbook:on_update:{pb_doc.name}",
                    condition="argument.get('enabled') == 1"
                )
                pb_doc.reload()
                
            if pb_doc.enabled:
                playbooks.append(frappe._dict(name=event_doc.playbook))
    else:
        # Fallback for events without a pre-linked playbook (only get active ones)
        playbooks = frappe.get_all(
            "Playbook",
            filters={
                "document_type": doc.doctype,
                "doc_event": event_doc.event_type,
                "enabled": 1
            }
        )
    
    from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_trigger_execution as native_queue_trigger_execution
    
    for pb in playbooks:
        playbook_doc = frappe.get_doc("Playbook", pb.name)
        if playbook_doc.meets_condition(doc):
            payload = doc.as_dict(convert_dates_to_str=True)
            execution_name = frappe.generate_hash(length=10)
            
            native_queue_trigger_execution(
                playbook_doc,
                doc.doctype,
                doc.name,
                payload,
                execution_name,
                as_child=False,
                playbook_event=event_doc.name
            )
