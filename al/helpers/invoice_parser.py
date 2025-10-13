"""
Invoice Parser - Extract vendor info from invoice images using Claude vision

When jeff sends an invoice screenshot, this uses Claude's vision API to:
- Extract vendor name, contact info, email, phone
- Pull product details and pricing
- Identify lead times if mentioned
- Structure the data for vendor_helper

All the grumpy personality stuff happens in the bot - this is just pure data extraction.
"""

import os
import base64
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from anthropic import Anthropic
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ParsedInvoice:
    """Structured invoice data extracted from image."""
    vendor_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None

    # Line items
    items: List[Dict[str, Any]] = None  # [{"product": str, "quantity": int, "unit_price": float, "total": float}]

    # Order details
    order_number: Optional[str] = None
    order_date: Optional[str] = None
    total_amount: Optional[float] = None

    # Other notes
    notes: Optional[str] = None
    raw_text: Optional[str] = None  # Full extracted text for debugging

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.items is None:
            self.items = []


class InvoiceParser:
    """
    Parse invoice images using Claude vision API.

    Extracts vendor information, line items, and order details.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize invoice parser.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)

    def parse_invoice_from_path(self, image_path: Path) -> ParsedInvoice:
        """
        Parse invoice from local image file.

        Args:
            image_path: Path to invoice image

        Returns:
            ParsedInvoice with extracted data

        Raises:
            FileNotFoundError: If image doesn't exist
            ValueError: If image format not supported
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Read and encode image
        image_data = image_path.read_bytes()
        media_type = self._get_media_type(image_path)

        return self.parse_invoice_from_bytes(image_data, media_type)

    def parse_invoice_from_bytes(
        self,
        image_bytes: bytes,
        media_type: str = "image/jpeg"
    ) -> ParsedInvoice:
        """
        Parse invoice from image or PDF bytes.

        Args:
            image_bytes: Raw image or PDF data
            media_type: MIME type (image/jpeg, image/png, application/pdf, etc.)

        Returns:
            ParsedInvoice with extracted data
        """
        # Encode to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # Prompt for structured extraction
        prompt = """Analyze this invoice document and extract the following information in JSON format:

{
  "vendor_name": "Company name",
  "contact_name": "Contact person (if shown)",
  "email": "Email address",
  "phone": "Phone number",
  "website": "Website URL",
  "order_number": "Order/Invoice number",
  "order_date": "Order date (YYYY-MM-DD if possible)",
  "items": [
    {
      "product": "Product description",
      "quantity": number,
      "unit_price": number,
      "total": number
    }
  ],
  "total_amount": total dollar amount,
  "notes": "Any shipping info, lead times, or special notes"
}

Return ONLY valid JSON. If a field isn't visible or can't be determined, use null.
"""

        try:
            # Build content based on media type
            if media_type == "application/pdf":
                # For PDFs, use document source type
                content = [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            else:
                # For images, use image source type
                content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]

            # Call Claude with vision/document parsing
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Vision and document-capable model
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()

            # Sometimes Claude wraps JSON in markdown code blocks
            if response_text.startswith("```"):
                # Extract JSON from code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])  # Remove first and last line
                response_text = response_text.strip()

            # Parse JSON
            data = json.loads(response_text)

            # Convert to ParsedInvoice
            return ParsedInvoice(
                vendor_name=data.get("vendor_name"),
                contact_name=data.get("contact_name"),
                email=data.get("email"),
                phone=data.get("phone"),
                website=data.get("website"),
                items=data.get("items", []),
                order_number=data.get("order_number"),
                order_date=data.get("order_date"),
                total_amount=data.get("total_amount"),
                notes=data.get("notes"),
                raw_text=response_text
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Claude response: {e}")
            logger.error(f"Response was: {response_text}")
            # Return partial data
            return ParsedInvoice(notes=f"Failed to parse: {str(e)}", raw_text=response_text)

        except Exception as e:
            logger.error(f"Invoice parsing failed: {e}")
            return ParsedInvoice(notes=f"Error: {str(e)}")

    def _get_media_type(self, file_path: Path) -> str:
        """
        Determine media type from file extension.

        Args:
            file_path: Path to file

        Returns:
            MIME type string
        """
        ext = file_path.suffix.lower()

        media_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
        }

        return media_types.get(ext, 'image/jpeg')

    def format_parsed_invoice(self, invoice: ParsedInvoice) -> str:
        """
        Format parsed invoice as readable text.

        Args:
            invoice: ParsedInvoice object

        Returns:
            Human-readable summary
        """
        lines = ["**Invoice Parsed:**\n"]

        if invoice.vendor_name:
            lines.append(f"**Vendor:** {invoice.vendor_name}")

        if invoice.contact_name:
            lines.append(f"Contact: {invoice.contact_name}")

        if invoice.email:
            lines.append(f"Email: {invoice.email}")

        if invoice.phone:
            lines.append(f"Phone: {invoice.phone}")

        if invoice.website:
            lines.append(f"Website: {invoice.website}")

        if invoice.order_number:
            lines.append(f"\nOrder #: {invoice.order_number}")

        if invoice.order_date:
            lines.append(f"Date: {invoice.order_date}")

        if invoice.items:
            lines.append("\n**Items:**")
            for item in invoice.items:
                product = item.get("product", "Unknown")
                qty = item.get("quantity", "?")
                price = item.get("unit_price")
                total = item.get("total")

                item_line = f"- {product}: {qty}"
                if price:
                    item_line += f" @ ${price:.2f}"
                if total:
                    item_line += f" = ${total:.2f}"

                lines.append(item_line)

        if invoice.total_amount:
            lines.append(f"\n**Total:** ${invoice.total_amount:.2f}")

        if invoice.notes:
            lines.append(f"\n**Notes:** {invoice.notes}")

        return "\n".join(lines)


def parse_invoice(image_path: Path) -> ParsedInvoice:
    """
    Convenience function to parse invoice from path.

    Args:
        image_path: Path to invoice image

    Returns:
        ParsedInvoice object
    """
    parser = InvoiceParser()
    return parser.parse_invoice_from_path(image_path)
