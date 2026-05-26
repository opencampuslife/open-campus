import { Refine } from "@refinedev/core";
import routerBindings from "@refinedev/react-router-v6";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { dataProvider } from "../dataProvider";
import { authProvider } from "../authProvider";
import { accessControlProvider } from "../accessControlProvider";
import { AdminLayout } from "./AdminLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { KnowledgeStagingPage } from "../pages/KnowledgeStagingPage";
import { KnowledgeGraphPage } from "../pages/KnowledgeGraphPage";
import { CrmLeadsPage } from "../pages/CrmLeadsPage";
import { SalesSessionsPage } from "../pages/SalesSessionsPage";
import { AuditPage } from "../pages/AuditPage";
import { CampusLeavesPage } from "../pages/CampusLeavesPage";
import { CampusMealsPage } from "../pages/CampusMealsPage";
import { CampusRepairsPage } from "../pages/CampusRepairsPage";
import { CampusDailyReportPage } from "../pages/CampusDailyReportPage";
import { CampusModulesPage } from "../pages/CampusModulesPage";

export function App() {
  return (
    <BrowserRouter>
      <Refine
        routerProvider={routerBindings}
        dataProvider={dataProvider}
        authProvider={authProvider}
        accessControlProvider={accessControlProvider}
        resources={[
          { name: "staging_docs", list: "/admin/knowledge/staging" },
          { name: "crm_leads", list: "/admin/crm/leads" },
          { name: "sales_sessions", list: "/admin/sales/sessions" },
          { name: "audit_logs", list: "/admin/audit" },
          { name: "campus_leaves", list: "/admin/campus/leaves" },
          { name: "campus_repairs", list: "/admin/campus/repairs" },
          { name: "campus_modules", list: "/admin/campus/modules" },
        ]}
        options={{
          disableTelemetry: true,
          reactQuery: {
            clientConfig: {
              defaultOptions: {
                queries: {
                  retry: 1,
                  staleTime: 30_000,
                  refetchOnWindowFocus: false,
                },
              },
            },
          },
        }}
      >
        <Routes>
          <Route path="/" element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="knowledge/staging" element={<KnowledgeStagingPage />} />
            <Route path="knowledge/graph" element={<KnowledgeGraphPage />} />
            <Route path="campus/leaves" element={<CampusLeavesPage />} />
            <Route path="campus/modules" element={<CampusModulesPage />} />
            <Route path="campus/meals" element={<CampusMealsPage />} />
            <Route path="campus/repairs" element={<CampusRepairsPage />} />
            <Route path="campus/reports/daily" element={<CampusDailyReportPage />} />
            <Route path="crm/leads" element={<CrmLeadsPage />} />
            <Route path="sales/sessions" element={<SalesSessionsPage />} />
            <Route path="audit" element={<AuditPage />} />
          </Route>
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}
