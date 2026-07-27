import { useEffect, useState } from "react";
import { Box, Card, CardContent, Grid, LinearProgress, Stack, Typography } from "@mui/material";
import {
  BadgeIndianRupee,
  Clock3,
  CreditCard,
  FileClock,
  ReceiptText,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";

import api from "../api/client.js";
import Currency, { formatCurrency } from "../components/Currency.jsx";
import MetricCard from "../components/MetricCard.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const emptySummary = {
  todays_sales: 0,
  todays_collections: 0,
  total_outstanding_amount: 0,
  partially_paid_invoice_amount: 0,
  fully_unpaid_invoice_amount: 0,
  customer_advances: 0,
  total_customers: 0,
  todays_orders: 0,
  monthly_revenue: 0,
  top_selling_materials: [],
  recent_invoices: [],
  recent_payments: [],
};

export default function DashboardPage() {
  const [summary, setSummary] = useState(emptySummary);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/dashboard")
      .then(({ data }) => setSummary({ ...emptySummary, ...data }))
      .finally(() => setLoading(false));
  }, []);

  const maxMaterial = Math.max(
    1,
    ...summary.top_selling_materials.map((row) => Number(row.sales || 0))
  );

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Dashboard</Typography>
        <Typography variant="body2" color="text.secondary">
          Today, collections, invoices, advances, and outstanding exposure
        </Typography>
      </Box>
      {loading ? <LinearProgress /> : null}
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Today's sales" value={summary.todays_sales} icon={BadgeIndianRupee} />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Today's collections" value={summary.todays_collections} icon={CreditCard} tone="#24744d" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Outstanding" value={summary.total_outstanding_amount} icon={FileClock} tone="#b42318" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Customer advances" value={summary.customer_advances} icon={Wallet} tone="#2768a6" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Partial dues" value={summary.partially_paid_invoice_amount} icon={Clock3} tone="#b36b00" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Unpaid invoices" value={summary.fully_unpaid_invoice_amount} icon={ReceiptText} tone="#b42318" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="This month's sales" value={summary.monthly_revenue} icon={TrendingUp} tone="#176b5b" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard label="Customers" value={summary.total_customers} icon={Users} currency={false} tone="#234a57" />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} lg={5}>
          <Card>
            <CardContent>
              <Typography variant="h6">Top Materials</Typography>
              <Stack spacing={1.5} sx={{ mt: 2 }}>
                {summary.top_selling_materials.length ? (
                  summary.top_selling_materials.map((row) => (
                    <Box key={row.material}>
                      <Box className="bar-row">
                        <Typography variant="body2">{row.material}</Typography>
                        <Typography variant="body2" fontWeight={700}>
                          {formatCurrency(row.sales)}
                        </Typography>
                      </Box>
                      <Box className="bar-track">
                        <Box className="bar-fill" sx={{ width: `${(Number(row.sales || 0) / maxMaterial) * 100}%` }} />
                      </Box>
                    </Box>
                  ))
                ) : (
                  <Typography color="text.secondary">No material sales yet</Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} lg={7}>
          <Card>
            <CardContent>
              <Typography variant="h6">Recent Invoices</Typography>
              <Stack spacing={1.2} sx={{ mt: 2 }}>
                {summary.recent_invoices.length ? (
                  summary.recent_invoices.map((invoice) => (
                    <Box className="inline-row" key={invoice.id}>
                      <Box>
                        <Typography variant="body2" fontWeight={700}>
                          {invoice.invoice_number}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Customer #{invoice.customer_id}
                        </Typography>
                      </Box>
                      <Currency value={invoice.grand_total} />
                      <StatusBadge value={invoice.payment_status} />
                    </Box>
                  ))
                ) : (
                  <Typography color="text.secondary">No invoices yet</Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Stack>
  );
}
