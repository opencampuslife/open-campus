import type { AuthProvider } from "@refinedev/core";

function canBootstrapDevSession(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1";
}

function bootstrapDevSession(): void {
  if (!canBootstrapDevSession()) return;
  if (!localStorage.getItem("admin_token")) {
    localStorage.setItem("admin_token", "dev-admin-session");
  }
  if (!localStorage.getItem("admin_role")) {
    localStorage.setItem("admin_role", "admin");
  }
  if (!localStorage.getItem("admin_user_id")) {
    localStorage.setItem("admin_user_id", "admin");
  }
  if (!localStorage.getItem("admin_campus")) {
    localStorage.setItem("admin_campus", "all");
  }
  if (!localStorage.getItem("admin_identity")) {
    localStorage.setItem(
      "admin_identity",
      JSON.stringify({
        id: "admin",
        role: "admin",
        campus: "all",
      })
    );
  }
}

export const authProvider: AuthProvider = {
  login: async ({ token }: { token: string }) => {
    localStorage.setItem("admin_token", token);
    localStorage.setItem("admin_role", "admin");
    localStorage.setItem("admin_user_id", "admin");
    localStorage.setItem("admin_campus", "all");
    return { success: true, redirectTo: "/admin/dashboard" };
  },

  logout: async () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_role");
    localStorage.removeItem("admin_user_id");
    localStorage.removeItem("admin_campus");
    localStorage.removeItem("admin_identity");
    return { success: true, redirectTo: "/" };
  },

  check: async () => {
    bootstrapDevSession();
    const token = localStorage.getItem("admin_token");
    if (token) {
      return { authenticated: true };
    }
    return { authenticated: false, redirectTo: "/" };
  },

  getIdentity: async () => {
    bootstrapDevSession();
    const token = localStorage.getItem("admin_token");
    if (!token) return null;
    try {
      const stored = localStorage.getItem("admin_identity");
      if (stored) return JSON.parse(stored);
    } catch {}
    return {
      id: "admin",
      role: localStorage.getItem("admin_role") || "admin",
      campus: "all",
    };
  },

  getPermissions: async () => {
    bootstrapDevSession();
    return localStorage.getItem("admin_role") || "guest";
  },

  onError: async (error) => {
    if (error.status === 401 || error.status === 403) {
      localStorage.removeItem("admin_token");
      localStorage.removeItem("admin_role");
      localStorage.removeItem("admin_user_id");
      localStorage.removeItem("admin_campus");
      localStorage.removeItem("admin_identity");
      return { logout: true, redirectTo: "/" };
    }
    return { error };
  },
};
