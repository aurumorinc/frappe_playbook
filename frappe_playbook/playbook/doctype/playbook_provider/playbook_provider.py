import frappe
from frappe.model.document import Document

class PlaybookProviderBase:
    def create_workflow(self, playbook_doc):
        raise NotImplementedError

    def delete_workflow(self, playbook_doc):
        raise NotImplementedError

    def get_builder_url(self, playbook_doc):
        raise NotImplementedError
        
    def toggle_workflow_status(self, playbook_doc, is_active: bool):
        """Activate or deactivate the workflow in the external provider"""
        raise NotImplementedError
        
    def queue_trigger_execution(self, playbook_doc, reference_doctype, reference_name, payload, idempotency_key, as_child=True):
        raise NotImplementedError
        
    def queue_test_execution(self, playbook_doc, reference_doctype, reference_name, payload, idempotency_key, as_child=True):
        raise NotImplementedError
        
    def queue_resume_execution(self, execution_doc, response_body, callback_url, idempotency_key=None):
        raise NotImplementedError
        
    def get_execution_status(self, execution_id):
        raise NotImplementedError
        
    def retry_execution(self, execution_id):
        raise NotImplementedError
        
    def stop_execution(self, execution_doc):
        raise NotImplementedError

class PlaybookProvider(Document):
    def on_update(self):
        if self.has_value_changed("enabled"):
            self.sync_playbooks_status()

    def sync_playbooks_status(self):
        playbooks = frappe.get_all("Playbook", filters={"provider": self.name, "is_active": 1})
        if not playbooks:
            return
            
        try:
            provider_instance = get_provider_instance(self.name)
            for pb in playbooks:
                doc = frappe.get_doc("Playbook", pb.name)
                provider_instance.toggle_workflow_status(doc, bool(self.enabled))
        except Exception as e:
            frappe.log_error(f"Failed to sync playbooks status for provider {self.name}: {str(e)}", "Playbook Provider Sync Error")

def get_provider_instance(provider_name):
    registered_providers = frappe.get_hooks("playbook_providers")
    if not registered_providers:
        frappe.throw(f"No playbook providers registered.")
        
    class_path = registered_providers.get(provider_name)
    
    if not class_path:
        frappe.throw(f"Provider plugin for {provider_name} is not installed.")
        
    ProviderClass = frappe.get_attr(class_path[0])
    return ProviderClass()

def delete_workflow(provider, workflow_id):
    if not provider or not workflow_id:
        return
    try:
        provider_instance = get_provider_instance(provider)
        # We need a dummy doc to pass to delete_workflow since it expects playbook_doc
        # But since the playbook is already deleted, we just pass an object with the workflow_id
        dummy_doc = frappe._dict({f"{provider.lower()}_workflow_id": workflow_id, "n8n_workflow_id": workflow_id})
        provider_instance.delete_workflow(dummy_doc)
    except Exception as e:
        frappe.log_error(f"Failed to delete workflow {workflow_id} in provider {provider}: {str(e)}", "Playbook Provider Error")
        raise
