import { Box, Card, CardContent, Typography } from "@mui/material";

import Currency from "./Currency.jsx";

export default function MetricCard({ label, value, icon: Icon, currency = true, tone = "#234a57" }) {
  return (
    <Card className="metric-card">
      <CardContent>
        <Box className="metric-card__header">
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          {Icon ? <Icon size={18} color={tone} /> : null}
        </Box>
        <Typography variant="h5" component="div" sx={{ mt: 1 }}>
          {currency ? <Currency value={value} /> : value}
        </Typography>
      </CardContent>
    </Card>
  );
}
