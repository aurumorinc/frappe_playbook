import frappe
from frappe.model.document import Document
from frappe_playbook.playbook.doctype.playbook_provider.playbook_provider import get_provider_instance
from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_trigger_execution
from frappe_controller.utils.background_jobs import enqueue

class Playbook(Document):
    def validate(self):
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
            self.is_active = 0
        elif self.status in ["Enabled", "Disabled"]:
            self.status = "Enabled" if self.is_active else "Disabled"

    def after_insert(self):
        if self.status == "Draft" or self.provider:
            enqueue("frappe_playbook.playbook.doctype.playbook.playbook.update_workflow", playbook_name=self.name)

    def on_update(self):
        if self.has_value_changed("status") or self.has_value_changed("is_active") or self.has_value_changed("provider"):
            enqueue("frappe_playbook.playbook.doctype.playbook.playbook.update_workflow", playbook_name=self.name)

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
        if self.provider:
            workflow_id = self.get(f"{self.provider.lower()}_workflow_id")
            if workflow_id:
                enqueue("frappe_playbook.playbook.doctype.playbook_provider.playbook_provider.delete_workflow", provider=self.provider, workflow_id=workflow_id)

def create_playbook_event(doc, method):
    if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
        return
        
    if doc.doctype in ("FS Job", "FS Event", "FS Match Condition", "Error Log", "Controller Job Log", "Controller Job Type", "Playbook Execution", "Playbook Event"):
        return

    # Map Frappe doc events to Playbook doc events
    event_map = {
        "after_insert": "New",
        "on_update": "Save",
        "on_submit": "Submit",
        "on_cancel": "Cancel",
        "on_trash": "Trash",
        "on_update_after_submit": "Save"
    }

    playbook_event = event_map.get(method)
    if not playbook_event:
        return

    # Only create event if there is at least one active playbook for this doctype and event
    has_playbooks = frappe.db.exists(
        "Playbook",
        {
            "document_type": doc.doctype,
            "doc_event": playbook_event,
            "is_active": 1
        }
    )
    
    if has_playbooks:
        event_doc = frappe.get_doc({
            "doctype": "Playbook Event",
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "event_type": playbook_event
        })
        event_doc.insert(ignore_permissions=True)

def update_workflow(playbook_name):
    if not frappe.db.exists("Playbook", playbook_name):
        return
    playbook_doc = frappe.get_doc("Playbook", playbook_name)
    if not playbook_doc.provider:
        return
        
    try:
        provider_instance = get_provider_instance(playbook_doc.provider)
        
        workflow_id = playbook_doc.get(f"{playbook_doc.provider.lower()}_workflow_id")
        if not workflow_id:
            workflow_id = provider_instance.create_workflow(playbook_doc)
            if workflow_id:
                field_name = f"{playbook_doc.provider.lower()}_workflow_id"
                if playbook_doc.meta.has_field(field_name):
                    playbook_doc.db_set(field_name, workflow_id)
        
        provider_instance.toggle_workflow_status(playbook_doc, bool(playbook_doc.is_active))
        
        playbook_doc.db_set('status', 'Enabled' if playbook_doc.is_active else 'Disabled')
    except Exception as e:
        frappe.log_error(f"Failed to sync workflow for Playbook {playbook_doc.name}: {str(e)}", "Playbook Provider Error")
        playbook_doc.db_set('status', 'Draft')
        playbook_doc.db_set('is_active', 0)
        raise

@frappe.whitelist()
def get_builder_url(playbook_name):
    doc = frappe.get_doc("Playbook", playbook_name)
    if doc.provider:
        provider_instance = get_provider_instance(doc.provider)
        return provider_instance.get_builder_url(doc)
    return None

@frappe.whitelist()
def trigger_test_execution(playbook_name):
    playbook_doc = frappe.get_doc("Playbook", playbook_name)
    
    waiting_exec = frappe.get_all(
        "Playbook Execution",
        filters={"playbook": playbook_name, "status": "waiting"},
        fields=["reference_doctype", "reference_name"],
        order_by="creation desc",
        limit=1
    )
    
    target_doc = None
    if waiting_exec:
        target_doc = frappe.get_doc(waiting_exec[0].reference_doctype, waiting_exec[0].reference_name)
    else:
        recent_docs = frappe.get_all(
            playbook_doc.document_type,
            order_by="creation desc",
            limit=50
        )
        for d in recent_docs:
            doc_instance = frappe.get_doc(playbook_doc.document_type, d.name)
            if playbook_doc.meets_condition(doc_instance):
                target_doc = doc_instance
                break
                
    if not target_doc:
        return {"status": "failed", "message": "No matching document found."}
        
    payload = {"doc": target_doc.as_dict(convert_dates_to_str=True)}
    idempotency_key = f"test-{playbook_doc.name}-{frappe.utils.now()}"
    
    if playbook_doc.provider:
        provider_instance = get_provider_instance(playbook_doc.provider)
        provider_instance.queue_test_execution(
            playbook_doc,
            target_doc.doctype,
            target_doc.name,
            payload,
            idempotency_key,
            as_child=False
        )
    else:
        from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_trigger_execution as native_queue_trigger_execution
        native_queue_trigger_execution(
            playbook_doc,
            target_doc.doctype,
            target_doc.name,
            payload,
            idempotency_key,
            as_child=False
        )
        
    return {"status": "success", "message": f"Test execution sent using {target_doc.doctype} {target_doc.name}"}
