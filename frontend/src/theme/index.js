import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#176b5b",
      dark: "#0f4e43",
      light: "#dcefe9",
      contrastText: "#ffffff",
    },
    secondary: { main: "#d46b3b" },
    success: { main: "#23815f" },
    warning: { main: "#b66a12" },
    error: { main: "#c13d35" },
    info: { main: "#3478b8" },
    background: {
      default: "#f6f8f7",
      paper: "#ffffff",
    },
    text: {
      primary: "#172622",
      secondary: "#62706c",
    },
    divider: "#e3e9e7",
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: [
      "Inter",
      "Segoe UI",
      "Roboto",
      "Arial",
      "sans-serif",
    ].join(","),
    h4: { fontWeight: 750, fontSize: "1.75rem", letterSpacing: "-0.025em" },
    h5: { fontWeight: 750, letterSpacing: "-0.02em" },
    h6: { fontWeight: 750, letterSpacing: "-0.012em" },
    button: { textTransform: "none", fontWeight: 700, letterSpacing: 0 },
    overline: { fontWeight: 750, letterSpacing: "0.08em" },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          minHeight: 40,
          borderRadius: 10,
          paddingInline: 16,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: "1px solid #e3e9e7",
          boxShadow: "0 8px 28px rgba(30, 55, 48, 0.055)",
          backgroundImage: "none",
        },
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          padding: 22,
          "&:last-child": { paddingBottom: 22 },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          backgroundColor: "#ffffff",
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontSize: "0.75rem",
          fontWeight: 750,
          letterSpacing: "0.035em",
          textTransform: "uppercase",
          color: "#50605b",
          backgroundColor: "#f1f5f3",
        },
        root: {
          borderColor: "#e7ecea",
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 16,
          boxShadow: "0 24px 70px rgba(16, 48, 40, 0.18)",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 700,
        },
      },
    },
  },
});

export default theme;
