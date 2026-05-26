import { useState } from "react";
import { useList, useCustom } from "@refinedev/core";
import { Table, THead, TBody, Tr, Th, Td } from "../components/ui/table";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { PhoneCall, RefreshCw, Eye, UserCheck, MessageCircle, Clock } from "lucide-react";

type SalesSession = Record<string, unknown> & {
  id: string | number;
  user_id?: string;
  user_name?: string;
  campus?: string;
  intent?: string;
  status?: string;
  takeover_status?: string;
  duration_seconds?: number;
  message_count?: number;
  created_at?: string;
  messages?: Array<Record<string, unknown>>;
};

const takeoverBadge: Record<string, "success" | "warning" | "error" | "info" | "default"> = {
  none: "default",
  requested: "warning",
  active: "info",
  completed: "success",
  declined: "error",
};

function SessionMessagesDialog({
  session,
  onClose,
}: {
  session: SalesSession | null;
  onClose: () => void;
}) {
  const { data, isLoading } = useCustom({
    url: session ? `/api/sales/sessions/${session.id}/detail` : "",
    method: "get",
    queryOptions: { enabled: !!session },
  });

  const messages = (
    data?.data
      ? Array.isArray(data.data)
        ? data.data
        : (data.data as Record<string, unknown>)?.messages || []
      : session?.messages || []
  ) as Array<Record<string, unknown>>;

  return (
    <Dialog open={!!session} onOpenChange={(open) => !open && onClose()}>
      {session && (
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>
              Session {String(session.id).slice(0, 8)}...
            </DialogTitle>
          </DialogHeader>
          <div className="p-6 overflow-y-auto flex-1 space-y-4">
            {/* Session info */}
            <div className="grid grid-cols-3 gap-3 text-sm mb-4">
              <div>
                <span className="text-stone-500 text-xs">User</span>
                <p className="text-stone-200">
                  {String(session.user_name || session.user_id || "-")}
                </p>
              </div>
              <div>
                <span className="text-stone-500 text-xs">Campus</span>
                <p className="text-stone-200">{String(session.campus || "-")}</p>
              </div>
              <div>
                <span className="text-stone-500 text-xs">Intent</span>
                <p className="text-stone-200">{String(session.intent || "-")}</p>
              </div>
            </div>

            {isLoading ? (
              <div className="text-center text-stone-500 py-8">
                Loading messages...
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-stone-500 py-8">
                No messages in this session
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((msg: Record<string, unknown>, i: number) => {
                  const role = String(msg.role || msg.sender || "unknown");
                  const isUser = role === "user" || role === "student";
                  return (
                    <div
                      key={i}
                      className={`flex ${isUser ? "justify-start" : "justify-end"}`}
                    >
                      <div
                        className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                          isUser
                            ? "bg-stone-800 text-stone-200"
                            : "bg-amber-900/40 text-amber-100"
                        }`}
                      >
                        <div className="text-[10px] text-stone-500 mb-1 uppercase">
                          {role}
                        </div>
                        <div className="whitespace-pre-wrap">
                          {String(
                            msg.content || msg.text || msg.message || ""
                          )}
                        </div>
                        <div className="text-[10px] text-stone-600 mt-1">
                          {String(msg.created_at || msg.timestamp || "")}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}

export function SalesSessionsPage() {
  const [selectedSession, setSelectedSession] =
    useState<SalesSession | null>(null);
  const [takeoverFilter, setTakeoverFilter] = useState("all");

  const { data, isLoading, refetch } = useList({
    resource: "sales_sessions",
    pagination: { current: 1, pageSize: 100 },
    sorters: [{ field: "created_at", order: "desc" }],
  });

  const sessions = (data?.data || []) as SalesSession[];
  const filteredSessions =
    takeoverFilter === "all"
      ? sessions
      : sessions.filter(
          (s) => String(s.takeover_status) === takeoverFilter
        );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">
            Sales Sessions
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            Monitor active and past sales conversations
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-stone-500">Takeover:</span>
        {[
          { value: "all", label: "All" },
          { value: "none", label: "None" },
          { value: "requested", label: "Requested" },
          { value: "active", label: "Active" },
          { value: "completed", label: "Completed" },
          { value: "declined", label: "Declined" },
        ].map((f) => (
          <button
            key={f.value}
            onClick={() => setTakeoverFilter(f.value)}
            className={`text-xs px-3 py-1 rounded-full transition-colors ${
              takeoverFilter === f.value
                ? "bg-amber-600 text-white"
                : "bg-stone-800 text-stone-400 hover:bg-stone-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <Tr>
                <Th>User</Th>
                <Th>Campus</Th>
                <Th>Intent</Th>
                <Th>Status</Th>
                <Th>Takeover</Th>
                <Th>Messages</Th>
                <Th>Duration</Th>
                <Th>Actions</Th>
              </Tr>
            </THead>
            <TBody>
              {isLoading ? (
                <Tr>
                  <Td colSpan={8} className="text-center py-8 text-stone-500">
                    Loading...
                  </Td>
                </Tr>
              ) : filteredSessions.length === 0 ? (
                <Tr>
                  <Td colSpan={8} className="text-center py-8 text-stone-500">
                    No sessions found
                  </Td>
                </Tr>
              ) : (
                filteredSessions.map((session) => (
                  <Tr key={String(session.id)}>
                    <Td>
                      <div className="flex items-center gap-2">
                        <PhoneCall className="h-4 w-4 text-stone-500" />
                        <span className="text-stone-200">
                          {String(
                            session.user_name || session.user_id || "Unknown"
                          )}
                        </span>
                      </div>
                    </Td>
                    <Td className="text-stone-400 text-xs">
                      {String(session.campus || "-")}
                    </Td>
                    <Td>
                      <Badge
                        variant={
                          String(session.intent) === "high"
                            ? "success"
                            : String(session.intent) === "medium"
                            ? "warning"
                            : "default"
                        }
                      >
                        {String(session.intent || "none")}
                      </Badge>
                    </Td>
                    <Td className="text-stone-400 text-xs">
                      {String(session.status || "-")}
                    </Td>
                    <Td>
                      <Badge
                        variant={
                          takeoverBadge[
                            String(session.takeover_status)
                          ] || "default"
                        }
                      >
                        {String(session.takeover_status || "none")}
                      </Badge>
                    </Td>
                    <Td className="text-stone-400 text-xs font-mono">
                      {String(session.message_count ?? "-")}
                    </Td>
                    <Td className="text-stone-500 text-xs">
                      {session.duration_seconds
                        ? `${Math.floor(
                            (session.duration_seconds as number) / 60
                          )}m ${(session.duration_seconds as number) % 60}s`
                        : "-"}
                    </Td>
                    <Td>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedSession(session)}
                        >
                          <MessageCircle className="h-3.5 w-3.5" />
                        </Button>
                        {String(session.takeover_status) === "requested" && (
                          <Button variant="default" size="sm">
                            <UserCheck className="h-3.5 w-3.5 mr-1" />
                            Takeover
                          </Button>
                        )}
                      </div>
                    </Td>
                  </Tr>
                ))
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <SessionMessagesDialog
        session={selectedSession}
        onClose={() => setSelectedSession(null)}
      />
    </div>
  );
}
