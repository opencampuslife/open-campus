import { useList, useCustom } from "@refinedev/core";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import {
  FileText,
  Clock,
  Users,
  Activity,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

export function DashboardPage() {
  const { data: healthData } = useCustom({
    url: "/api/admin/health",
    method: "get",
  });

  const { data: stagingData, isLoading: stagingLoading } = useList({
    resource: "staging_docs",
    pagination: { current: 1, pageSize: 100 },
  });

  const { data: sourcesData } = useList({
    resource: "sources",
    pagination: { current: 1, pageSize: 1 },
  });

  const { data: leadsData } = useList({
    resource: "crm_leads",
    pagination: { current: 1, pageSize: 1 },
  });

  const { data: sessionsData } = useList({
    resource: "sales_sessions",
    pagination: { current: 1, pageSize: 1 },
  });

  const { data: auditData } = useList({
    resource: "audit_logs",
    pagination: { current: 1, pageSize: 10 },
    sorters: [{ field: "created_at", order: "desc" }],
  });

  const health = healthData?.data as Record<string, unknown> | undefined;
  const stagingDocs = stagingData?.data || [];
  const pendingDocs = stagingDocs.filter(
    (d: Record<string, unknown>) => d.status === "pending"
  );
  const totalDocs = sourcesData?.total ?? 0;
  const totalLeads = leadsData?.total ?? 0;
  const activeSessions = sessionsData?.total ?? 0;
  const auditLogs = auditData?.data || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-100">Dashboard</h1>
        <p className="text-sm text-stone-500 mt-1">
          System overview and recent activity
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-stone-400">
              Total Documents
            </CardTitle>
            <FileText className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-stone-100">{totalDocs}</div>
            <p className="text-xs text-stone-500 mt-1">Published + staging</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-stone-400">
              Staging Pending
            </CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-stone-100">
              {stagingLoading ? "..." : pendingDocs.length}
            </div>
            <p className="text-xs text-stone-500 mt-1">Awaiting review</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-stone-400">
              CRM Leads
            </CardTitle>
            <Users className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-stone-100">{totalLeads}</div>
            <p className="text-xs text-stone-500 mt-1">Total leads tracked</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-stone-400">
              Active Sessions
            </CardTitle>
            <Activity className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-stone-100">
              {activeSessions}
            </div>
            <p className="text-xs text-stone-500 mt-1">Sales conversations</p>
          </CardContent>
        </Card>
      </div>

      {/* Health Status */}
      {health && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-stone-400">
              System Health
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {Object.entries(health).map(([key, val]) => (
                <div key={key} className="space-y-1">
                  <div className="text-xs text-stone-500 capitalize">
                    {key.replace(/_/g, " ")}
                  </div>
                  <div className="flex items-center gap-2">
                    {String(val) === "ok" || String(val) === "healthy" ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                    )}
                    <span className="text-sm text-stone-200">{String(val)}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-stone-400">
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {auditLogs.length === 0 ? (
            <p className="text-sm text-stone-500">No recent activity</p>
          ) : (
            <div className="space-y-3">
              {auditLogs.slice(0, 8).map((log: Record<string, unknown>) => (
                <div
                  key={String(log.id || log.action_id)}
                  className="flex items-center justify-between py-1 border-b border-stone-800/50 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-amber-600" />
                    <div>
                      <span className="text-sm text-stone-200">
                        {String(log.action || log.action_type || "-")}
                      </span>
                      <span className="text-xs text-stone-500 ml-2">
                        {String(log.entity || log.resource || "")}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-stone-500">
                      {String(log.user_id || log.performed_by || "")}
                    </span>
                    <span className="text-xs text-stone-600">
                      {String(log.created_at || log.timestamp || "").slice(0, 10)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
