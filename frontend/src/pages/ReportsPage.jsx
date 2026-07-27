import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import {
  BadgeIndianRupee,
  BarChart3,
  Download,
  ReceiptText,
  RefreshCw,
  Table2,
  Users,
  Wallet,
} from "lucide-react";

import api, { downloadBlob } from "../api/client.js";
import Currency, { formatCurrency } from "../components/Currency.jsx";
import MetricCard from "../components/MetricCard.jsx";

const reportTabs = [
  { key: "sales", label: "Sales", path: "/reports/sales" },
  { key: "payments", label: "Collections", path: "/reports/payments" },
  { key: "outstanding", label: "Outstanding", path: "/reports/outstanding" },
  { key: "ageing", label: "Ageing", path: "/reports/ageing" },
  { key: "advances", label: "Advances", path: "/reports/advances" },
  { key: "gst", label: "GST", path: "/reports/gst" },
  { key: "cheques", label: "Cheques", path: "/reports/cheques" },
  { key: "reversed", label: "Reversed", path: "/reports/reversed-payments" },
];

const rangeOptions = [7, 30, 90];

export default function ReportsPage() {
  const [view, setView] = useState("tables");
  const [active, setActive] = useState("sales");
  const [rows, setRows] = useState([]);
  const [days, setDays] = useState(30);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const activeReport = reportTabs.find((tab) => tab.key === active);

  const loadReport = useCallback(async function loadReport() {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(activeReport.path);
      setRows(Array.isArray(data) ? data : [data]);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Could not load this report.");
    } finally {
      setLoading(false);
    }
  }, [activeReport]);

  const loadAnalytics = useCallback(async function loadAnalytics() {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/reports/analytics", { params: { days } });
      setAnalytics(data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Could not load visual reports.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    if (view === "tables") {
      loadReport();
    }
  }, [loadReport, view]);

  useEffect(() => {
    if (view === "visual") {
      loadAnalytics();
    }
  }, [loadAnalytics, view]);

  const headers = rows[0] ? Object.keys(rows[0]) : [];
  const refresh = view === "visual" ? loadAnalytics : loadReport;

  return (
    <Stack spacing={3}>
      <Box className="page-header">
        <Box>
          <Typography variant="h4">Reports</Typography>
          <Typography variant="body2" color="text.secondary">
            {view === "visual"
              ? "See business trends and balances at a glance"
              : "Sales, collections, GST, outstanding, ageing, advances, cheque status, and reversals"}
          </Typography>
        </Box>
        <Box className="table-actions">
          {view === "tables" ? (
            <>
              <Button
                variant="outlined"
                startIcon={<Download size={18} />}
                onClick={() =>
                  downloadBlob(
                    `${activeReport.path}?export=excel`,
                    `${activeReport.key}.xlsx`
                  )
                }
              >
                Excel
              </Button>
              <Button
                variant="outlined"
                startIcon={<Download size={18} />}
                onClick={() =>
                  downloadBlob(`${activeReport.path}?export=csv`, `${activeReport.key}.csv`)
                }
              >
                CSV
              </Button>
            </>
          ) : null}
          <Button variant="outlined" startIcon={<RefreshCw size={18} />} onClick={refresh}>
            Refresh
          </Button>
        </Box>
      </Box>

      <ToggleButtonGroup
        exclusive
        value={view}
        onChange={(_, value) => value && setView(value)}
        size="small"
        aria-label="Report view"
        sx={{ alignSelf: "flex-start", bgcolor: "background.paper" }}
      >
        <ToggleButton value="tables">
          <Table2 size={17} style={{ marginRight: 8 }} />
          Table reports
        </ToggleButton>
        <ToggleButton value="visual">
          <BarChart3 size={17} style={{ marginRight: 8 }} />
          Visual reports
        </ToggleButton>
      </ToggleButtonGroup>

      {error ? <Alert severity="error">{error}</Alert> : null}

      {view === "tables" ? (
        <TableReports
          active={active}
          headers={headers}
          loading={loading}
          rows={rows}
          setActive={setActive}
        />
      ) : (
        <VisualReports
          analytics={analytics}
          days={days}
          loading={loading}
          setDays={setDays}
        />
      )}
    </Stack>
  );
}

function TableReports({ active, headers, loading, rows, setActive }) {
  return (
    <Card>
      <CardContent>
        <Tabs
          value={active}
          onChange={(_, value) => setActive(value)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}
        >
          {reportTabs.map((tab) => (
            <Tab key={tab.key} label={tab.label} value={tab.key} />
          ))}
        </Tabs>
        {loading ? (
          <LoadingState />
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {headers.map((header) => (
                    <TableCell key={header}>{header.replaceAll("_", " ")}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={index} hover>
                    {headers.map((header) => (
                      <TableCell key={header}>
                        {isMoneyColumn(header) ? <Currency value={row[header]} /> : String(row[header] ?? "-")}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
                {!rows.length ? (
                  <TableRow>
                    <TableCell colSpan={Math.max(headers.length, 1)}>
                      <Typography color="text.secondary">No report rows</Typography>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
}

function VisualReports({ analytics, days, loading, setDays }) {
  const daily = analytics?.daily || [];
  const summary = analytics?.summary;
  const salesSeries = useMemo(
    () => [
      { key: "sales", label: "Sales", color: "#176b5b" },
      { key: "collections", label: "Collections", color: "#d46b3b" },
    ],
    []
  );
  const customerSeries = useMemo(
    () => [
      { key: "new_customers", label: "New customers", color: "#3478b8" },
      { key: "invoice_count", label: "Invoices", color: "#8765a9" },
    ],
    []
  );
  const outstandingSeries = useMemo(
    () => [{ key: "outstanding", label: "Outstanding", color: "#b66a12" }],
    []
  );

  return (
    <Stack spacing={2.5}>
      <Box
        sx={{
          display: "flex",
          alignItems: { xs: "flex-start", sm: "center" },
          justifyContent: "space-between",
          gap: 2,
          flexDirection: { xs: "column", sm: "row" },
        }}
      >
        <Box>
          <Typography variant="h6">Business overview</Typography>
          <Typography variant="body2" color="text.secondary">
            Daily figures through today
          </Typography>
        </Box>
        <ToggleButtonGroup
          exclusive
          value={days}
          onChange={(_, value) => value && setDays(value)}
          size="small"
          aria-label="Visual report period"
          sx={{ bgcolor: "background.paper" }}
        >
          {rangeOptions.map((option) => (
            <ToggleButton key={option} value={option}>
              {option} days
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {loading && !analytics ? <LoadingState /> : null}

      {analytics ? (
        <>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, minmax(0, 1fr))",
                xl: "repeat(4, minmax(0, 1fr))",
              },
              gap: 2,
              opacity: loading ? 0.6 : 1,
            }}
          >
            <MetricCard label="Sales in period" value={summary.total_sales} icon={BadgeIndianRupee} />
            <MetricCard label="Collections in period" value={summary.total_collections} icon={Wallet} tone="#d46b3b" />
            <MetricCard label="Amount still to collect" value={summary.current_outstanding} icon={ReceiptText} tone="#b66a12" />
            <MetricCard label="Customers served" value={summary.customers_served} icon={Users} currency={false} tone="#3478b8" />
          </Box>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", xl: "repeat(2, minmax(0, 1fr))" },
              gap: 2,
            }}
          >
            <TrendChart
              title="Sales and collections over days"
              subtitle={`${summary.invoice_count} invoices in this period`}
              data={daily}
              series={salesSeries}
              currency
            />
            <TrendChart
              title="New customers over days"
              subtitle={`${summary.new_customers} new customers · invoice count shown for context`}
              data={daily}
              series={customerSeries}
            />
          </Box>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.35fr) minmax(300px, 0.65fr)" },
              gap: 2,
            }}
          >
            <TrendChart
              title="Amount remaining to collect"
              subtitle="Closing customer outstanding balance for each day"
              data={daily}
              series={outstandingSeries}
              currency
            />
            <TopMaterials materials={analytics.top_materials || []} />
          </Box>
        </>
      ) : null}
    </Stack>
  );
}

function TrendChart({ currency = false, data, series, subtitle, title }) {
  const width = 760;
  const height = 260;
  const margin = { top: 22, right: 22, bottom: 42, left: 74 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = data.flatMap((point) => series.map((item) => Number(point[item.key] || 0)));
  const maximum = Math.max(0, ...values);
  const yMaximum = maximum || 1;
  const hasActivity = maximum > 0;
  const xAt = (index) =>
    margin.left + (data.length <= 1 ? plotWidth / 2 : (index / (data.length - 1)) * plotWidth);
  const yAt = (value) => margin.top + plotHeight - (Number(value || 0) / yMaximum) * plotHeight;
  const labelIndexes = [...new Set([0, Math.floor((data.length - 1) / 2), data.length - 1])].filter(
    (index) => index >= 0
  );

  return (
    <Card sx={{ minWidth: 0 }}>
      <CardContent>
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="h6">{title}</Typography>
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        </Box>
        <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" sx={{ mb: 1 }}>
          {series.map((item) => (
            <Stack key={item.key} direction="row" spacing={0.75} alignItems="center">
              <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: item.color }} />
              <Typography variant="caption" color="text.secondary">
                {item.label}
              </Typography>
            </Stack>
          ))}
        </Stack>
        {!data.length || !hasActivity ? (
          <Box className="empty-state" sx={{ minHeight: 230 }}>
            <Box>
              <BarChart3 size={30} />
              <Typography>No activity in this period</Typography>
            </Box>
          </Box>
        ) : (
          <Box sx={{ width: "100%", overflow: "hidden" }}>
            <svg
              viewBox={`0 0 ${width} ${height}`}
              width="100%"
              role="img"
              aria-label={`${title}. ${subtitle}`}
              style={{ display: "block", minWidth: 0 }}
            >
              {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
                const y = margin.top + plotHeight * fraction;
                const value = yMaximum * (1 - fraction);
                return (
                  <g key={fraction}>
                    <line
                      x1={margin.left}
                      x2={width - margin.right}
                      y1={y}
                      y2={y}
                      stroke="#e5ebe8"
                      strokeWidth="1"
                    />
                    <text
                      x={margin.left - 10}
                      y={y + 4}
                      textAnchor="end"
                      fill="#71807b"
                      fontSize="11"
                    >
                      {currency ? compactCurrency(value) : compactNumber(value)}
                    </text>
                  </g>
                );
              })}

              {labelIndexes.map((index) => (
                <text
                  key={index}
                  x={xAt(index)}
                  y={height - 12}
                  textAnchor={index === 0 ? "start" : index === data.length - 1 ? "end" : "middle"}
                  fill="#71807b"
                  fontSize="11"
                >
                  {formatChartDate(data[index].date)}
                </text>
              ))}

              {series.map((item) => {
                const points = data
                  .map((point, index) => `${xAt(index)},${yAt(point[item.key])}`)
                  .join(" ");
                return (
                  <g key={item.key}>
                    <polyline
                      points={points}
                      fill="none"
                      stroke={item.color}
                      strokeWidth="3"
                      strokeLinejoin="round"
                      strokeLinecap="round"
                    />
                    {data.length <= 31
                      ? data.map((point, index) => (
                          <circle
                            key={`${item.key}-${point.date}`}
                            cx={xAt(index)}
                            cy={yAt(point[item.key])}
                            r="3"
                            fill="#ffffff"
                            stroke={item.color}
                            strokeWidth="2"
                          >
                            <title>
                              {`${item.label}, ${formatChartDate(point.date)}: ${
                                currency
                                  ? formatCurrency(point[item.key])
                                  : compactNumber(point[item.key])
                              }`}
                            </title>
                          </circle>
                        ))
                      : null}
                  </g>
                );
              })}
            </svg>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

function TopMaterials({ materials }) {
  const maximum = Math.max(0, ...materials.map((item) => Number(item.sales || 0)));

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Top materials</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Highest sales value in the selected period
        </Typography>
        {materials.length ? (
          <Stack spacing={2.25}>
            {materials.map((item) => (
              <Box key={item.material}>
                <Box className="bar-row" sx={{ mb: 0.75 }}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" fontWeight={700} noWrap>
                      {item.material}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {compactNumber(item.quantity)} {item.unit}
                    </Typography>
                  </Box>
                  <Typography variant="body2" fontWeight={750}>
                    <Currency value={item.sales} />
                  </Typography>
                </Box>
                <Box className="bar-track">
                  <Box
                    className="bar-fill"
                    sx={{ width: `${maximum ? (Number(item.sales) / maximum) * 100 : 0}%` }}
                  />
                </Box>
              </Box>
            ))}
          </Stack>
        ) : (
          <Box className="empty-state" sx={{ minHeight: 230 }}>
            <Box>
              <BarChart3 size={30} />
              <Typography>No material sales in this period</Typography>
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

function LoadingState() {
  return (
    <Box sx={{ minHeight: 220, display: "grid", placeItems: "center" }}>
      <Stack spacing={1.5} alignItems="center">
        <CircularProgress size={28} />
        <Typography variant="body2" color="text.secondary">
          Loading report…
        </Typography>
      </Stack>
    </Box>
  );
}

function formatChartDate(value) {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short" }).format(
    new Date(`${value}T00:00:00`)
  );
}

function compactCurrency(value) {
  return `₹${compactNumber(value)}`;
}

function compactNumber(value) {
  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value || 0));
}

function isMoneyColumn(header) {
  return [
    "amount",
    "total",
    "grand_total",
    "total_paid",
    "remaining_amount",
    "outstanding",
    "advance",
    "advance_balance",
    "credit_limit",
    "taxable_amount",
    "cgst",
    "sgst",
    "igst",
    "bucket_0_30",
    "bucket_31_60",
    "bucket_61_90",
    "bucket_91_180",
    "bucket_over_180",
  ].includes(header);
}
