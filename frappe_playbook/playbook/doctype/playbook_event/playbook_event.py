import frappe
from frappe.model.document import Document
from frappe_controller.utils.background_jobs import enqueue

class PlaybookEvent(Document):
    def after_insert(self):
        enqueue("frappe_playbook.playbook.doctype.playbook_event.playbook_event.queue_trigger_execution", event_name=self.name)

def queue_trigger_execution(event_name):
    if not frappe.db.exists("Playbook Event", event_name):
        return
        
    event_doc = frappe.get_doc("Playbook Event", event_name)
    
    if not frappe.db.exists(event_doc.reference_doctype, event_doc.reference_name):
        return
        
    doc = frappe.get_doc(event_doc.reference_doctype, event_doc.reference_name)
    
    playbooks = frappe.get_all(
        "Playbook",
        filters={
            "document_type": doc.doctype,
            "doc_event": event_doc.event_type,
            "is_active": 1
        }
    )
    
    from frappe_playbook.playbook.doctype.playbook_provider.playbook_provider import get_provider_instance
    from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_trigger_execution as native_queue_trigger_execution
    
    for pb in playbooks:
        playbook_doc = frappe.get_doc("Playbook", pb.name)
        if playbook_doc.meets_condition(doc):
            payload = {"doc": doc.as_dict(convert_dates_to_str=True)}
            idempotency_key = f"{playbook_doc.name}-{event_doc.name}"
            
            if playbook_doc.provider:
                provider_instance = get_provider_instance(playbook_doc.provider)
                provider_instance.queue_trigger_execution(
                    playbook_doc,
                    doc.doctype,
                    doc.name,
                    payload,
                    idempotency_key,
                    as_child=False
                )
            else:
                native_queue_trigger_execution(
                    playbook_doc,
                    doc.doctype,
                    doc.name,
                    payload,
                    idempotency_key,
                    as_child=False
                )
