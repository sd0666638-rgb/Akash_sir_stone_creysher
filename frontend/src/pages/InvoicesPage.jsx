import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  IconButton,
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
  Tooltip,
  Typography,
} from "@mui/material";
import {
  ChevronDown,
  Download,
  FilePlus2,
  PackageOpen,
  Plus,
  Printer,
  ReceiptIndianRupee,
  RefreshCw,
  Trash2,
  UserPlus,
} from "lucide-react";

import api, { downloadBlob, printPdf } from "../api/client.js";
import Currency, { formatCurrency } from "../components/Currency.jsx";
import CustomerDialog from "../components/CustomerDialog.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import TodayDateField from "../components/TodayDateField.jsx";
import { localDateText } from "../utils/date.js";

const paymentMethods = ["Cash", "UPI", "Card", "Bank transfer", "RTGS", "NEFT", "Other"];

function blankInvoiceItem() {
  return {
    material_id: "",
    material_name: "",
    dispatch_date: "",
    receipt_number: "",
    hsn_code: "",
    vehicle_number: "",
    quantity: 1,
    unit: "TON",
    rate: 0,
    gst_percentage: 5,
    discount_percentage: 0,
  };
}

function createBlankForm() {
  return {
    invoice_date: localDateText(),
    customer_id: "",
    delivery_note: "",
    other_reference: "",
    buyer_order_number: "",
    vehicle_number: "",
    driver_name: "",
    transporter: "",
    delivery_location: "",
    transport_charges: 0,
    loading_charges: 0,
    other_charges: 0,
    round_off: 0,
    amount_paid_now: 0,
    payment_method: "Cash",
    advance_to_adjust: 0,
    notes: "",
  };
}

function lineTotals(item) {
  const subtotal = Number(item.quantity || 0) * Number(item.rate || 0);
  const discount = subtotal * (Number(item.discount_percentage || 0) / 100);
  const taxable = subtotal - discount;
  const gst = taxable * (Number(item.gst_percentage || 0) / 100);
  return {
    subtotal,
    discount,
    taxable,
    gst,
    total: taxable + gst,
  };
}

function requestErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
}

function mergeCustomers(current, incoming) {
  const merged = new Map(current.map((customer) => [String(customer.id), customer]));
  incoming.forEach((customer) => merged.set(String(customer.id), customer));
  return Array.from(merged.values());
}

function customerOptionLabel(customer) {
  return customer.mobile_number
    ? `${customer.mobile_number} — ${customer.name}`
    : customer.name;
}

export default function InvoicesPage() {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState(createBlankForm);
  const [items, setItems] = useState([blankInvoiceItem()]);
  const [customerDialogOpen, setCustomerDialogOpen] = useState(false);
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerSearchLoading, setCustomerSearchLoading] = useState(false);
  const [buyerOrderPreview, setBuyerOrderPreview] = useState("");

  async function loadAll() {
    try {
      setError("");
      const [customersResponse, materialsResponse, invoicesResponse] = await Promise.all([
        api.get("/customers?limit=50"),
        api.get("/materials"),
        api.get("/invoices"),
      ]);
      setCustomers(customersResponse.data);
      setMaterials(materialsResponse.data);
      setInvoices(invoicesResponse.data);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to load invoice data"));
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    const query = customerSearch.trim();
    if (!query) return undefined;
    let ignore = false;
    const timer = window.setTimeout(async () => {
      setCustomerSearchLoading(true);
      try {
        const { data } = await api.get("/customers", {
          params: { q: query, limit: 50 },
        });
        if (!ignore) {
          setCustomers((current) => mergeCustomers(current, data));
        }
      } catch {
        // Keep the already-loaded top 50 available if a search request fails.
      } finally {
        if (!ignore) setCustomerSearchLoading(false);
      }
    }, 300);
    return () => {
      ignore = true;
      window.clearTimeout(timer);
    };
  }, [customerSearch]);

  useEffect(() => {
    let ignore = false;
    async function loadBuyerOrderPreview() {
      if (!form.invoice_date) {
        setBuyerOrderPreview("");
        return;
      }
      try {
        const { data } = await api.get("/invoices/next-buyer-order-number", {
          params: { invoice_date: form.invoice_date },
        });
        if (!ignore) setBuyerOrderPreview(data.buyer_order_number || "");
      } catch {
        if (!ignore) setBuyerOrderPreview("");
      }
    }
    loadBuyerOrderPreview();
    return () => {
      ignore = true;
    };
  }, [form.invoice_date]);

  const customerById = useMemo(
    () => new Map(customers.map((customer) => [String(customer.id), customer])),
    [customers]
  );
  const selectedCustomer = customerById.get(String(form.customer_id));

  const totals = useMemo(() => {
    const rows = items.map(lineTotals);
    const subtotal = rows.reduce((sum, row) => sum + row.subtotal, 0);
    const discount = rows.reduce((sum, row) => sum + row.discount, 0);
    const taxable = rows.reduce((sum, row) => sum + row.taxable, 0);
    const gst = rows.reduce((sum, row) => sum + row.gst, 0);
    const grand =
      taxable +
      gst +
      Number(form.transport_charges || 0) +
      Number(form.loading_charges || 0) +
      Number(form.other_charges || 0) +
      Number(form.round_off || 0);
    return { subtotal, discount, taxable, gst, grand };
  }, [items, form]);

  const paidNow = Number(form.amount_paid_now || 0);
  const advanceNow = Number(form.advance_to_adjust || 0);
  const availableAdvance = Number(selectedCustomer?.advance_balance || 0);
  const remainingAfterPayment = Math.max(totals.grand - paidNow - advanceNow, 0);
  const paymentInvalid =
    paidNow < 0 ||
    advanceNow < 0 ||
    advanceNow > availableAdvance ||
    paidNow + advanceNow > totals.grand + 0.005;

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateItem(index, field, value) {
    setItems((current) =>
      current.map((item, itemIndex) => {
        if (itemIndex !== index) return item;
        const next = { ...item, [field]: value };
        if (field === "material_id") {
          const material = materials.find((entry) => String(entry.id) === String(value));
          if (material) {
            next.material_name = material.name;
            next.unit = material.unit;
            next.rate = Number(material.selling_rate);
            next.gst_percentage = Number(material.gst_percentage);
            next.dispatch_date = next.dispatch_date || form.invoice_date;
            next.receipt_number = next.receipt_number || form.delivery_note;
            next.hsn_code = material.hsn_code || "";
            next.vehicle_number = next.vehicle_number || form.vehicle_number;
          }
        }
        return next;
      })
    );
  }

  function removeItem(index) {
    setItems((current) =>
      current.length === 1 ? current : current.filter((_, itemIndex) => itemIndex !== index)
    );
  }

  async function submitInvoice(event) {
    event.preventDefault();
    if (paymentInvalid) return;
    if (!form.customer_id) {
      setError("Select an existing customer or add a new customer first");
      return;
    }
    setError("");
    setIsSubmitting(true);
    const payload = {
      invoice_date: form.invoice_date,
      customer_id: Number(form.customer_id),
      delivery_note: form.delivery_note.trim() || null,
      other_reference: form.other_reference.trim() || null,
      buyer_order_number: form.buyer_order_number.trim() || null,
      vehicle_number: form.vehicle_number.trim() || null,
      driver_name: form.driver_name.trim() || null,
      transporter: form.transporter.trim() || null,
      delivery_location: form.delivery_location.trim() || null,
      notes: form.notes.trim() || null,
      transport_charges: Number(form.transport_charges || 0),
      loading_charges: Number(form.loading_charges || 0),
      other_charges: Number(form.other_charges || 0),
      round_off: Number(form.round_off || 0),
      amount_paid_now: paidNow,
      payment_method: paidNow > 0 ? form.payment_method : "Cash",
      advance_to_adjust: advanceNow,
      items: items.map((item) => ({
        material_id: item.material_id ? Number(item.material_id) : null,
        material_name: item.material_name,
        dispatch_date: item.dispatch_date || form.invoice_date,
        receipt_number: item.receipt_number.trim() || null,
        hsn_code: item.hsn_code.trim() || null,
        vehicle_number: item.vehicle_number.trim() || null,
        quantity: Number(item.quantity || 0),
        unit: item.unit,
        rate: Number(item.rate || 0),
        gst_percentage: Number(item.gst_percentage || 0),
        discount_percentage: Number(item.discount_percentage || 0),
      })),
    };

    try {
      const { data } = await api.post("/invoices", payload);
      setMessage(
        `${data.invoice_number} created${
          data.buyer_order_number ? ` · Order ${data.buyer_order_number}` : ""
        }${
          paidNow > 0 ? ` with ${formatCurrency(paidNow)} received` : ""
        }`
      );
      const nextForm = createBlankForm();
      setItems([blankInvoiceItem()]);
      setForm(nextForm);
      setCustomerSearch("");
      await loadAll();
      try {
        const { data: nextOrder } = await api.get(
          "/invoices/next-buyer-order-number",
          { params: { invoice_date: nextForm.invoice_date } }
        );
        setBuyerOrderPreview(nextOrder.buyer_order_number || "");
      } catch {
        setBuyerOrderPreview("");
      }
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to create invoice"));
    } finally {
      setIsSubmitting(false);
    }
  }

  function recordPayment(invoice) {
    const params = new URLSearchParams({
      customer_id: String(invoice.customer_id),
      invoice_id: String(invoice.id),
    });
    navigate(`/payments?${params.toString()}`);
  }

  return (
    <Stack spacing={3}>
      <Box className="page-header">
        <Box>
          <Typography variant="h4">Invoices</Typography>
          <Typography variant="body2" color="text.secondary">
            Create a dispatch bill and track every payment against it
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshCw size={18} />} onClick={loadAll}>
          Refresh
        </Button>
      </Box>

      {message ? <Alert onClose={() => setMessage("")}>{message}</Alert> : null}
      {error ? (
        <Alert severity="error" onClose={() => setError("")}>
          {error}
        </Alert>
      ) : null}

      <Card>
        <CardContent>
          <Box className="card-title-row">
            <Box>
              <Typography variant="h6">Create invoice</Typography>
              <Typography variant="body2" color="text.secondary">
                Only customer, date and one material are required.
              </Typography>
            </Box>
            <Typography variant="h6" color="primary.main">
              {formatCurrency(totals.grand)}
            </Typography>
          </Box>

          <Box component="form" onSubmit={submitInvoice}>
            <Box className="form-grid">
              <TodayDateField
                className="span-3"
                label="Invoice date"
                value={form.invoice_date}
                onChange={(event) => setField("invoice_date", event.target.value)}
                onToday={(value) => setField("invoice_date", value)}
                required
              />
              <Box className="span-6 customer-picker-row">
                <Autocomplete
                  fullWidth
                  options={customers}
                  value={selectedCustomer || null}
                  inputValue={customerSearch}
                  loading={customerSearchLoading}
                  onInputChange={(_, value, reason) => {
                    setCustomerSearch(value);
                    if (
                      reason === "input" &&
                      selectedCustomer &&
                      value !== customerOptionLabel(selectedCustomer)
                    ) {
                      setField("customer_id", "");
                      setField("advance_to_adjust", 0);
                    }
                  }}
                  onChange={(_, customer) => {
                    setField("customer_id", customer?.id || "");
                    setField("advance_to_adjust", 0);
                  }}
                  isOptionEqualToValue={(option, value) => option.id === value.id}
                  getOptionLabel={customerOptionLabel}
                  filterOptions={(options, state) => {
                    const query = state.inputValue.trim().toLowerCase();
                    if (!query) return options.slice(0, 50);
                    return options
                      .filter((customer) =>
                        [customer.mobile_number, customer.name, customer.city]
                          .filter(Boolean)
                          .some((value) => String(value).toLowerCase().includes(query))
                      )
                      .slice(0, 50);
                  }}
                  renderOption={(props, customer) => (
                    <Box component="li" {...props} key={customer.id}>
                      <Box>
                        <Typography fontWeight={750}>
                          {customer.mobile_number || "No mobile"}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {customer.name}
                          {customer.city ? ` · ${customer.city}` : ""}
                        </Typography>
                      </Box>
                    </Box>
                  )}
                  noOptionsText="No customer found — use the add button"
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Customer mobile or name"
                      placeholder="Search mobile number first"
                      required
                    />
                  )}
                />
                <Tooltip title="Add a new customer">
                  <IconButton
                    className="customer-add-button"
                    color="primary"
                    aria-label="Add customer"
                    onClick={() => setCustomerDialogOpen(true)}
                  >
                    <UserPlus size={20} />
                  </IconButton>
                </Tooltip>
              </Box>
              <TextField
                className="span-3"
                label="Buyer order number"
                value={form.buyer_order_number}
                onChange={(event) => setField("buyer_order_number", event.target.value)}
                placeholder={buyerOrderPreview || "Generated automatically"}
                helperText={
                  buyerOrderPreview
                    ? `Leave blank to use ${buyerOrderPreview}`
                    : "Leave blank to generate automatically"
                }
              />
            </Box>

            <Box sx={{ mt: 3 }}>
              <Box className="card-title-row" sx={{ mb: 1 }}>
                <Box>
                  <Typography className="section-heading" sx={{ mb: 0 }}>
                    Materials
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Add each dispatch or challan as a separate row.
                  </Typography>
                </Box>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<Plus size={17} />}
                  onClick={() => setItems((current) => [...current, blankInvoiceItem()])}
                >
                  Add row
                </Button>
              </Box>

              <TableContainer className="invoice-items-table">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Dispatch date</TableCell>
                      <TableCell>Challan no.</TableCell>
                      <TableCell>Material</TableCell>
                      <TableCell>Vehicle</TableCell>
                      <TableCell align="right">Quantity</TableCell>
                      <TableCell align="right">Rate</TableCell>
                      <TableCell align="right">GST</TableCell>
                      <TableCell align="right">Amount</TableCell>
                      <TableCell align="right" aria-label="Actions" />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell sx={{ minWidth: 145 }}>
                          <TodayDateField
                            fullWidth
                            size="small"
                            value={item.dispatch_date}
                            onChange={(event) =>
                              updateItem(index, "dispatch_date", event.target.value)
                            }
                            onToday={(value) => updateItem(index, "dispatch_date", value)}
                            inputProps={{ "aria-label": "Dispatch date" }}
                          />
                        </TableCell>
                        <TableCell sx={{ minWidth: 120 }}>
                          <TextField
                            fullWidth
                            size="small"
                            placeholder="Optional"
                            value={item.receipt_number}
                            onChange={(event) =>
                              updateItem(index, "receipt_number", event.target.value)
                            }
                            inputProps={{ "aria-label": "Challan number" }}
                          />
                        </TableCell>
                        <TableCell sx={{ minWidth: 190 }}>
                          <TextField
                            select
                            fullWidth
                            size="small"
                            value={item.material_id}
                            onChange={(event) =>
                              updateItem(index, "material_id", event.target.value)
                            }
                            required
                          >
                            {materials.map((material) => (
                              <MenuItem key={material.id} value={material.id}>
                                {material.name}
                              </MenuItem>
                            ))}
                          </TextField>
                        </TableCell>
                        <TableCell sx={{ minWidth: 135 }}>
                          <TextField
                            fullWidth
                            size="small"
                            placeholder={form.vehicle_number || "Optional"}
                            value={item.vehicle_number}
                            onChange={(event) =>
                              updateItem(index, "vehicle_number", event.target.value)
                            }
                            inputProps={{ "aria-label": "Vehicle number" }}
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ minWidth: 125 }}>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            value={item.quantity}
                            onChange={(event) => updateItem(index, "quantity", event.target.value)}
                            InputProps={{
                              endAdornment: (
                                <InputAdornment position="end">{item.unit}</InputAdornment>
                              ),
                            }}
                            inputProps={{ min: 0.001, step: "0.001" }}
                            required
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ minWidth: 115 }}>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            value={item.rate}
                            onChange={(event) => updateItem(index, "rate", event.target.value)}
                            inputProps={{ min: 0, step: "0.01" }}
                            required
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ minWidth: 92 }}>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            value={item.gst_percentage}
                            onChange={(event) =>
                              updateItem(index, "gst_percentage", event.target.value)
                            }
                            InputProps={{
                              endAdornment: <InputAdornment position="end">%</InputAdornment>,
                            }}
                            inputProps={{ min: 0, max: 100, step: "0.01" }}
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                          <Typography fontWeight={750}>
                            {formatCurrency(lineTotals(item).total)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title="Remove row">
                            <span>
                              <IconButton
                                size="small"
                                color="error"
                                aria-label="Remove item"
                                onClick={() => removeItem(index)}
                                disabled={items.length === 1}
                              >
                                <Trash2 size={17} />
                              </IconButton>
                            </span>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>

            <Accordion
              disableGutters
              elevation={0}
              sx={{
                mt: 2,
                border: "1px solid",
                borderColor: "divider",
                borderRadius: "12px !important",
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary expandIcon={<ChevronDown size={18} />}>
                <Box>
                  <Typography fontWeight={750}>Optional details and charges</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Transport, delivery references and notes
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Box className="form-grid">
                  <TextField
                    className="span-3"
                    label="Delivery note"
                    value={form.delivery_note}
                    onChange={(event) => setField("delivery_note", event.target.value)}
                  />
                  <TextField
                    className="span-3"
                    label="Default vehicle number"
                    value={form.vehicle_number}
                    onChange={(event) => setField("vehicle_number", event.target.value)}
                  />
                  <TextField
                    className="span-3"
                    label="Driver name"
                    value={form.driver_name}
                    onChange={(event) => setField("driver_name", event.target.value)}
                  />
                  <TextField
                    className="span-3"
                    label="Transporter"
                    value={form.transporter}
                    onChange={(event) => setField("transporter", event.target.value)}
                  />
                  <TextField
                    className="span-6"
                    label="Delivery location"
                    value={form.delivery_location}
                    onChange={(event) => setField("delivery_location", event.target.value)}
                  />
                  <TextField
                    className="span-6"
                    label="Other reference"
                    value={form.other_reference}
                    onChange={(event) => setField("other_reference", event.target.value)}
                  />
                  <TextField
                    className="span-3"
                    label="Transport charges"
                    type="number"
                    value={form.transport_charges}
                    onChange={(event) => setField("transport_charges", event.target.value)}
                    inputProps={{ min: 0, step: "0.01" }}
                  />
                  <TextField
                    className="span-3"
                    label="Loading charges"
                    type="number"
                    value={form.loading_charges}
                    onChange={(event) => setField("loading_charges", event.target.value)}
                    inputProps={{ min: 0, step: "0.01" }}
                  />
                  <TextField
                    className="span-3"
                    label="Other charges"
                    type="number"
                    value={form.other_charges}
                    onChange={(event) => setField("other_charges", event.target.value)}
                    inputProps={{ min: 0, step: "0.01" }}
                  />
                  <TextField
                    className="span-3"
                    label="Round off"
                    type="number"
                    value={form.round_off}
                    onChange={(event) => setField("round_off", event.target.value)}
                    inputProps={{ min: -1, max: 1, step: "0.01" }}
                  />
                  <TextField
                    className="span-12"
                    label="Notes"
                    multiline
                    minRows={2}
                    value={form.notes}
                    onChange={(event) => setField("notes", event.target.value)}
                  />
                </Box>
              </AccordionDetails>
            </Accordion>

            <Grid container spacing={2.5} sx={{ mt: 0.5 }}>
              <Grid item xs={12} md={7}>
                <Box className="muted-surface payment-balance">
                  <Typography className="section-heading">Payment received now (optional)</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Enter any amount received today. A smaller amount is saved as a partial
                    payment, and the balance stays open.
                  </Typography>
                  <Box className="form-grid">
                    <TextField
                      className="span-6"
                      label="Amount received"
                      type="number"
                      value={form.amount_paid_now}
                      onChange={(event) => setField("amount_paid_now", event.target.value)}
                      inputProps={{ min: 0, max: totals.grand, step: "0.01" }}
                    />
                    <TextField
                      className="span-6"
                      select
                      label="Payment method"
                      value={form.payment_method}
                      onChange={(event) => setField("payment_method", event.target.value)}
                      disabled={paidNow <= 0}
                    >
                      {paymentMethods.map((method) => (
                        <MenuItem key={method} value={method}>
                          {method}
                        </MenuItem>
                      ))}
                    </TextField>
                    {availableAdvance > 0 ? (
                      <TextField
                        className="span-6"
                        label="Use customer advance"
                        type="number"
                        value={form.advance_to_adjust}
                        onChange={(event) => setField("advance_to_adjust", event.target.value)}
                        helperText={`${formatCurrency(availableAdvance)} available`}
                        inputProps={{
                          min: 0,
                          max: Math.min(availableAdvance, totals.grand),
                          step: "0.01",
                        }}
                      />
                    ) : null}
                  </Box>
                  {paymentInvalid ? (
                    <Alert severity="error" sx={{ mt: 2 }}>
                      Payment and advance cannot exceed the invoice total or available advance.
                    </Alert>
                  ) : null}
                </Box>
              </Grid>
              <Grid item xs={12} md={5}>
                <Box className="summary-panel">
                  <Typography className="section-heading">Invoice summary</Typography>
                  <Stack spacing={0}>
                    <Box className="inline-row">
                      <span>Subtotal</span>
                      <strong>{formatCurrency(totals.subtotal)}</strong>
                    </Box>
                    {totals.discount > 0 ? (
                      <Box className="inline-row">
                        <span>Discount</span>
                        <strong>-{formatCurrency(totals.discount)}</strong>
                      </Box>
                    ) : null}
                    <Box className="inline-row">
                      <span>GST</span>
                      <strong>{formatCurrency(totals.gst)}</strong>
                    </Box>
                    <Box className="inline-row">
                      <span>Grand total</span>
                      <Typography variant="h6">{formatCurrency(totals.grand)}</Typography>
                    </Box>
                    <Box className="inline-row" sx={{ borderBottom: 0 }}>
                      <span>Balance after payment</span>
                      <Typography variant="h6" color="primary.main">
                        {formatCurrency(remainingAfterPayment)}
                      </Typography>
                    </Box>
                  </Stack>
                </Box>
              </Grid>
            </Grid>

            <Divider sx={{ my: 2.5 }} />
            <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
              <Button
                type="submit"
                variant="contained"
                size="large"
                startIcon={<FilePlus2 size={18} />}
                disabled={isSubmitting || paymentInvalid || totals.grand <= 0}
              >
                {isSubmitting ? "Creating..." : "Create invoice"}
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <Box sx={{ px: 2.75, py: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="h6">Recent invoices</Typography>
          <Typography variant="body2" color="text.secondary">
            Paid and remaining amounts update after every payment.
          </Typography>
        </Box>
        {invoices.length ? (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Invoice</TableCell>
                  <TableCell>Customer</TableCell>
                  <TableCell align="right">Total</TableCell>
                  <TableCell align="right">Paid</TableCell>
                  <TableCell align="right">Balance</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {invoices.map((invoice) => {
                  const availableToReceive = Number(
                    invoice.available_payment_amount ?? invoice.remaining_amount ?? 0
                  );
                  const pendingPayment = Number(invoice.pending_payment_amount || 0);
                  const canReceivePayment =
                    availableToReceive > 0 &&
                    !["Fully Paid", "Cancelled"].includes(invoice.payment_status);
                  return (
                    <TableRow key={invoice.id} hover>
                      <TableCell>
                        <Typography fontWeight={750}>{invoice.invoice_number}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {invoice.invoice_date}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {customerById.get(String(invoice.customer_id))?.name || "—"}
                      </TableCell>
                      <TableCell align="right">
                        <Currency value={invoice.grand_total} />
                      </TableCell>
                      <TableCell align="right">
                        <Currency
                          value={
                            Number(invoice.total_paid || 0) +
                            Number(invoice.advance_adjusted || 0)
                          }
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography fontWeight={750}>
                          <Currency value={invoice.remaining_amount} />
                        </Typography>
                        {pendingPayment > 0 ? (
                          <Typography variant="caption" color="warning.main">
                            {formatCurrency(pendingPayment)} cheque pending
                          </Typography>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        <StatusBadge value={invoice.payment_status} />
                      </TableCell>
                      <TableCell align="right">
                        <Box className="table-row-actions">
                          {canReceivePayment ? (
                            <Button
                              size="small"
                              variant="outlined"
                              startIcon={<ReceiptIndianRupee size={16} />}
                              onClick={() => recordPayment(invoice)}
                            >
                              Record payment
                            </Button>
                          ) : null}
                          <Tooltip title="Download invoice">
                            <IconButton
                              size="small"
                              aria-label="Download invoice"
                              onClick={() => downloadBlob(`/invoices/${invoice.id}/pdf`)}
                            >
                              <Download size={18} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Print invoice">
                            <IconButton
                              size="small"
                              aria-label="Print invoice"
                              onClick={() => printPdf(`/invoices/${invoice.id}/pdf`)}
                            >
                              <Printer size={18} />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Box className="empty-state">
            <Box>
              <PackageOpen size={34} />
              <Typography variant="h6">No invoices yet</Typography>
              <Typography variant="body2">
                Your first invoice will appear here after it is created.
              </Typography>
            </Box>
          </Box>
        )}
      </Card>

      <CustomerDialog
        open={customerDialogOpen}
        onClose={() => setCustomerDialogOpen(false)}
        initialMobile={customerSearch.replace(/\D/g, "")}
        onCreated={(customer) => {
          setCustomers((current) => mergeCustomers(current, [customer]));
          setField("customer_id", customer.id);
          setCustomerSearch(
            customer.mobile_number
              ? `${customer.mobile_number} — ${customer.name}`
              : customer.name
          );
          setMessage(`${customer.name} added and selected`);
        }}
      />
    </Stack>
  );
}
