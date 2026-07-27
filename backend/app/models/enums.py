from enum import Enum


class InvoicePaymentStatus(str, Enum):
    UNPAID = "Unpaid"
    PARTIALLY_PAID = "Partially Paid"
    FULLY_PAID = "Fully Paid"
    OVERPAID = "Overpaid"
    CANCELLED = "Cancelled"


class PaymentMethod(str, Enum):
    CASH = "Cash"
    UPI = "UPI"
    CARD = "Card"
    BANK_TRANSFER = "Bank transfer"
    CHEQUE = "Cheque"
    RTGS = "RTGS"
    NEFT = "NEFT"
    CUSTOMER_ADVANCE = "Customer advance"
    ADJUSTMENT = "Adjustment"
    OTHER = "Other"


class PaymentRecordStatus(str, Enum):
    SUCCESSFUL = "Successful"
    PENDING = "Pending"
    REVERSED = "Reversed"
    CANCELLED = "Cancelled"
    BOUNCED = "Bounced"


class ChequeStatus(str, Enum):
    RECEIVED = "Received"
    DEPOSITED = "Deposited"
    CLEARED = "Cleared"
    BOUNCED = "Bounced"
    CANCELLED = "Cancelled"


class LedgerTransactionType(str, Enum):
    INVOICE = "Invoice"
    PAYMENT = "Payment"
    ADVANCE_PAYMENT = "Advance payment"
    ADVANCE_ADJUSTMENT = "Advance adjustment"
    PAYMENT_REVERSAL = "Payment reversal"
    OPENING_BALANCE = "Opening balance"
    DEBIT_NOTE = "Debit note"
    CREDIT_NOTE = "Credit note"
    DISCOUNT_ADJUSTMENT = "Discount adjustment"
    ADDITIONAL_CHARGE = "Additional charge"


class StockMovementType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"
