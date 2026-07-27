import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
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
import { BookOpen, Search, Send, UserPlus } from "lucide-react";

import api from "../api/client.js";
import Currency from "../components/Currency.jsx";
import CustomerDialog from "../components/CustomerDialog.jsx";

function requestErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return fallback;
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState("");
  const [ledger, setLedger] = useState([]);
  const [ledgerCustomer, setLedgerCustomer] = useState(null);
  const [customerDialogOpen, setCustomerDialogOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await api.get("/customers", {
          params: { q: search.trim() || undefined, limit: 50 },
        });
        if (!ignore) {
          setCustomers(data);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) setError(requestErrorMessage(requestError, "Unable to load customers"));
      }
    }, search ? 250 : 0);

    return () => {
      ignore = true;
      window.clearTimeout(timer);
    };
  }, [search]);

  async function openLedger(customer) {
    try {
      const { data } = await api.get(`/customers/${customer.id}/ledger`);
      setLedger(data);
      setLedgerCustomer(customer);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to load customer ledger"));
    }
  }

  async function reminder(customer) {
    try {
      await api.post(`/customers/${customer.id}/payment-reminder`);
      setMessage(`Reminder logged for ${customer.name}`);
    } catch (requestError) {
      setError(requestErrorMessage(requestError, "Unable to log reminder"));
    }
  }

  return (
    <Stack spacing={3}>
      <Box className="page-header">
        <Box>
          <Typography variant="h4">Customers</Typography>
          <Typography variant="body2" color="text.secondary">
            Search by mobile number, review balances and open ledger history
          </Typography>
        </Box>
        <Box className="page-actions">
          <TextField
            size="small"
            placeholder="Search mobile or name"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search size={17} />
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="contained"
            startIcon={<UserPlus size={18} />}
            onClick={() => setCustomerDialogOpen(true)}
          >
            Add customer
          </Button>
        </Box>
      </Box>

      {message ? <Alert onClose={() => setMessage("")}>{message}</Alert> : null}
      {error ? (
        <Alert severity="error" onClose={() => setError("")}>
          {error}
        </Alert>
      ) : null}

      <Card>
        {customers.length ? (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Mobile</TableCell>
                  <TableCell>Customer</TableCell>
                  <TableCell>City</TableCell>
                  <TableCell align="right">Outstanding</TableCell>
                  <TableCell align="right">Advance</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {customers.map((customer) => (
                  <TableRow key={customer.id} hover>
                    <TableCell>
                      <Typography fontWeight={800}>{customer.mobile_number || "—"}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography fontWeight={750}>{customer.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        GST {customer.gst_number || "—"}
                      </Typography>
                    </TableCell>
                    <TableCell>{customer.city || "—"}</TableCell>
                    <TableCell align="right">
                      <Currency value={customer.current_outstanding_balance} />
                    </TableCell>
                    <TableCell align="right">
                      <Currency value={customer.advance_balance} />
                    </TableCell>
                    <TableCell align="right">
                      <Box className="table-row-actions">
                        <Tooltip title="Open ledger">
                          <IconButton
                            size="small"
                            aria-label={`Open ${customer.name} ledger`}
                            onClick={() => openLedger(customer)}
                          >
                            <BookOpen size={18} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Log payment reminder">
                          <IconButton
                            size="small"
                            aria-label={`Remind ${customer.name}`}
                            onClick={() => reminder(customer)}
                          >
                            <Send size={18} />
                          </IconButton>
                        </Tooltip>
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
              <UserPlus size={34} />
              <Typography variant="h6">
                {search ? "No matching customer" : "No customers yet"}
              </Typography>
              <Typography variant="body2">
                {search
                  ? "Try another mobile number or name."
                  : "Use Add customer to create the first record."}
              </Typography>
            </Box>
          </Box>
        )}
      </Card>

      <CustomerDialog
        open={customerDialogOpen}
        onClose={() => setCustomerDialogOpen(false)}
        initialMobile={search.replace(/\D/g, "")}
        onCreated={(customer) => {
          setCustomers((current) => [customer, ...current].slice(0, 50));
          setMessage(`${customer.name} added`);
        }}
      />

      <Dialog
        open={Boolean(ledgerCustomer)}
        onClose={() => setLedgerCustomer(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{ledgerCustomer?.name} ledger</DialogTitle>
        <DialogContent dividers>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Reference</TableCell>
                  <TableCell align="right">Debit</TableCell>
                  <TableCell align="right">Credit</TableCell>
                  <TableCell align="right">Balance</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {ledger.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.transaction_date}</TableCell>
                    <TableCell>{row.transaction_type}</TableCell>
                    <TableCell>{row.reference_number}</TableCell>
                    <TableCell align="right">
                      <Currency value={row.debit} />
                    </TableCell>
                    <TableCell align="right">
                      <Currency value={row.credit} />
                    </TableCell>
                    <TableCell align="right">
                      <Currency value={row.running_balance} />
                    </TableCell>
                  </TableRow>
                ))}
                {!ledger.length ? (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Typography color="text.secondary">No ledger entries yet</Typography>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
      </Dialog>
    </Stack>
  );
}
