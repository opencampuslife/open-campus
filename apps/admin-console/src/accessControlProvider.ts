import type { AccessControlProvider } from "@refinedev/core";

const adminResources = ["knowledge", "ingestion", "graph", "audit", "staging_docs", "audit_logs", "sources", "ingestion_runs", "graph_runs"];
const salesResources = ["crm_leads", "sales_sessions"];

function getResourceName(resource: unknown): string {
  if (typeof resource === "string") return resource;
  if (resource && typeof resource === "object" && "name" in resource) {
    return typeof resource.name === "string" ? resource.name : "";
  }
  return "";
}

export const accessControlProvider: AccessControlProvider = {
  can: async ({ resource, action }) => {
    const role = (localStorage.getItem("admin_role") || "guest") as string;
    const resourceName = getResourceName(resource);

    if (role === "admin") {
      return { can: true };
    }

    if (role === "sales") {
      if (!salesResources.includes(resourceName)) {
        return { can: false, reason: "Access denied. Sales role cannot access this resource." };
      }
      if (!["list", "edit", "show"].includes(action)) {
        return { can: false, reason: "Access denied. Cannot modify this resource." };
      }
      return { can: true };
    }

    return { can: false, reason: "Unauthorized. Admin access required." };
  },
};
