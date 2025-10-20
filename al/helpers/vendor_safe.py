"""
Safe vendor operations with duplicate detection and verification.

All vendor database operations go through this layer for safety.
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from al.helpers.vendor_helper import VendorHelper, Vendor
from al.helpers.data_safety import (
    DuplicateChecker,
    ChangeVerifier,
    AuditEntry,
    get_audit_logger,
    PendingConfirmation
)

logger = logging.getLogger(__name__)


class SafeVendorOperations:
    """Safe wrapper for vendor operations with duplicate checking and verification."""

    def __init__(self, vendor_helper: Optional[VendorHelper] = None):
        """Initialize safe vendor operations."""
        self.vendor_helper = vendor_helper or VendorHelper()
        self.audit_logger = get_audit_logger()

    def add_vendor_safe(
        self,
        name: str,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        products: Optional[List[str]] = None,
        lead_time_days: Optional[int] = None,
        notes: Optional[str] = None,
        skip_duplicate_check: bool = False
    ) -> Dict[str, Any]:
        """
        Safely add a vendor with duplicate checking and verification.

        Args:
            name: Vendor name
            contact_name: Contact person name
            email: Contact email
            phone: Contact phone
            products: List of products they supply
            lead_time_days: Lead time in days
            notes: Additional notes
            skip_duplicate_check: If True, bypass duplicate check (user confirmed "trust me")

        Returns:
            Dict with status, message, duplicates (if any), verification result
        """
        operation_id = str(uuid.uuid4())[:8]

        intended_data = {
            "name": name,
            "contact_name": contact_name,
            "email": email,
            "phone": phone,
            "products": products or [],
            "lead_time_days": lead_time_days,
            "notes": notes
        }

        # Step 1: Check for duplicates (unless skipped)
        duplicates = []
        if not skip_duplicate_check:
            existing_vendors = self.vendor_helper.get_all_vendors()
            existing_vendor_data = [
                {
                    "id": v.name,  # Using name as ID for now
                    "name": v.name,
                    "email": v.email,
                    "phone": v.phone,
                    "products": v.products
                }
                for v in existing_vendors
            ]

            duplicate_matches = DuplicateChecker.check_vendor_duplicates(
                name=name,
                email=email,
                phone=phone,
                existing_vendors=existing_vendor_data
            )

            if duplicate_matches:
                # Found duplicates - need user confirmation
                duplicates_data = [d.to_dict() for d in duplicate_matches]

                # Store pending operation
                PendingConfirmation.add(
                    operation_id=operation_id,
                    operation="add_vendor",
                    entity_type="vendor",
                    intended_data=intended_data,
                    duplicates=duplicate_matches
                )

                # Log to audit
                audit_entry = AuditEntry(
                    timestamp=datetime.now().isoformat(),
                    operation="add_vendor",
                    entity_type="vendor",
                    user="jeff",
                    intended_data=intended_data,
                    duplicates_found=len(duplicate_matches),
                    duplicate_details=duplicates_data,
                    user_confirmed=None,
                    confirmation_choice=None,
                    result="pending",
                    verification=None,
                    notion_record_id=None,
                    actual_data=None
                )
                self.audit_logger.log(audit_entry)

                return {
                    "status": "duplicate_found",
                    "operation_id": operation_id,
                    "message": f"Found {len(duplicate_matches)} potential duplicate(s). Need confirmation.",
                    "duplicates": duplicates_data,
                    "intended_data": intended_data
                }

        # Step 2: No duplicates (or check skipped) - proceed with add
        try:
            vendor = self.vendor_helper.add_vendor(
                name=name,
                contact_name=contact_name,
                email=email,
                phone=phone,
                products=products,
                lead_time_days=lead_time_days,
                notes=notes
            )

            # Step 3: Verify the write
            actual_data = {
                "name": vendor.name,
                "contact_name": vendor.contact_name,
                "email": vendor.email,
                "phone": vendor.phone,
                "products": vendor.products,
                "lead_time_days": vendor.lead_time_days,
                "notes": vendor.notes
            }

            verification = ChangeVerifier.verify_record(
                intended_data=intended_data,
                actual_data=actual_data
            )

            # Step 4: Log to audit
            audit_entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                operation="add_vendor",
                entity_type="vendor",
                user="jeff",
                intended_data=intended_data,
                duplicates_found=len(duplicates),
                duplicate_details=[],
                user_confirmed=True if skip_duplicate_check else None,
                confirmation_choice="create_new" if skip_duplicate_check else None,
                result="success" if verification.passed else "verification_failed",
                verification=verification.to_dict(),
                notion_record_id=vendor.name,  # Using name as ID
                actual_data=actual_data
            )
            self.audit_logger.log(audit_entry)

            # Step 5: Return result
            if verification.passed:
                return {
                    "status": "success",
                    "message": f"Vendor '{name}' added successfully and verified.",
                    "vendor": actual_data,
                    "verification": verification.to_dict()
                }
            else:
                return {
                    "status": "verification_failed",
                    "message": f"Vendor '{name}' was added but verification failed!",
                    "vendor": actual_data,
                    "verification": verification.to_dict(),
                    "error": f"Mismatches: {verification.mismatches}"
                }

        except Exception as e:
            # Log failure
            audit_entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                operation="add_vendor",
                entity_type="vendor",
                user="jeff",
                intended_data=intended_data,
                duplicates_found=len(duplicates),
                duplicate_details=[],
                user_confirmed=True if skip_duplicate_check else None,
                confirmation_choice="create_new" if skip_duplicate_check else None,
                result="failed",
                verification=None,
                notion_record_id=None,
                actual_data=None,
                error=str(e)
            )
            self.audit_logger.log(audit_entry)

            return {
                "status": "failed",
                "message": f"Failed to add vendor: {str(e)}",
                "error": str(e)
            }

    def update_vendor_safe(
        self,
        name: str,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        products: Optional[List[str]] = None,
        lead_time_days: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Safely update a vendor with verification.

        Shows before/after and asks for confirmation.
        """
        # Get current vendor data
        current_vendor = self.vendor_helper.get_vendor(name)
        if not current_vendor:
            return {
                "status": "failed",
                "message": f"Vendor '{name}' not found.",
                "error": "Vendor not found"
            }

        # Build update data (only fields that were provided)
        update_data = {}
        if contact_name is not None:
            update_data["contact_name"] = contact_name
        if email is not None:
            update_data["email"] = email
        if phone is not None:
            update_data["phone"] = phone
        if products is not None:
            update_data["products"] = products
        if lead_time_days is not None:
            update_data["lead_time_days"] = lead_time_days
        if notes is not None:
            update_data["notes"] = notes

        operation_id = str(uuid.uuid4())[:8]

        # Show before/after comparison - store as pending
        current_data = {
            "contact_name": current_vendor.contact_name,
            "email": current_vendor.email,
            "phone": current_vendor.phone,
            "products": current_vendor.products,
            "lead_time_days": current_vendor.lead_time_days,
            "notes": current_vendor.notes
        }

        PendingConfirmation.add(
            operation_id=operation_id,
            operation="update_vendor",
            entity_type="vendor",
            intended_data={"name": name, **update_data},
            duplicates=[]  # No duplicate check for updates
        )

        return {
            "status": "confirmation_required",
            "operation_id": operation_id,
            "message": f"Please confirm update to vendor '{name}'",
            "current_data": current_data,
            "proposed_changes": update_data
        }

    def confirm_operation(
        self,
        operation_id: str,
        choice: str,  # "create_new", "update_existing", "cancel"
        update_record_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Confirm a pending operation.

        Args:
            operation_id: ID of pending operation
            choice: What to do ("create_new", "update_existing", "cancel")
            update_record_id: If choice is "update_existing", which record to update

        Returns:
            Result of executing the confirmed operation
        """
        pending = PendingConfirmation.get(operation_id)
        if not pending:
            return {
                "status": "failed",
                "message": f"No pending operation found with ID {operation_id}",
                "error": "Operation not found or already processed"
            }

        operation = pending["operation"]
        intended_data = pending["intended_data"]

        # Remove from pending
        PendingConfirmation.remove(operation_id)

        # Handle based on choice
        if choice == "cancel":
            # Log cancellation
            audit_entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                operation=operation,
                entity_type=pending["entity_type"],
                user="jeff",
                intended_data=intended_data,
                duplicates_found=len(pending["duplicates"]),
                duplicate_details=[d.to_dict() for d in pending["duplicates"]],
                user_confirmed=False,
                confirmation_choice="cancel",
                result="cancelled",
                verification=None,
                notion_record_id=None,
                actual_data=None
            )
            self.audit_logger.log(audit_entry)

            return {
                "status": "cancelled",
                "message": "Operation cancelled by user"
            }

        elif choice == "create_new":
            # Proceed with add, skip duplicate check
            if operation == "add_vendor":
                return self.add_vendor_safe(
                    **intended_data,
                    skip_duplicate_check=True
                )
            else:
                return {
                    "status": "failed",
                    "message": f"Cannot 'create_new' for operation {operation}",
                    "error": "Invalid choice for this operation"
                }

        elif choice == "update_existing":
            if not update_record_id:
                return {
                    "status": "failed",
                    "message": "update_record_id required for 'update_existing' choice",
                    "error": "Missing update_record_id"
                }

            # Update the existing record instead
            if operation == "add_vendor":
                # Convert to update operation
                return self.update_vendor_safe(
                    name=update_record_id,  # Use the existing vendor's name
                    **{k: v for k, v in intended_data.items() if k != "name"}
                )
            else:
                return {
                    "status": "failed",
                    "message": f"Cannot 'update_existing' for operation {operation}",
                    "error": "Invalid choice for this operation"
                }

        elif choice == "confirm" or choice == "proceed":
            # For update operations - proceed with the update
            if operation == "update_vendor":
                try:
                    # Execute the update
                    vendor = self.vendor_helper.update_vendor(
                        name=intended_data["name"],
                        **{k: v for k, v in intended_data.items() if k != "name"}
                    )

                    # Verify
                    actual_data = {
                        "name": vendor.name,
                        "contact_name": vendor.contact_name,
                        "email": vendor.email,
                        "phone": vendor.phone,
                        "products": vendor.products,
                        "lead_time_days": vendor.lead_time_days,
                        "notes": vendor.notes
                    }

                    verification = ChangeVerifier.verify_record(
                        intended_data=intended_data,
                        actual_data=actual_data
                    )

                    # Log
                    audit_entry = AuditEntry(
                        timestamp=datetime.now().isoformat(),
                        operation="update_vendor",
                        entity_type="vendor",
                        user="jeff",
                        intended_data=intended_data,
                        duplicates_found=0,
                        duplicate_details=[],
                        user_confirmed=True,
                        confirmation_choice="confirm",
                        result="success" if verification.passed else "verification_failed",
                        verification=verification.to_dict(),
                        notion_record_id=vendor.name,
                        actual_data=actual_data
                    )
                    self.audit_logger.log(audit_entry)

                    if verification.passed:
                        return {
                            "status": "success",
                            "message": f"Vendor '{intended_data['name']}' updated successfully and verified.",
                            "vendor": actual_data,
                            "verification": verification.to_dict()
                        }
                    else:
                        return {
                            "status": "verification_failed",
                            "message": f"Vendor updated but verification failed!",
                            "vendor": actual_data,
                            "verification": verification.to_dict()
                        }

                except Exception as e:
                    audit_entry = AuditEntry(
                        timestamp=datetime.now().isoformat(),
                        operation="update_vendor",
                        entity_type="vendor",
                        user="jeff",
                        intended_data=intended_data,
                        duplicates_found=0,
                        duplicate_details=[],
                        user_confirmed=True,
                        confirmation_choice="confirm",
                        result="failed",
                        verification=None,
                        notion_record_id=None,
                        actual_data=None,
                        error=str(e)
                    )
                    self.audit_logger.log(audit_entry)

                    return {
                        "status": "failed",
                        "message": f"Failed to update vendor: {str(e)}",
                        "error": str(e)
                    }

        return {
            "status": "failed",
            "message": f"Unknown choice: {choice}",
            "error": "Invalid choice"
        }

    def check_pending_reminders(self) -> List[str]:
        """Check for operations needing reminders (10+ minutes old)."""
        return PendingConfirmation.get_all_needing_reminders()


# Convenience functions
_safe_vendor_ops = None

def get_safe_vendor_ops() -> SafeVendorOperations:
    """Get singleton instance of SafeVendorOperations."""
    global _safe_vendor_ops
    if _safe_vendor_ops is None:
        _safe_vendor_ops = SafeVendorOperations()
    return _safe_vendor_ops


def add_vendor_safe(**kwargs) -> Dict[str, Any]:
    """Convenience function for safe vendor add."""
    return get_safe_vendor_ops().add_vendor_safe(**kwargs)


def update_vendor_safe(**kwargs) -> Dict[str, Any]:
    """Convenience function for safe vendor update."""
    return get_safe_vendor_ops().update_vendor_safe(**kwargs)


def confirm_vendor_operation(operation_id: str, choice: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for confirming vendor operations."""
    return get_safe_vendor_ops().confirm_operation(operation_id, choice, **kwargs)
