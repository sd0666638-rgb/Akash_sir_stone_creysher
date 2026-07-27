import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  BarChart3,
  Boxes,
  FileText,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ReceiptIndianRupee,
  Settings,
  Users,
} from "lucide-react";

import api from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const expandedDrawerWidth = 248;
const collapsedDrawerWidth = 80;

const navItems = [
  { to: "/", label: "Dashboard", icon: BarChart3 },
  { to: "/customers", label: "Customers", icon: Users },
  { to: "/materials", label: "Materials", icon: Boxes },
  { to: "/invoices", label: "Invoices", icon: FileText },
  { to: "/payments", label: "Payments", icon: ReceiptIndianRupee },
  { to: "/reports", label: "Reports", icon: BarChart3 },
];

function DrawerContent({ onNavigate, collapsed = false, companyName }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <Box className="drawer-content">
      <Box className={`brand-block${collapsed ? " brand-block--collapsed" : ""}`}>
        <Box className="brand-mark">
          <Boxes size={22} />
        </Box>
        {!collapsed ? (
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle1" fontWeight={800} color="white" noWrap>
              {companyName}
            </Typography>
            <Typography variant="caption" sx={{ color: "rgba(220, 235, 230, 0.72)" }}>
              Stone Crusher ERP
            </Typography>
          </Box>
        ) : null}
      </Box>
      <Divider />
      <List className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon;
          const button = (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.to === "/"}
              onClick={onNavigate}
              sx={{ justifyContent: collapsed ? "center" : "flex-start" }}
            >
              <ListItemIcon
                sx={{
                  minWidth: collapsed ? 0 : 40,
                  justifyContent: "center",
                }}
              >
                <Icon size={20} />
              </ListItemIcon>
              {!collapsed ? <ListItemText primary={item.label} /> : null}
            </ListItemButton>
          );
          return collapsed ? (
            <Tooltip key={item.to} title={item.label} placement="right" arrow>
              {button}
            </Tooltip>
          ) : (
            button
          );
        })}
      </List>
      <Box sx={{ flexGrow: 1 }} />
      <Divider />
      <Box sx={{ p: collapsed ? 1.25 : 2, textAlign: "center" }}>
        {!collapsed ? (
          <>
            <Typography
              variant="caption"
              sx={{ display: "block", mb: 1.25, color: "#a9c7bf" }}
            >
              Signed in as {user?.full_name || "Operator"}
            </Typography>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<LogOut size={18} />}
              onClick={handleLogout}
              sx={{
                color: "#e3efec",
                borderColor: "rgba(255,255,255,0.2)",
                "&:hover": { borderColor: "rgba(255,255,255,0.36)" },
              }}
            >
              Sign out
            </Button>
          </>
        ) : (
          <Tooltip title="Sign out" placement="right" arrow>
            <IconButton
              aria-label="Sign out"
              onClick={handleLogout}
              sx={{
                color: "#e3efec",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              <LogOut size={18} />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [companyName, setCompanyName] = useState("Radhya Construction");
  const [collapsed, setCollapsed] = useState(
    () => window.localStorage.getItem("stone_sidebar_collapsed") === "true"
  );
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const activeItem = location.pathname.startsWith("/settings")
    ? { label: "Settings" }
    : navItems.find(
        (item) => item.to !== "/" && location.pathname.startsWith(item.to)
      ) || navItems[0];
  const initials = (user?.full_name || "Operator")
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const desktopDrawerWidth = collapsed ? collapsedDrawerWidth : expandedDrawerWidth;

  useEffect(() => {
    let ignore = false;

    async function loadCompanyName() {
      try {
        const { data } = await api.get("/settings/company");
        if (!ignore && data.company_name?.trim()) {
          setCompanyName(data.company_name.trim());
        }
      } catch {
        // The navigation remains usable with the fallback name.
      }
    }

    function handleSettingsUpdated(event) {
      const nextName = event.detail?.companyName?.trim();
      if (nextName) setCompanyName(nextName);
    }

    loadCompanyName();
    window.addEventListener("company-settings-updated", handleSettingsUpdated);
    return () => {
      ignore = true;
      window.removeEventListener("company-settings-updated", handleSettingsUpdated);
    };
  }, []);

  function toggleSidebar() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("stone_sidebar_collapsed", String(next));
      return next;
    });
  }

  return (
    <Box className="app-shell">
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        className="topbar"
        sx={{
          width: { md: `calc(100% - ${desktopDrawerWidth}px)` },
          ml: { md: `${desktopDrawerWidth}px` },
          transition: (theme) =>
            theme.transitions.create(["width", "margin"], {
              duration: theme.transitions.duration.shorter,
            }),
        }}
      >
        <Toolbar>
          <IconButton
            edge="start"
            onClick={() => setMobileOpen(true)}
            sx={{ mr: 2, display: { md: "none" } }}
            aria-label="Open navigation"
          >
            <Menu size={22} />
          </IconButton>
          <Tooltip title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <IconButton
              edge="start"
              onClick={toggleSidebar}
              sx={{ mr: 1.5, display: { xs: "none", md: "inline-flex" } }}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <PanelLeftOpen size={21} /> : <PanelLeftClose size={21} />}
            </IconButton>
          </Tooltip>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle1" fontWeight={800} noWrap>
              {activeItem.label}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>
              Billing, sales and payments
            </Typography>
          </Box>
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title="Company settings">
            <IconButton
              aria-label="Open company settings"
              aria-current={location.pathname.startsWith("/settings") ? "page" : undefined}
              onClick={() => navigate("/settings")}
              sx={{
                mr: 1,
                color: location.pathname.startsWith("/settings")
                  ? "primary.main"
                  : "text.secondary",
                bgcolor: location.pathname.startsWith("/settings")
                  ? "primary.light"
                  : "transparent",
              }}
            >
              <Settings size={20} />
            </IconButton>
          </Tooltip>
          <Avatar
            sx={{
              width: 36,
              height: 36,
              bgcolor: "primary.light",
              color: "primary.dark",
              fontSize: 13,
              fontWeight: 800,
            }}
          >
            {initials}
          </Avatar>
        </Toolbar>
      </AppBar>

      <Box
        component="nav"
        sx={{ width: { md: desktopDrawerWidth }, flexShrink: { md: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: "block", md: "none" },
            "& .MuiDrawer-paper": { width: expandedDrawerWidth },
          }}
        >
          <DrawerContent
            companyName={companyName}
            onNavigate={() => setMobileOpen(false)}
          />
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": {
              width: desktopDrawerWidth,
              boxSizing: "border-box",
              overflowX: "hidden",
              transition: (theme) =>
                theme.transitions.create("width", {
                  duration: theme.transitions.duration.shorter,
                }),
            },
          }}
          open
        >
          <DrawerContent collapsed={collapsed} companyName={companyName} />
        </Drawer>
      </Box>

      <Box component="main" className="main-panel">
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
