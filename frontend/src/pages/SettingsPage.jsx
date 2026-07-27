import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  MenuItem,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import {
  Building2,
  Landmark,
  Save,
  Settings2,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";

import api from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const defaultValues = {
  company_name: "",
  company_address: "",
  company_phone: "",
  company_gstin: "",
  company_state: "",
  company_gst_state_code: "",
  company_jurisdiction: "",
  company_bank_name: "",
  company_bank_account: "",
  company_bank_ifsc: "",
  company_bank_branch: "",
};

const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
const IFSC_PATTERN = /^[A-Z]{4}0[A-Z0-9]{6}$/;
const PHONE_PATTERN = /^[+0-9()\-\s]{7,20}$/;
const emptyUserForm = {
  full_name: "",
  username: "",
  role_name: "Operator",
  password: "",
  confirm_password: "",
};
const roleDescriptions = {
  Admin: "Full access, including company settings and user management.",
  Manager: "Manage customers, materials, invoices and company details.",
  Operator: "Create customers and invoices and record payments.",
  Accountant: "Manage payments, cheques, advances and financial reports.",
};

function errorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
}

function formValues(data = {}) {
  return Object.fromEntries(
    Object.keys(defaultValues).map((key) => [
      key,
      data[key] ?? data[key.toUpperCase()] ?? "",
    ])
  );
}

function cleanPayload(values) {
  return {
    company_name: values.company_name.trim(),
    company_address: values.company_address.trim(),
    company_phone: values.company_phone.trim(),
    company_gstin: values.company_gstin.trim().toUpperCase(),
    company_state: values.company_state.trim(),
    company_gst_state_code: values.company_gst_state_code.trim(),
    company_jurisdiction: values.company_jurisdiction.trim(),
    company_bank_name: values.company_bank_name.trim(),
    company_bank_account: values.company_bank_account.trim(),
    company_bank_ifsc: values.company_bank_ifsc.trim().toUpperCase(),
    company_bank_branch: values.company_bank_branch.trim(),
  };
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [message, setMessage] = useState("");
  const [managedUsers, setManagedUsers] = useState([]);
  const [availableRoles, setAvailableRoles] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState("");
  const [userMessage, setUserMessage] = useState("");
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [userForm, setUserForm] = useState(emptyUserForm);
  const [userSaving, setUserSaving] = useState(false);
  const [userFormError, setUserFormError] = useState("");
  const { register, handleSubmit, reset, formState } = useForm({ defaultValues });

  const roleNames = new Set((user?.roles || []).map((role) => role.name));
  const canEdit = roleNames.has("Admin") || roleNames.has("Manager");
  const canManageUsers = roleNames.has("Admin");
  const readOnlyProps = { readOnly: !canEdit };

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const { data } = await api.get("/settings/company");
      reset(formValues(data));
    } catch (error) {
      setLoadError(errorMessage(error, "Unable to load company settings"));
    } finally {
      setLoading(false);
    }
  }, [reset]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const loadUsers = useCallback(async () => {
    if (!canManageUsers) return;
    setUsersLoading(true);
    setUsersError("");
    try {
      const [usersResponse, rolesResponse] = await Promise.all([
        api.get("/users"),
        api.get("/users/roles"),
      ]);
      setManagedUsers(usersResponse.data);
      setAvailableRoles(rolesResponse.data);
    } catch (error) {
      setUsersError(errorMessage(error, "Unable to load users"));
    } finally {
      setUsersLoading(false);
    }
  }, [canManageUsers]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  async function saveSettings(values) {
    setSaveError("");
    setMessage("");
    try {
      const { data } = await api.put("/settings/company", cleanPayload(values));
      const updatedValues = formValues(data);
      reset(updatedValues);
      window.dispatchEvent(
        new window.CustomEvent("company-settings-updated", {
          detail: { companyName: updatedValues.company_name },
        })
      );
      setMessage("Company details saved. New invoices and PDFs will use these details.");
    } catch (error) {
      setSaveError(errorMessage(error, "Unable to save company settings"));
    }
  }

  function setUserField(field, value) {
    setUserForm((current) => ({ ...current, [field]: value }));
  }

  function openUserDialog() {
    setUserForm(emptyUserForm);
    setUserFormError("");
    setUserDialogOpen(true);
  }

  async function addUser(event) {
    event.preventDefault();
    setUserFormError("");
    setUserMessage("");
    if (userForm.password !== userForm.confirm_password) {
      setUserFormError("The password confirmation does not match.");
      return;
    }
    setUserSaving(true);
    try {
      const { data } = await api.post("/users", {
        full_name: userForm.full_name.trim(),
        username: userForm.username.trim().toLowerCase(),
        password: userForm.password,
        role_names: [userForm.role_name],
      });
      setManagedUsers((current) =>
        [...current, data].sort((left, right) =>
          left.full_name.localeCompare(right.full_name)
        )
      );
      setUserDialogOpen(false);
      setUserMessage(`${data.full_name} can now sign in as ${data.username}.`);
    } catch (error) {
      setUserFormError(errorMessage(error, "Unable to add user"));
    } finally {
      setUserSaving(false);
    }
  }

  if (loading) {
    return (
      <Stack spacing={2}>
        <Skeleton variant="rounded" height={76} />
        <Skeleton variant="rounded" height={410} />
      </Stack>
    );
  }

  return (
    <Stack spacing={3} component="form" onSubmit={handleSubmit(saveSettings)}>
      <Box className="page-header">
        <Box>
          <Typography variant="h4">Settings</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage company details, documents and user access
          </Typography>
        </Box>
        {canEdit ? (
          <Button
            type="submit"
            variant="contained"
            startIcon={<Save size={18} />}
            disabled={formState.isSubmitting || Boolean(loadError)}
          >
            {formState.isSubmitting ? "Saving..." : "Save company details"}
          </Button>
        ) : null}
      </Box>

      {loadError ? (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={loadSettings}>
              Retry
            </Button>
          }
        >
          {loadError}
        </Alert>
      ) : null}
      {saveError ? <Alert severity="error">{saveError}</Alert> : null}
      {message ? <Alert onClose={() => setMessage("")}>{message}</Alert> : null}
      {!canEdit ? (
        <Alert severity="info">
          These settings are read-only for your account. An administrator or manager can
          update them.
        </Alert>
      ) : null}

      <Card className="settings-card">
        <CardContent>
          <Box className="settings-section-title">
            <Box className="dialog-icon">
              <Building2 size={20} />
            </Box>
            <Box>
              <Typography variant="h6">Business details</Typography>
              <Typography variant="body2" color="text.secondary">
                The company name and contact details shown at the top of each document
              </Typography>
            </Box>
          </Box>

          <Grid container spacing={2.25}>
            <Grid item xs={12} sm={7}>
              <TextField
                fullWidth
                required
                label="Company or shop name"
                placeholder="Radhya Construction"
                error={Boolean(formState.errors.company_name)}
                helperText={
                  formState.errors.company_name?.message ||
                  "This name appears prominently on invoices."
                }
                InputProps={readOnlyProps}
                {...register("company_name", {
                  required: "Enter the company or shop name",
                  minLength: { value: 2, message: "Enter at least 2 characters" },
                  maxLength: { value: 160, message: "Use 160 characters or fewer" },
                })}
              />
            </Grid>
            <Grid item xs={12} sm={5}>
              <TextField
                fullWidth
                label="Phone number"
                placeholder="+91 98765 43210"
                error={Boolean(formState.errors.company_phone)}
                helperText={
                  formState.errors.company_phone?.message ||
                  "Optional. Include area or country code when needed."
                }
                InputProps={readOnlyProps}
                {...register("company_phone", {
                  validate: (value) =>
                    !value.trim() ||
                    PHONE_PATTERN.test(value.trim()) ||
                    "Enter a valid phone number",
                })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                required
                multiline
                minRows={2}
                label="Shop address"
                placeholder="Street, area, city, district and PIN code"
                error={Boolean(formState.errors.company_address)}
                helperText={
                  formState.errors.company_address?.message ||
                  "Use the complete address that should appear on the PDF."
                }
                InputProps={readOnlyProps}
                {...register("company_address", {
                  required: "Enter the shop address",
                  minLength: { value: 5, message: "Enter a complete address" },
                  maxLength: { value: 500, message: "Use 500 characters or fewer" },
                })}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Box className="settings-section-title">
            <Box className="dialog-icon">
              <Settings2 size={20} />
            </Box>
            <Box>
              <Typography variant="h6">GST and legal details</Typography>
              <Typography variant="body2" color="text.secondary">
                Optional tax registration and invoice jurisdiction information
              </Typography>
            </Box>
          </Box>

          <Grid container spacing={2.25}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Company GSTIN"
                placeholder="27ABCDE1234F1Z5"
                error={Boolean(formState.errors.company_gstin)}
                helperText={
                  formState.errors.company_gstin?.message ||
                  "Optional. Must be a valid 15-character GSTIN when provided."
                }
                inputProps={{ maxLength: 15 }}
                InputProps={readOnlyProps}
                {...register("company_gstin", {
                  validate: (value) =>
                    !value.trim() ||
                    GSTIN_PATTERN.test(value.trim().toUpperCase()) ||
                    "Enter a valid 15-character GSTIN",
                })}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="State"
                placeholder="Maharashtra"
                helperText="Used to determine intra-state or inter-state GST."
                InputProps={readOnlyProps}
                {...register("company_state", {
                  maxLength: { value: 100, message: "Use 100 characters or fewer" },
                })}
              />
            </Grid>
            <Grid item xs={12} sm={2}>
              <TextField
                fullWidth
                label="State code"
                placeholder="27"
                error={Boolean(formState.errors.company_gst_state_code)}
                helperText={formState.errors.company_gst_state_code?.message || "Two digits"}
                inputProps={{ maxLength: 2, inputMode: "numeric" }}
                InputProps={readOnlyProps}
                {...register("company_gst_state_code", {
                  validate: (value) =>
                    !value.trim() || /^\d{2}$/.test(value.trim()) || "Use two digits",
                })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Jurisdiction"
                placeholder="Ahmednagar"
                helperText="Shown in the invoice terms, for example “Subject to Ahmednagar jurisdiction”."
                InputProps={readOnlyProps}
                {...register("company_jurisdiction", {
                  maxLength: { value: 160, message: "Use 160 characters or fewer" },
                })}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Box className="settings-section-title">
            <Box className="dialog-icon">
              <Landmark size={20} />
            </Box>
            <Box>
              <Typography variant="h6">Bank details</Typography>
              <Typography variant="body2" color="text.secondary">
                Optional payment information printed on invoices
              </Typography>
            </Box>
          </Box>

          <Grid container spacing={2.25}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Bank name"
                placeholder="Bank name"
                InputProps={readOnlyProps}
                {...register("company_bank_name", {
                  maxLength: { value: 160, message: "Use 160 characters or fewer" },
                })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Branch"
                placeholder="Branch name"
                InputProps={readOnlyProps}
                {...register("company_bank_branch", {
                  maxLength: { value: 160, message: "Use 160 characters or fewer" },
                })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Account number"
                placeholder="Account number"
                error={Boolean(formState.errors.company_bank_account)}
                helperText={formState.errors.company_bank_account?.message}
                InputProps={readOnlyProps}
                {...register("company_bank_account", {
                  validate: (value) =>
                    !value.trim() ||
                    /^[A-Z0-9-]{5,34}$/i.test(value.trim()) ||
                    "Enter a valid account number",
                })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="IFSC code"
                placeholder="ABCD0123456"
                error={Boolean(formState.errors.company_bank_ifsc)}
                helperText={
                  formState.errors.company_bank_ifsc?.message ||
                  "Optional 11-character bank branch code."
                }
                inputProps={{ maxLength: 11 }}
                InputProps={readOnlyProps}
                {...register("company_bank_ifsc", {
                  validate: (value) =>
                    !value.trim() ||
                    IFSC_PATTERN.test(value.trim().toUpperCase()) ||
                    "Enter a valid IFSC code",
                })}
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {canEdit ? (
        <Box className="settings-save-row">
          <Typography variant="body2" color="text.secondary">
            Changes apply to newly generated documents.
          </Typography>
          <Button
            type="submit"
            variant="contained"
            startIcon={<Save size={18} />}
            disabled={formState.isSubmitting || Boolean(loadError)}
          >
            {formState.isSubmitting ? "Saving..." : "Save company details"}
          </Button>
        </Box>
      ) : null}

      {canManageUsers ? (
        <Card className="settings-card">
          <CardContent>
            <Box className="settings-section-title settings-section-title--actions">
              <Box className="settings-section-title__copy">
                <Box className="dialog-icon">
                  <Users size={20} />
                </Box>
                <Box>
                  <Typography variant="h6">User management</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Add people who can sign in and choose what they are allowed to manage
                  </Typography>
                </Box>
              </Box>
              <Button
                type="button"
                variant="contained"
                startIcon={<UserPlus size={18} />}
                onClick={openUserDialog}
                disabled={usersLoading || availableRoles.length === 0}
              >
                Add user
              </Button>
            </Box>

            {usersError ? (
              <Alert
                severity="error"
                sx={{ mb: 2 }}
                action={
                  <Button color="inherit" size="small" onClick={loadUsers}>
                    Retry
                  </Button>
                }
              >
                {usersError}
              </Alert>
            ) : null}
            {userMessage ? (
              <Alert sx={{ mb: 2 }} onClose={() => setUserMessage("")}>
                {userMessage}
              </Alert>
            ) : null}

            {usersLoading ? (
              <Stack spacing={1}>
                <Skeleton variant="rounded" height={68} />
                <Skeleton variant="rounded" height={68} />
              </Stack>
            ) : managedUsers.length ? (
              <Box className="user-account-list">
                {managedUsers.map((account) => (
                  <Box className="user-account-row" key={account.id}>
                    <Box className="user-account-identity">
                      <Box className="user-account-avatar">
                        {account.full_name
                          .split(/\s+/)
                          .map((part) => part[0])
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()}
                      </Box>
                      <Box>
                        <Typography fontWeight={800}>
                          {account.full_name}
                          {account.id === user?.id ? (
                            <Typography
                              component="span"
                              variant="caption"
                              color="text.secondary"
                              sx={{ ml: 1 }}
                            >
                              You
                            </Typography>
                          ) : null}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          @{account.username}
                        </Typography>
                      </Box>
                    </Box>
                    <Box className="user-account-roles">
                      {account.roles.map((role) => (
                        <Chip
                          key={role.id}
                          size="small"
                          icon={<ShieldCheck size={14} />}
                          label={role.name}
                          color={role.name === "Admin" ? "primary" : "default"}
                          variant={role.name === "Admin" ? "filled" : "outlined"}
                        />
                      ))}
                      <Chip
                        size="small"
                        label={account.is_active ? "Active" : "Inactive"}
                        color={account.is_active ? "success" : "default"}
                        variant="outlined"
                      />
                    </Box>
                  </Box>
                ))}
              </Box>
            ) : (
              <Alert severity="info">No user accounts have been added yet.</Alert>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Dialog
        open={userDialogOpen}
        onClose={userSaving ? undefined : () => setUserDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <Box component="form" onSubmit={addUser}>
          <DialogTitle>
            <Box className="settings-dialog-title">
              <Box className="dialog-icon">
                <UserPlus size={20} />
              </Box>
              <Box>
                <Typography variant="h6">Add user</Typography>
                <Typography variant="body2" color="text.secondary">
                  Create a separate sign-in account for a staff member
                </Typography>
              </Box>
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            {userFormError ? (
              <Alert severity="error" sx={{ mb: 2 }}>
                {userFormError}
              </Alert>
            ) : null}
            <Stack spacing={2.25} sx={{ pt: 0.5 }}>
              <TextField
                label="Full name"
                value={userForm.full_name}
                onChange={(event) => setUserField("full_name", event.target.value)}
                inputProps={{ minLength: 2, maxLength: 150 }}
                autoFocus
                required
              />
              <TextField
                label="Username"
                value={userForm.username}
                onChange={(event) => setUserField("username", event.target.value)}
                helperText="Use letters, numbers, dots, underscores or hyphens."
                inputProps={{
                  minLength: 3,
                  maxLength: 80,
                  pattern: "[A-Za-z0-9._-]+",
                }}
                autoComplete="off"
                required
              />
              <TextField
                select
                label="Access role"
                value={userForm.role_name}
                onChange={(event) => setUserField("role_name", event.target.value)}
                helperText={
                  roleDescriptions[userForm.role_name] || "Choose the account permissions."
                }
                required
              >
                {availableRoles.map((role) => (
                  <MenuItem key={role.id} value={role.name}>
                    {role.name}
                  </MenuItem>
                ))}
              </TextField>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    type="password"
                    label="Password"
                    value={userForm.password}
                    onChange={(event) => setUserField("password", event.target.value)}
                    inputProps={{ minLength: 8, maxLength: 128 }}
                    autoComplete="new-password"
                    helperText="At least 8 characters"
                    required
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    type="password"
                    label="Confirm password"
                    value={userForm.confirm_password}
                    onChange={(event) =>
                      setUserField("confirm_password", event.target.value)
                    }
                    inputProps={{ minLength: 8, maxLength: 128 }}
                    autoComplete="new-password"
                    required
                  />
                </Grid>
              </Grid>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, py: 2 }}>
            <Button
              type="button"
              color="inherit"
              onClick={() => setUserDialogOpen(false)}
              disabled={userSaving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<UserPlus size={18} />}
              disabled={userSaving || availableRoles.length === 0}
            >
              {userSaving ? "Adding..." : "Add user"}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Stack>
  );
}
