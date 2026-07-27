import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { ChevronDown, UserPlus } from "lucide-react";

import api from "../api/client.js";

const defaults = {
  name: "",
  mobile_number: "",
  gst_number: "",
  city: "",
  state: "",
  billing_address: "",
  delivery_address: "",
  opening_balance: 0,
  credit_limit: 0,
};

function requestErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return "Unable to add customer";
}

export default function CustomerDialog({
  open,
  onClose,
  onCreated,
  initialMobile = "",
}) {
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState } = useForm({
    defaultValues: defaults,
  });

  useEffect(() => {
    if (open) {
      reset({ ...defaults, mobile_number: initialMobile });
      setError("");
    }
  }, [initialMobile, open, reset]);

  async function submit(values) {
    setError("");
    try {
      const { data } = await api.post("/customers", {
        name: values.name.trim(),
        mobile_number: values.mobile_number.trim(),
        gst_number: values.gst_number.trim() || null,
        city: values.city.trim() || null,
        state: values.state.trim() || null,
        billing_address: values.billing_address.trim() || null,
        delivery_address: values.delivery_address.trim() || null,
        opening_balance: Number(values.opening_balance || 0),
        credit_limit: Number(values.credit_limit || 0),
      });
      onCreated?.(data);
      onClose();
    } catch (requestError) {
      setError(requestErrorMessage(requestError));
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <Box component="form" onSubmit={handleSubmit(submit)}>
        <DialogTitle>
          <Stack direction="row" spacing={1.25} alignItems="center">
            <Box className="dialog-icon">
              <UserPlus size={19} />
            </Box>
            <Box>
              <Typography variant="h6">Add customer</Typography>
              <Typography variant="caption" color="text.secondary">
                Mobile number is used to find and prevent duplicate customers.
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            <Grid container spacing={2}>
              <Grid item xs={12} sm={7}>
                <TextField
                  autoFocus
                  fullWidth
                  label="Customer name"
                  error={Boolean(formState.errors.name)}
                  helperText={formState.errors.name ? "Customer name is required" : ""}
                  {...register("name", { required: true, minLength: 2 })}
                />
              </Grid>
              <Grid item xs={12} sm={5}>
                <TextField
                  fullWidth
                  label="Mobile number"
                  error={Boolean(formState.errors.mobile_number)}
                  helperText={
                    formState.errors.mobile_number ? "Enter a valid mobile number" : ""
                  }
                  inputProps={{ inputMode: "tel" }}
                  {...register("mobile_number", {
                    required: true,
                    validate: (value) =>
                      value.replace(/\D/g, "").length >= 10,
                  })}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth label="City" {...register("city")} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth label="State" {...register("state")} />
              </Grid>
            </Grid>

            <Accordion
              disableGutters
              elevation={0}
              sx={{
                border: "1px solid",
                borderColor: "divider",
                borderRadius: "10px !important",
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary expandIcon={<ChevronDown size={18} />}>
                <Box>
                  <Typography fontWeight={750}>More details</Typography>
                  <Typography variant="caption" color="text.secondary">
                    GST, addresses and opening balances
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <TextField fullWidth label="GST number" {...register("gst_number")} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Opening balance"
                      type="number"
                      inputProps={{ min: 0, step: "0.01" }}
                      {...register("opening_balance")}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Credit limit"
                      type="number"
                      inputProps={{ min: 0, step: "0.01" }}
                      {...register("credit_limit")}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Billing address"
                      multiline
                      minRows={2}
                      {...register("billing_address")}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Delivery address"
                      multiline
                      minRows={2}
                      {...register("delivery_address")}
                    />
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            startIcon={<UserPlus size={17} />}
            disabled={formState.isSubmitting}
          >
            {formState.isSubmitting ? "Adding..." : "Add customer"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
