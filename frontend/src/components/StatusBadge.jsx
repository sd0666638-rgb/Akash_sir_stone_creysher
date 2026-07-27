import { Chip } from "@mui/material";

const statusColor = {
  Unpaid: "error",
  "Partially Paid": "warning",
  "Fully Paid": "success",
  Advance: "info",
  Cancelled: "default",
  Overpaid: "secondary",
  Successful: "success",
  Pending: "warning",
  Reversed: "default",
  Bounced: "error",
};

export default function StatusBadge({ value }) {
  return (
    <Chip
      label={value || "Unknown"}
      color={statusColor[value] || "default"}
      size="small"
      sx={{ minWidth: 88, fontWeight: 700 }}
    />
  );
}
