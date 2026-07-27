import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { Boxes, LogIn } from "lucide-react";

import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const [error, setError] = useState("");
  const { register, handleSubmit, formState } = useForm({
    defaultValues: { username: "", password: "" },
  });

  if (isAuthenticated) return <Navigate to="/" replace />;

  async function onSubmit(values) {
    setError("");
    try {
      await login(values.username, values.password);
    } catch {
      setError("Invalid username or password");
    }
  }

  return (
    <Box className="login-screen">
      <Paper className="login-panel" elevation={0}>
        <Box className="login-brand-mark">
          <Boxes size={25} />
        </Box>
        <Typography variant="h4">Radhya Construction</Typography>
        <Typography variant="body1" color="text.secondary">
          Stone crusher billing and payments
        </Typography>
        <Box component="form" onSubmit={handleSubmit(onSubmit)} sx={{ mt: 3 }}>
          <Stack spacing={2}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            <TextField label="Username" {...register("username", { required: true })} />
            <TextField
              label="Password"
              type="password"
              {...register("password", { required: true })}
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              startIcon={<LogIn size={18} />}
              disabled={formState.isSubmitting}
            >
              Sign in
            </Button>
          </Stack>
        </Box>
      </Paper>
    </Box>
  );
}
