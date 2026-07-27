import { useCallback, useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
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
import {
  Boxes,
  PackagePlus,
  Pencil,
  Plus,
  Search,
  Trash2,
  Warehouse,
} from "lucide-react";

import api from "../api/client.js";
import Currency from "../components/Currency.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const defaults = {
  name: "",
  hsn_code: "25171090",
  unit: "TON",
  selling_rate: 0,
  purchase_rate: 0,
  gst_percentage: 5,
  stock_quantity: 0,
  minimum_stock: 0,
};

const MATERIAL_UNITS = ["TON", "BRASS", "CFT", "KG", "CUM", "NOS"];

function errorMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
}

function materialFormValues(material) {
  if (!material) return defaults;
  return {
    name: material.name || "",
    hsn_code: material.hsn_code || "",
    unit: material.unit || "TON",
    selling_rate: Number(material.selling_rate || 0),
    purchase_rate: Number(material.purchase_rate || 0),
    gst_percentage: Number(material.gst_percentage || 0),
    stock_quantity: Number(material.stock_quantity || 0),
    minimum_stock: Number(material.minimum_stock || 0),
  };
}

export default function MaterialsPage() {
  const { user } = useAuth();
  const [materials, setMaterials] = useState([]);
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingMaterial, setEditingMaterial] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [stockTarget, setStockTarget] = useState(null);
  const [stockForm, setStockForm] = useState({
    movement_type: "IN",
    quantity: "",
    reference_number: "",
  });
  const [stockSaving, setStockSaving] = useState(false);

  const { control, register, handleSubmit, reset, formState } = useForm({
    defaultValues: defaults,
  });
  const roleNames = new Set((user?.roles || []).map((role) => role.name));
  const canManage = roleNames.has("Admin") || roleNames.has("Manager");
  const canUpdateStock = canManage || roleNames.has("Operator");

  const loadMaterials = useCallback(async () => {
    try {
      setError("");
      const { data } = await api.get("/materials");
      setMaterials(data);
    } catch (requestError) {
      setError(errorMessage(requestError, "Unable to load materials"));
    }
  }, []);

  useEffect(() => {
    loadMaterials();
  }, [loadMaterials]);

  const visibleMaterials = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return materials;
    return materials.filter((material) =>
      [material.name, material.hsn_code, material.unit]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    );
  }, [materials, search]);

  function openCreate() {
    setError("");
    setEditingMaterial(null);
    reset(defaults);
    setFormOpen(true);
  }

  function openEdit(material) {
    setError("");
    setEditingMaterial(material);
    reset(materialFormValues(material));
    setFormOpen(true);
  }

  async function saveMaterial(values) {
    setError("");
    const payload = {
      name: values.name.trim(),
      hsn_code: values.hsn_code?.trim() || null,
      unit: values.unit.trim().toUpperCase(),
      selling_rate: Number(values.selling_rate || 0),
      purchase_rate: Number(values.purchase_rate || 0),
      gst_percentage: Number(values.gst_percentage || 0),
      minimum_stock: Number(values.minimum_stock || 0),
    };
    if (!editingMaterial) payload.stock_quantity = Number(values.stock_quantity || 0);

    try {
      if (editingMaterial) {
        await api.put(`/materials/${editingMaterial.id}`, payload);
        setMessage(`${payload.name} updated`);
      } else {
        await api.post("/materials", payload);
        setMessage(`${payload.name} added`);
      }
      setFormOpen(false);
      setEditingMaterial(null);
      reset(defaults);
      await loadMaterials();
    } catch (requestError) {
      setError(errorMessage(requestError, "Unable to save material"));
    }
  }

  async function deleteMaterial() {
    if (!deleteTarget) return;
    try {
      setError("");
      await api.delete(`/materials/${deleteTarget.id}`);
      setMessage(`${deleteTarget.name} deleted`);
      setDeleteTarget(null);
      await loadMaterials();
    } catch (requestError) {
      setError(errorMessage(requestError, "Unable to delete material"));
    }
  }

  function openStock(material) {
    setError("");
    setStockTarget(material);
    setStockForm({ movement_type: "IN", quantity: "", reference_number: "" });
  }

  async function updateStock(event) {
    event.preventDefault();
    if (!stockTarget || Number(stockForm.quantity) <= 0) return;
    setStockSaving(true);
    setError("");
    try {
      await api.post(`/materials/${stockTarget.id}/stock`, {
        movement_type: stockForm.movement_type,
        quantity: Number(stockForm.quantity),
        reference_number: stockForm.reference_number.trim() || null,
      });
      setMessage(
        `${stockTarget.name} stock ${
          stockForm.movement_type === "IN" ? "increased" : "reduced"
        }`
      );
      setStockTarget(null);
      await loadMaterials();
    } catch (requestError) {
      setError(errorMessage(requestError, "Unable to update stock"));
    } finally {
      setStockSaving(false);
    }
  }

  return (
    <Stack spacing={3}>
      <Box className="page-header">
        <Box>
          <Typography variant="h4">Materials</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage products, prices, tax and available stock
          </Typography>
        </Box>
        <Box className="page-actions">
          <TextField
            size="small"
            placeholder="Search materials"
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
          {canManage ? (
            <Button variant="contained" startIcon={<Plus size={18} />} onClick={openCreate}>
              Add material
            </Button>
          ) : null}
        </Box>
      </Box>

      {message ? <Alert onClose={() => setMessage("")}>{message}</Alert> : null}
      {error ? (
        <Alert severity="error" onClose={() => setError("")}>
          {error}
        </Alert>
      ) : null}

      <Card>
        <Box sx={{ px: 2.75, py: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="h6">Material list</Typography>
          <Typography variant="body2" color="text.secondary">
            {visibleMaterials.length} {visibleMaterials.length === 1 ? "material" : "materials"}
          </Typography>
        </Box>
        {visibleMaterials.length ? (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Material</TableCell>
                  <TableCell>HSN/SAC</TableCell>
                  <TableCell>Unit</TableCell>
                  <TableCell align="right">Selling rate</TableCell>
                  <TableCell align="right">GST</TableCell>
                  <TableCell align="right">Stock</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {visibleMaterials.map((material) => {
                  const stock = Number(material.stock_quantity || 0);
                  const minimum = Number(material.minimum_stock || 0);
                  const isLow = minimum > 0 && stock <= minimum;
                  return (
                    <TableRow key={material.id} hover>
                      <TableCell>
                        <Typography fontWeight={750}>{material.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Purchase: <Currency value={material.purchase_rate} />
                        </Typography>
                      </TableCell>
                      <TableCell>{material.hsn_code || "—"}</TableCell>
                      <TableCell>{material.unit}</TableCell>
                      <TableCell align="right">
                        <Currency value={material.selling_rate} />
                      </TableCell>
                      <TableCell align="right">{Number(material.gst_percentage)}%</TableCell>
                      <TableCell align="right">
                        <Typography fontWeight={750}>
                          {stock.toLocaleString("en-IN")} {material.unit}
                        </Typography>
                        {minimum > 0 ? (
                          <Typography variant="caption" color="text.secondary">
                            Minimum {minimum.toLocaleString("en-IN")}
                          </Typography>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          color={isLow ? "warning" : "success"}
                          variant={isLow ? "filled" : "outlined"}
                          label={isLow ? "Low stock" : "In stock"}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Box className="table-row-actions">
                          {canUpdateStock ? (
                            <Tooltip title="Update stock">
                              <IconButton
                                size="small"
                                aria-label={`Update stock for ${material.name}`}
                                onClick={() => openStock(material)}
                              >
                                <Warehouse size={18} />
                              </IconButton>
                            </Tooltip>
                          ) : null}
                          {canManage ? (
                            <>
                              <Tooltip title="Edit material">
                                <IconButton
                                  size="small"
                                  aria-label={`Edit ${material.name}`}
                                  onClick={() => openEdit(material)}
                                >
                                  <Pencil size={17} />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Delete material">
                                <IconButton
                                  size="small"
                                  color="error"
                                  aria-label={`Delete ${material.name}`}
                                  onClick={() => {
                                    setError("");
                                    setDeleteTarget(material);
                                  }}
                                >
                                  <Trash2 size={17} />
                                </IconButton>
                              </Tooltip>
                            </>
                          ) : null}
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
              <Boxes size={34} />
              <Typography variant="h6">
                {search ? "No matching materials" : "No materials yet"}
              </Typography>
              <Typography variant="body2">
                {search
                  ? "Try another name, HSN code or unit."
                  : "Add your first material to start creating invoices."}
              </Typography>
            </Box>
          </Box>
        )}
      </Card>

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <Box component="form" onSubmit={handleSubmit(saveMaterial)}>
          <DialogTitle>{editingMaterial ? "Edit material" : "Add material"}</DialogTitle>
          <DialogContent dividers>
            <Stack spacing={2.25}>
              {error ? <Alert severity="error">{error}</Alert> : null}
              <TextField
                autoFocus
                label="Material name"
                error={Boolean(formState.errors.name)}
                helperText={formState.errors.name ? "Enter at least 2 characters" : ""}
                {...register("name", { required: true, minLength: 2 })}
              />
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Controller
                    name="unit"
                    control={control}
                    rules={{
                      required: "Select or enter a unit",
                      validate: (value) =>
                        Boolean(value?.trim()) || "Select or enter a unit",
                    }}
                    render={({ field, fieldState }) => (
                      <Autocomplete
                        freeSolo
                        autoHighlight
                        clearOnBlur={false}
                        options={MATERIAL_UNITS}
                        value={field.value || null}
                        inputValue={field.value || ""}
                        onChange={(_, value) => field.onChange(value || "")}
                        onInputChange={(_, value) => field.onChange(value)}
                        onBlur={field.onBlur}
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            fullWidth
                            required
                            label="Unit"
                            placeholder="Search or type a unit"
                            error={Boolean(fieldState.error)}
                            helperText={fieldState.error?.message}
                            inputRef={field.ref}
                          />
                        )}
                      />
                    )}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField fullWidth label="HSN/SAC code" {...register("hsn_code")} />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Selling rate"
                    type="number"
                    inputProps={{ min: 0, step: "0.01" }}
                    {...register("selling_rate")}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="GST percentage"
                    type="number"
                    inputProps={{ min: 0, max: 100, step: "0.01" }}
                    {...register("gst_percentage")}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Purchase rate"
                    type="number"
                    inputProps={{ min: 0, step: "0.01" }}
                    {...register("purchase_rate")}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Low-stock warning at"
                    type="number"
                    inputProps={{ min: 0, step: "0.001" }}
                    {...register("minimum_stock")}
                  />
                </Grid>
                {!editingMaterial ? (
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Opening stock"
                      type="number"
                      helperText="You can update stock separately later."
                      inputProps={{ min: 0, step: "0.001" }}
                      {...register("stock_quantity")}
                    />
                  </Grid>
                ) : null}
              </Grid>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={editingMaterial ? <Pencil size={17} /> : <PackagePlus size={18} />}
              disabled={formState.isSubmitting}
            >
              {formState.isSubmitting
                ? "Saving..."
                : editingMaterial
                  ? "Save changes"
                  : "Add material"}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>

      <Dialog
        open={Boolean(stockTarget)}
        onClose={() => setStockTarget(null)}
        fullWidth
        maxWidth="xs"
      >
        <Box component="form" onSubmit={updateStock}>
          <DialogTitle>Update stock</DialogTitle>
          <DialogContent dividers>
            {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
            <Typography fontWeight={750}>{stockTarget?.name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Available: {Number(stockTarget?.stock_quantity || 0).toLocaleString("en-IN")}{" "}
              {stockTarget?.unit}
            </Typography>
            <Stack spacing={2}>
              <TextField
                select
                label="Action"
                value={stockForm.movement_type}
                onChange={(event) =>
                  setStockForm((current) => ({
                    ...current,
                    movement_type: event.target.value,
                  }))
                }
                SelectProps={{ native: true }}
              >
                <option value="IN">Add stock</option>
                <option value="OUT">Remove stock</option>
              </TextField>
              <TextField
                autoFocus
                label="Quantity"
                type="number"
                value={stockForm.quantity}
                onChange={(event) =>
                  setStockForm((current) => ({ ...current, quantity: event.target.value }))
                }
                inputProps={{ min: 0.001, step: "0.001" }}
                required
              />
              <TextField
                label="Reference (optional)"
                placeholder="Challan or note number"
                value={stockForm.reference_number}
                onChange={(event) =>
                  setStockForm((current) => ({
                    ...current,
                    reference_number: event.target.value,
                  }))
                }
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setStockTarget(null)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={stockSaving}>
              {stockSaving ? "Updating..." : "Update stock"}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>

      <Dialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete material?</DialogTitle>
        <DialogContent>
          {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
          <Typography>
            <strong>{deleteTarget?.name}</strong> will no longer appear in new invoices.
            Existing invoices will stay unchanged.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDeleteTarget(null)}>Keep material</Button>
          <Button color="error" variant="contained" onClick={deleteMaterial}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
