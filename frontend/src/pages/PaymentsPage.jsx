import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  InputAdornment,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import {
  Download,
  IndianRupee,
  Landmark,
  ReceiptIndianRupee,
  RefreshCw,
  WalletCards,
} from "lucide-react";

import api, { downloadBlob } from "../api/client.js";
import Currency, { formatCurrency } from "../components/Currency.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import TodayDateField from "../components/TodayDateField.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { localDateText } from "../utils/date.js";

const methods = ["Cash", "UPI", "Card", "Bank transfer", "Cheque", "RTGS", "NEFT", "Other"];

function newPaymentForm(customerId = "") {
  return {
    customer_id: customerId,
    payment_date: localDateText(),
    total_amount: "",
    payment_method: "Cash",
    transaction_reference: "",
    bank_name: "",
    cheque_number: "",
    cheque_date: "",
    notes: "",
  };
}

function requestErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
}

function customerOptionLabel(customer) {
  if (!customer) return "";
  return [customer.name, customer.mobile_number].filter(Boolean).join(" · ");
}

function invoiceMaterials(invoice) {
  return [...new Set((invoice?.items || []).map((item) => item.material_name).filter(Boolean))].join(
    ", "
  );
}

export default function PaymentsPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const requestedCustomerId = searchParams.get("customer_id") || "";
  const requestedInvoiceId = searchParams.get("invoice_id") || "";
  const queryApplied = useRef(false);

  const [customers, setCustomers] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [payments, setPayments] = useState([]);
  const [allocationTarget, setAllocationTarget] = useState(null);
  const [form, setForm] = useState(() => newPaymentForm(requestedCustomerId));
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chequeTarget, setChequeTarget] = useState(null);
  const [chequeForm, setChequeForm] = useState({
    cheque_status: "Cleared",
    bounce_charges: 0,
    notes: "",
  });
  const [chequeSaving, setChequeSaving] = useState(false);
  const roleNames = new Set((user?.roles || []).map((role) => role.name));
  const canManageCheques = roleNames.has("Admin") || roleNames.has("Accountant");

  const loadBase = useCallback(async () => {
    try {
      setError("");
      const [customersResponse, paymentsResponse] = await Promise.all([
        api.get("/customers"),
        api.get("/payments"),
      ]);
      setCustomers(customersResponse.data);
      setPayments(paymentsResponse.data);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to load payment data"));
    }
  }, []);

  const fetchOpenInvoices = useCallback(async (customerId) => {
    if (!customerId) {
      return [];
    }
    try {
      const { data } = await api.get(`/invoices?customer_id=${customerId}`);
      const openInvoices = data.filter(
        (invoice) =>
          Number(invoice.available_payment_amount ?? invoice.remaining_amount ?? 0) > 0 &&
          !["Fully Paid", "Cancelled"].includes(invoice.payment_status)
      );
      return openInvoices;
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to load open invoices"));
      return [];
    }
  }, []);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    let ignore = false;
    async function refreshInvoices() {
      if (!form.customer_id) {
        setInvoices([]);
        return;
      }
      const openInvoices = await fetchOpenInvoices(form.customer_id);
      if (ignore) return;
      setInvoices(openInvoices);
      if (!queryApplied.current && requestedInvoiceId) {
        const requestedInvoice = openInvoices.find(
          (invoice) => String(invoice.id) === String(requestedInvoiceId)
        );
        if (requestedInvoice) {
          setAllocationTarget(String(requestedInvoice.id));
          setForm((current) => ({
            ...current,
            total_amount: Number(
              requestedInvoice.available_payment_amount ??
                requestedInvoice.remaining_amount ??
                0
            ),
          }));
        }
        queryApplied.current = true;
      }
    }
    refreshInvoices();
    return () => {
      ignore = true;
    };
  }, [form.customer_id, fetchOpenInvoices, requestedInvoiceId]);

  const customerById = useMemo(
    () => new Map(customers.map((customer) => [String(customer.id), customer])),
    [customers]
  );
  const selectedCustomer = customerById.get(String(form.customer_id));
  const selectedInvoice = invoices.find(
    (invoice) => String(invoice.id) === String(allocationTarget)
  );
  const allocationOptions = useMemo(
    () =>
      form.customer_id
        ? [
            ...invoices.map((invoice) => ({
              id: String(invoice.id),
              kind: "invoice",
              invoice,
            })),
            {
              id: "advance",
              kind: "advance",
            },
          ]
        : [],
    [form.customer_id, invoices]
  );
  const selectedAllocation =
    allocationOptions.find((option) => option.id === allocationTarget) || null;
  const paymentAmount = Number(form.total_amount || 0);
  const invoiceBalance = Number(
    selectedInvoice?.available_payment_amount ?? selectedInvoice?.remaining_amount ?? 0
  );
  const pendingChequeAmount = Number(selectedInvoice?.pending_payment_amount || 0);
  const remainingAfterPayment = selectedInvoice
    ? Math.max(invoiceBalance - paymentAmount, 0)
    : 0;
  const paymentInvalid =
    !Number.isFinite(paymentAmount) ||
    paymentAmount <= 0 ||
    (selectedInvoice && paymentAmount > invoiceBalance + 0.005);
  const isPartial =
    Boolean(selectedInvoice) && paymentAmount > 0 && paymentAmount < invoiceBalance - 0.005;

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function changeCustomer(customerId) {
    setAllocationTarget(null);
    setInvoices([]);
    setForm(newPaymentForm(customerId));
    queryApplied.current = true;
  }

  function changeAllocation(targetId) {
    setAllocationTarget(targetId);
    const invoice = invoices.find((entry) => String(entry.id) === String(targetId));
    setField(
      "total_amount",
      invoice
        ? Number(invoice.available_payment_amount ?? invoice.remaining_amount ?? 0)
        : ""
    );
  }

  async function submitPayment(event) {
    event.preventDefault();
    if (paymentInvalid || !form.customer_id || !allocationTarget) return;
    setIsSubmitting(true);
    setError("");
    const payload = {
      customer_id: Number(form.customer_id),
      payment_date: form.payment_date,
      total_amount: paymentAmount,
      payment_method: form.payment_method,
      transaction_reference: form.transaction_reference.trim() || null,
      bank_name: form.bank_name.trim() || null,
      cheque_number: form.cheque_number.trim() || null,
      cheque_date: form.cheque_date || null,
      notes: form.notes.trim() || null,
      allocation_method: "manual",
      allocations: selectedInvoice
        ? [
            {
              invoice_id: selectedInvoice.id,
              allocated_amount: paymentAmount,
            },
          ]
        : [],
    };

    try {
      const { data } = await api.post("/payments", payload);
      setMessage(
        selectedInvoice
          ? `${formatCurrency(paymentAmount)} recorded for ${selectedInvoice.invoice_number}`
          : `${formatCurrency(paymentAmount)} saved as customer advance`
      );
      const customerId = form.customer_id;
      setForm(newPaymentForm(customerId));
      setAllocationTarget(null);
      const [, openInvoices] = await Promise.all([
        loadBase(),
        fetchOpenInvoices(customerId),
      ]);
      setInvoices(openInvoices);
      if (data.unallocated_amount > 0 && selectedInvoice) {
        setMessage("Payment saved; the unused amount is available as customer advance");
      }
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to save payment"));
    } finally {
      setIsSubmitting(false);
    }
  }

  function openCheque(payment) {
    setChequeTarget(payment);
    setChequeForm({
      cheque_status: payment.cheque_status === "Cleared" ? "Bounced" : "Cleared",
      bounce_charges: 0,
      notes: "",
    });
  }

  async function updateChequeStatus(event) {
    event.preventDefault();
    if (!chequeTarget) return;
    setChequeSaving(true);
    setError("");
    try {
      await api.post(`/payments/${chequeTarget.id}/cheque-status`, {
        cheque_status: chequeForm.cheque_status,
        bounce_charges:
          chequeForm.cheque_status === "Bounced"
            ? Number(chequeForm.bounce_charges || 0)
            : 0,
        notes: chequeForm.notes.trim() || null,
      });
      setMessage(
        `${chequeTarget.cheque_number || "Cheque"} marked ${chequeForm.cheque_status.toLowerCase()}`
      );
      setChequeTarget(null);
      const [, openInvoices] = await Promise.all([
        loadBase(),
        fetchOpenInvoices(form.customer_id),
      ]);
      setInvoices(openInvoices);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to update cheque status"));
    } finally {
      setChequeSaving(false);
    }
  }

  const chequeStatusOptions =
    chequeTarget?.cheque_status === "Cleared"
      ? ["Bounced", "Cancelled"]
      : ["Deposited", "Cleared", "Bounced", "Cancelled"].filter(
          (status) => status !== chequeTarget?.cheque_status
        );

  return (
    <Stack spacing={3}>
      <Box className="page-header">
        <Box>
          <Typography variant="h4">Payments</Typography>
          <Typography variant="body2" color="text.secondary">
            Record full or partial payments and download a receipt
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshCw size={18} />} onClick={loadBase}>
          Refresh
        </Button>
      </Box>

      {message ? <Alert onClose={() => setMessage("")}>{message}</Alert> : null}
      {error ? (
        <Alert severity="error" onClose={() => setError("")}>
          {error}
        </Alert>
      ) : null}

      <Grid container spacing={2.5}>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Box className="card-title-row">
                <Box>
                  <Typography variant="h6">Record payment</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Choose an invoice, then enter the amount actually received.
                  </Typography>
                </Box>
                <ReceiptIndianRupee size={26} color="#176b5b" />
              </Box>

              <Box component="form" onSubmit={submitPayment}>
                <Box className="form-grid">
                  <Autocomplete
                    className="span-6"
                    options={customers}
                    value={selectedCustomer || null}
                    onChange={(_, customer) => changeCustomer(customer?.id || "")}
                    isOptionEqualToValue={(option, value) => option.id === value.id}
                    getOptionLabel={customerOptionLabel}
                    renderOption={(props, customer) => (
                      <Box component="li" {...props} key={customer.id}>
                        <Box>
                          <Typography fontWeight={750}>{customer.name}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            {customer.mobile_number || "No mobile number"}
                            {customer.city ? ` · ${customer.city}` : ""}
                          </Typography>
                        </Box>
                      </Box>
                    )}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Customer"
                        placeholder="Search name or mobile"
                        required
                      />
                    )}
                  />
                  <TodayDateField
                    className="span-3"
                    label="Payment date"
                    value={form.payment_date}
                    onChange={(event) => setField("payment_date", event.target.value)}
                    onToday={(value) => setField("payment_date", value)}
                    required
                  />
                  <TextField
                    className="span-3"
                    select
                    label="Payment method"
                    value={form.payment_method}
                    onChange={(event) => setField("payment_method", event.target.value)}
                  >
                    {methods.map((method) => (
                      <MenuItem key={method} value={method}>
                        {method}
                      </MenuItem>
                    ))}
                  </TextField>
                  <Box className="span-12" sx={{ mt: 0.5 }}>
                    <Typography className="section-heading" sx={{ mb: 0 }}>
                      Apply this payment to
                    </Typography>
                  </Box>
                  <Autocomplete
                    className="span-8"
                    options={allocationOptions}
                    value={selectedAllocation}
                    onChange={(_, option) => changeAllocation(option?.id || null)}
                    disabled={!form.customer_id}
                    isOptionEqualToValue={(option, value) => option.id === value.id}
                    getOptionLabel={(option) =>
                      option.kind === "advance"
                        ? "Customer advance · not linked to an invoice"
                        : `${option.invoice.invoice_number} · ${formatCurrency(
                            option.invoice.available_payment_amount ??
                              option.invoice.remaining_amount
                          )} outstanding`
                    }
                    renderOption={(props, option) => (
                      <Box component="li" {...props} key={option.id}>
                        {option.kind === "advance" ? (
                          <Box>
                            <Typography fontWeight={750}>Customer advance</Typography>
                            <Typography variant="body2" color="text.secondary">
                              Use only when this payment is not for a specific invoice
                            </Typography>
                          </Box>
                        ) : (
                          <Box sx={{ width: "100%" }}>
                            <Box className="invoice-option-title">
                              <Typography fontWeight={800}>
                                {option.invoice.invoice_number}
                              </Typography>
                              <Typography fontWeight={800} color="primary.main">
                                {formatCurrency(
                                  option.invoice.available_payment_amount ??
                                    option.invoice.remaining_amount
                                )}{" "}
                                due
                              </Typography>
                            </Box>
                            <Typography variant="body2" color="text.secondary">
                              {option.invoice.invoice_date}
                              {invoiceMaterials(option.invoice)
                                ? ` · ${invoiceMaterials(option.invoice)}`
                                : ""}
                              {" · "}Invoice total {formatCurrency(option.invoice.grand_total)}
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    )}
                    noOptionsText="No unpaid invoices found"
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Invoice or customer advance"
                        placeholder={
                          form.customer_id ? "Search and choose an invoice" : "Select a customer first"
                        }
                        helperText={
                          form.customer_id
                            ? "Invoice choices show the material, total and amount still due."
                            : "Select a customer first."
                        }
                        required
                      />
                    )}
                  />
                  <TextField
                    className="span-4"
                    label="Amount received"
                    type="number"
                    value={form.total_amount}
                    onChange={(event) => setField("total_amount", event.target.value)}
                    InputProps={{
                      startAdornment: <InputAdornment position="start">₹</InputAdornment>,
                    }}
                    inputProps={{
                      min: 0.01,
                      max: selectedInvoice ? invoiceBalance : undefined,
                      step: "0.01",
                    }}
                    required
                  />
                  <TextField
                    className="span-6"
                    label="Transaction reference (optional)"
                    value={form.transaction_reference}
                    onChange={(event) => setField("transaction_reference", event.target.value)}
                  />
                  {form.payment_method === "Cheque" ? (
                    <>
                      <TextField
                        className="span-6"
                        label="Bank name"
                        value={form.bank_name}
                        onChange={(event) => setField("bank_name", event.target.value)}
                      />
                      <TextField
                        className="span-6"
                        label="Cheque number"
                        value={form.cheque_number}
                        onChange={(event) => setField("cheque_number", event.target.value)}
                        required
                      />
                      <TodayDateField
                        className="span-6"
                        label="Cheque date"
                        value={form.cheque_date}
                        onChange={(event) => setField("cheque_date", event.target.value)}
                        onToday={(value) => setField("cheque_date", value)}
                      />
                    </>
                  ) : null}
                  <TextField
                    className="span-12"
                    label="Notes (optional)"
                    value={form.notes}
                    onChange={(event) => setField("notes", event.target.value)}
                    multiline
                    minRows={2}
                  />
                </Box>

                {selectedInvoice ? (
                  <Box className="summary-panel payment-balance" sx={{ mt: 2.5 }}>
                    <Box className="card-title-row" sx={{ mb: 0.5 }}>
                      <Box>
                        <Typography fontWeight={800}>{selectedInvoice.invoice_number}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {selectedInvoice.invoice_date}
                          {invoiceMaterials(selectedInvoice)
                            ? ` · ${invoiceMaterials(selectedInvoice)}`
                            : ""}
                        </Typography>
                      </Box>
                      {paymentAmount > 0 ? (
                        <Chip
                          color={isPartial ? "warning" : "success"}
                          label={isPartial ? "Partial payment" : "Pays in full"}
                        />
                      ) : null}
                    </Box>
                    <Box className="summary-strip" sx={{ mt: 2 }}>
                      <span>
                        <small>Invoice total</small>
                        <strong>{formatCurrency(selectedInvoice.grand_total)}</strong>
                      </span>
                      <span>
                        <small>Previously paid</small>
                        <strong>
                          {formatCurrency(
                            Number(selectedInvoice.total_paid || 0) +
                              Number(selectedInvoice.advance_adjusted || 0)
                          )}
                        </strong>
                      </span>
                      <span>
                        <small>Receiving now</small>
                        <strong>{formatCurrency(paymentAmount)}</strong>
                      </span>
                      <span>
                        <small>Remaining after payment</small>
                        <strong>{formatCurrency(remainingAfterPayment)}</strong>
                      </span>
                    </Box>
                    {pendingChequeAmount > 0 ? (
                      <Alert severity="info" sx={{ mt: 1.5 }}>
                        {formatCurrency(pendingChequeAmount)} is reserved against a pending cheque.
                      </Alert>
                    ) : null}
                    <Button
                      size="small"
                      sx={{ mt: 1.5 }}
                      onClick={() => setField("total_amount", invoiceBalance)}
                    >
                      Use full outstanding amount
                    </Button>
                  </Box>
                ) : allocationTarget === "advance" ? (
                  <Alert severity="info" sx={{ mt: 2.5 }}>
                    This will be saved as an advance for {selectedCustomer?.name}. It can be used
                    on a future invoice.
                  </Alert>
                ) : null}

                {selectedInvoice && paymentAmount > invoiceBalance ? (
                  <Alert severity="error" sx={{ mt: 2 }}>
                    Amount cannot be more than the invoice balance of{" "}
                    {formatCurrency(invoiceBalance)}.
                  </Alert>
                ) : null}

                <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 2.5 }}>
                  <Button
                    type="submit"
                    size="large"
                    variant="contained"
                    startIcon={<IndianRupee size={18} />}
                    disabled={
                      !form.customer_id || !allocationTarget || paymentInvalid || isSubmitting
                    }
                  >
                    {isSubmitting
                      ? "Saving..."
                      : selectedInvoice && isPartial
                        ? "Record partial payment"
                        : "Save payment"}
                  </Button>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Typography variant="h6">Customer balance</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Select a customer to see their current position.
              </Typography>
              <Stack spacing={0}>
                <Box className="inline-row">
                  <span>Outstanding</span>
                  <Typography variant="h6">
                    {formatCurrency(selectedCustomer?.current_outstanding_balance || 0)}
                  </Typography>
                </Box>
                <Box className="inline-row" sx={{ borderBottom: 0 }}>
                  <span>Available advance</span>
                  <Typography variant="h6" color="primary.main">
                    {formatCurrency(selectedCustomer?.advance_balance || 0)}
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <Box sx={{ px: 2.75, py: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="h6">Recent payments</Typography>
          <Typography variant="body2" color="text.secondary">
            Download a receipt for any recorded payment.
          </Typography>
        </Box>
        {payments.length ? (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Receipt</TableCell>
                  <TableCell>Customer</TableCell>
                  <TableCell>Date & method</TableCell>
                  <TableCell align="right">Amount</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Receipt</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {payments.map((payment) => (
                  <TableRow key={payment.id} hover>
                    <TableCell>
                      <Typography fontWeight={750}>{payment.receipt_number}</Typography>
                    </TableCell>
                    <TableCell>
                      {customerById.get(String(payment.customer_id))?.name || "—"}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{payment.payment_date}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {payment.payment_method}
                        {payment.payment_method === "Cheque" && payment.cheque_status
                          ? ` · ${payment.cheque_status}`
                          : ""}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Currency value={payment.total_amount} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge value={payment.payment_status} />
                    </TableCell>
                    <TableCell align="right">
                      <Box className="table-row-actions">
                        {canManageCheques &&
                        payment.payment_method === "Cheque" &&
                        !["Bounced", "Cancelled"].includes(payment.cheque_status) ? (
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<Landmark size={16} />}
                            onClick={() => openCheque(payment)}
                          >
                            Manage cheque
                          </Button>
                        ) : null}
                        <Button
                          size="small"
                          variant="text"
                          startIcon={<Download size={16} />}
                          onClick={() => downloadBlob(`/payments/${payment.id}/receipt`)}
                        >
                          Download
                        </Button>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Box className="empty-state">
            <Box>
              <WalletCards size={34} />
              <Typography variant="h6">No payments yet</Typography>
              <Typography variant="body2">
                Payments and downloadable receipts will appear here.
              </Typography>
            </Box>
          </Box>
        )}
      </Card>

      <Dialog
        open={Boolean(chequeTarget)}
        onClose={() => setChequeTarget(null)}
        fullWidth
        maxWidth="xs"
      >
        <Box component="form" onSubmit={updateChequeStatus}>
          <DialogTitle>Update cheque</DialogTitle>
          <DialogContent dividers>
            <Typography fontWeight={750}>
              Cheque {chequeTarget?.cheque_number || "payment"}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Current status: {chequeTarget?.cheque_status || "Received"}
            </Typography>
            <Stack spacing={2}>
              <TextField
                select
                label="New status"
                value={chequeForm.cheque_status}
                onChange={(event) =>
                  setChequeForm((current) => ({
                    ...current,
                    cheque_status: event.target.value,
                  }))
                }
              >
                {chequeStatusOptions.map((status) => (
                  <MenuItem key={status} value={status}>
                    {status}
                  </MenuItem>
                ))}
              </TextField>
              {chequeForm.cheque_status === "Bounced" ? (
                <TextField
                  label="Bounce charges"
                  type="number"
                  value={chequeForm.bounce_charges}
                  onChange={(event) =>
                    setChequeForm((current) => ({
                      ...current,
                      bounce_charges: event.target.value,
                    }))
                  }
                  inputProps={{ min: 0, step: "0.01" }}
                />
              ) : null}
              <TextField
                label="Note (optional)"
                value={chequeForm.notes}
                onChange={(event) =>
                  setChequeForm((current) => ({ ...current, notes: event.target.value }))
                }
                multiline
                minRows={2}
              />
              {["Bounced", "Cancelled"].includes(chequeForm.cheque_status) ? (
                <Alert severity="warning">
                  This releases the amount reserved against the invoice.
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setChequeTarget(null)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={chequeSaving}>
              {chequeSaving ? "Updating..." : "Update cheque"}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Stack>
  );
}
