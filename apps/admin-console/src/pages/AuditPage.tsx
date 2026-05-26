import { useState } from "react";
import { useList } from "@refinedev/core";
import { Table, THead, TBody, Tr, Th, Td } from "../components/ui/table";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent } from "../components/ui/card";
import { Shield, RefreshCw, Search } from "lucide-react";

type AuditEntry = Record<string, unknown> & {
  id: string | number;
  action?: string;
  action_type?: string;
  entity?: string;
  resource?: string;
  entity_id?: string;
  user_id?: string;
  performed_by?: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  created_at?: string;
  timestamp?: string;
};

const actionBadge: Record<string, "success" | "warning" | "error" | "info" | "default"> = {
  create: "success",
  update: "info",
  delete: "error",
  publish: "success",
  approve: "success",
  reject: "error",
  validate: "info",
  login: "default",
  logout: "default",
};

export function AuditPage() {
  const [actionFilter, setActionFilter] = useState("all");
  const [searchText, setSearchText] = useState("");

  const { data, isLoading, refetch } = useList({
    resource: "audit_logs",
    pagination: { current: 1, pageSize: 200 },
    sorters: [{ field: "created_at", order: "desc" }],
  });

  const logs = (data?.data || []) as AuditEntry[];
  const allActions = [
    ...new Set(logs.map((l) => l.action || l.action_type || "unknown")),
  ];

  const filteredLogs = logs.filter((log) => {
    if (actionFilter !== "all" && (log.action || log.action_type) !== actionFilter) {
      return false;
    }
    if (searchText) {
      const q = searchText.toLowerCase();
      const searchable = [
        String(log.action || ""),
        String(log.action_type || ""),
        String(log.entity || ""),
        String(log.resource || ""),
        String(log.user_id || ""),
        String(log.performed_by || ""),
        String(log.entity_id || ""),
      ].join(" ").toLowerCase();
      return searchable.includes(q);
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">Audit Log</h1>
          <p className="text-sm text-stone-500 mt-1">
            Track all administrative actions and system events
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-stone-500">Action:</span>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-stone-900 text-stone-200 text-xs border border-stone-700 rounded px-2 py-1.5 outline-none focus:border-amber-600"
          >
            <option value="all">All Actions</option>
            {allActions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-stone-500" />
          <input
            type="text"
            placeholder="Search logs..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="bg-stone-900 text-stone-200 text-xs border border-stone-700 rounded pl-8 pr-3 py-1.5 w-56 outline-none focus:border-amber-600 placeholder-stone-600"
          />
        </div>
        <span className="text-xs text-stone-500">
          {filteredLogs.length} of {logs.length} entries
        </span>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <Tr>
                <Th>Timestamp</Th>
                <Th>Action</Th>
                <Th>Resource</Th>
                <Th>Entity ID</Th>
                <Th>User</Th>
                <Th>Details</Th>
              </Tr>
            </THead>
            <TBody>
              {isLoading ? (
                <Tr>
                  <Td colSpan={6} className="text-center py-8 text-stone-500">
                    Loading...
                  </Td>
                </Tr>
              ) : filteredLogs.length === 0 ? (
                <Tr>
                  <Td colSpan={6} className="text-center py-8 text-stone-500">
                    No audit log entries found
                  </Td>
                </Tr>
              ) : (
                filteredLogs.map((log) => {
                  const action = String(log.action || log.action_type || "unknown");
                  return (
                    <Tr key={String(log.id)}>
                      <Td className="text-stone-500 text-xs font-mono whitespace-nowrap">
                        {String(log.created_at || log.timestamp || "-")}
                      </Td>
                      <Td>
                        <Badge variant={actionBadge[action] || "default"}>
                          {action}
                        </Badge>
                      </Td>
                      <Td className="text-stone-400 text-xs">
                        <div className="flex items-center gap-1.5">
                          <Shield className="h-3 w-3 text-stone-600" />
                          {String(log.entity || log.resource || "-")}
                        </div>
                      </Td>
                      <Td className="text-stone-500 text-xs font-mono">
                        {String(log.entity_id || "-").slice(0, 12)}
                      </Td>
                      <Td className="text-stone-400 text-xs">
                        {String(log.user_id || log.performed_by || "-")}
                      </Td>
                      <Td className="max-w-[200px]">
                        {log.details ? (
                          <pre className="text-[10px] text-stone-500 overflow-hidden text-ellipsis whitespace-nowrap">
                            {JSON.stringify(log.details).slice(0, 80)}
                            {JSON.stringify(log.details).length > 80 ? "..." : ""}
                          </pre>
                        ) : (
                          <span className="text-stone-600 text-xs">-</span>
                        )}
                      </Td>
                    </Tr>
                  );
                })
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
