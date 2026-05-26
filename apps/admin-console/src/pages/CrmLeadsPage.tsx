import { useState } from "react";
import { useList, useCustom } from "@refinedev/core";
import { Table, THead, TBody, Tr, Th, Td } from "../components/ui/table";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { getAdminHeaders } from "../dataProvider";
import {
  Users,
  UserPlus,
  RefreshCw,
  Eye,
  MessageSquare,
  UserCheck,
  ArrowUpDown,
} from "lucide-react";

type CrmLead = Record<string, unknown> & {
  id: string | number;
  name?: string;
  score?: number;
  status?: string;
  intent_level?: string;
  campus?: string;
  phone?: string;
  created_at?: string;
  last_contacted?: string;
  followups?: Array<Record<string, unknown>>;
};

const statusBadge: Record<string, "success" | "warning" | "error" | "info" | "default"> = {
  new: "info",
  contacted: "warning",
  qualified: "success",
  lost: "error",
  converted: "success",
};

function LeadDetailDialog({
  lead,
  onClose,
}: {
  lead: CrmLead | null;
  onClose: () => void;
}) {
  const [followupText, setFollowupText] = useState("");
  const [newStatus, setNewStatus] = useState("");

  async function addFollowup() {
    if (!followupText.trim() || !lead) return;
    try {
      await fetch(`/api/crm/leads/${lead.id}/followups`, {
        method: "POST",
        headers: getAdminHeaders(),
        body: JSON.stringify({ note: followupText }),
      });
      setFollowupText("");
    } catch (err) {
      console.error("Failed to add followup:", err);
    }
  }

  async function changeStatus() {
    if (!newStatus || !lead) return;
    try {
      await fetch(`/api/crm/leads/${lead.id}/status`, {
        method: "POST",
        headers: getAdminHeaders(),
        body: JSON.stringify({ status: newStatus }),
      });
      setNewStatus("");
    } catch (err) {
      console.error("Failed to update status:", err);
    }
  }

  async function assignTo(assignee: string) {
    if (!lead) return;
    try {
      await fetch(`/api/crm/leads/${lead.id}/assign`, {
        method: "POST",
        headers: getAdminHeaders(),
        body: JSON.stringify({ assignee }),
      });
    } catch (err) {
      console.error("Failed to assign lead:", err);
    }
  }

  return (
    <Dialog open={!!lead} onOpenChange={(open) => !open && onClose()}>
      {lead && (
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{String(lead.name || lead.id)}</DialogTitle>
          </DialogHeader>
          <div className="p-6 space-y-5">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-stone-500">ID</span>
                <p className="text-stone-200 font-mono text-xs">{String(lead.id)}</p>
              </div>
              <div>
                <span className="text-stone-500">Status</span>
                <p>
                  <Badge variant={statusBadge[String(lead.status)] || "default"}>
                    {String(lead.status)}
                  </Badge>
                </p>
              </div>
              <div>
                <span className="text-stone-500">Score</span>
                <p className="text-stone-200">{String(lead.score ?? "-")}</p>
              </div>
              <div>
                <span className="text-stone-500">Intent</span>
                <p className="text-stone-200">{String(lead.intent_level || "-")}</p>
              </div>
              <div>
                <span className="text-stone-500">Campus</span>
                <p className="text-stone-200">{String(lead.campus || "-")}</p>
              </div>
              <div>
                <span className="text-stone-500">Phone</span>
                <p className="text-stone-200">{String(lead.phone || "-")}</p>
              </div>
              <div>
                <span className="text-stone-500">Created</span>
                <p className="text-stone-200">{String(lead.created_at || "-")}</p>
              </div>
              <div>
                <span className="text-stone-500">Last Contacted</span>
                <p className="text-stone-200">{String(lead.last_contacted || "-")}</p>
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-3 border-t border-stone-800 pt-4">
              <div>
                <span className="text-sm text-stone-500">Change Status</span>
                <div className="flex items-center gap-2 mt-1">
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value)}
                    className="admin-input text-xs flex-1"
                  >
                    <option value="">Select status...</option>
                    <option value="new">New</option>
                    <option value="contacted">Contacted</option>
                    <option value="qualified">Qualified</option>
                    <option value="lost">Lost</option>
                    <option value="converted">Converted</option>
                  </select>
                  <Button size="sm" onClick={changeStatus} disabled={!newStatus}>
                    Update
                  </Button>
                </div>
              </div>

              <div>
                <span className="text-sm text-stone-500">Assign To</span>
                <div className="flex items-center gap-2 mt-1">
                  <Input
                    placeholder="Assignee name..."
                    className="text-xs flex-1"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        assignTo((e.target as HTMLInputElement).value);
                        (e.target as HTMLInputElement).value = "";
                      }
                    }}
                  />
                  <Button size="sm">Assign</Button>
                </div>
              </div>

              <div>
                <span className="text-sm text-stone-500">Add Follow-up</span>
                <div className="flex items-center gap-2 mt-1">
                  <Input
                    placeholder="Follow-up note..."
                    className="text-xs flex-1"
                    value={followupText}
                    onChange={(e) => setFollowupText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") addFollowup();
                    }}
                  />
                  <Button size="sm" onClick={addFollowup} disabled={!followupText.trim()}>
                    Add
                  </Button>
                </div>
              </div>
            </div>

            {/* Follow-ups history */}
            {lead.followups && lead.followups.length > 0 && (
              <div className="border-t border-stone-800 pt-4">
                <span className="text-sm text-stone-500">Follow-up History</span>
                <div className="mt-2 space-y-2">
                  {lead.followups.map((fup, i) => (
                    <div
                      key={i}
                      className="p-2 rounded bg-stone-900 text-xs text-stone-300"
                    >
                      <p>{String(fup.note || fup.message || "-")}</p>
                      <p className="text-stone-600 mt-1">
                        {String(fup.created_at || fup.timestamp || "")}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}

export function CrmLeadsPage() {
  const [selectedLead, setSelectedLead] = useState<CrmLead | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  const { data, isLoading, refetch } = useList({
    resource: "crm_leads",
    pagination: { current: 1, pageSize: 100 },
  });

  const leads = (data?.data || []) as CrmLead[];
  const filteredLeads =
    statusFilter === "all"
      ? leads
      : leads.filter((l) => String(l.status) === statusFilter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">CRM Leads</h1>
          <p className="text-sm text-stone-500 mt-1">
            Manage and track sales leads
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
          <Button size="sm">
            <UserPlus className="h-4 w-4 mr-1" />
            Add Lead
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-stone-500">Status:</span>
        {["all", "new", "contacted", "qualified", "lost", "converted"].map(
          (s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`text-xs px-3 py-1 rounded-full transition-colors ${
                statusFilter === s
                  ? "bg-amber-600 text-white"
                  : "bg-stone-800 text-stone-400 hover:bg-stone-700"
              }`}
            >
              {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          )
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <Tr>
                <Th>Name</Th>
                <Th>Score</Th>
                <Th>Intent</Th>
                <Th>Status</Th>
                <Th>Campus</Th>
                <Th>Created</Th>
                <Th>Actions</Th>
              </Tr>
            </THead>
            <TBody>
              {isLoading ? (
                <Tr>
                  <Td colSpan={7} className="text-center py-8 text-stone-500">
                    Loading...
                  </Td>
                </Tr>
              ) : filteredLeads.length === 0 ? (
                <Tr>
                  <Td colSpan={7} className="text-center py-8 text-stone-500">
                    No leads found
                  </Td>
                </Tr>
              ) : (
                filteredLeads.map((lead) => (
                  <Tr key={String(lead.id)}>
                    <Td>
                      <button
                        onClick={() => setSelectedLead(lead)}
                        className="flex items-center gap-2 text-stone-200 hover:text-amber-500 transition-colors"
                      >
                        <Users className="h-4 w-4 text-stone-500" />
                        <span>{String(lead.name || "Unnamed")}</span>
                      </button>
                    </Td>
                    <Td>
                      <span
                        className={`font-mono text-sm ${
                          (lead.score as number) >= 70
                            ? "text-emerald-400"
                            : (lead.score as number) >= 40
                            ? "text-amber-400"
                            : "text-stone-400"
                        }`}
                      >
                        {String(lead.score ?? "-")}
                      </span>
                    </Td>
                    <Td>
                      <Badge
                        variant={
                          String(lead.intent_level) === "high"
                            ? "success"
                            : String(lead.intent_level) === "medium"
                            ? "warning"
                            : "default"
                        }
                      >
                        {String(lead.intent_level || "-")}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge
                        variant={statusBadge[String(lead.status)] || "default"}
                      >
                        {String(lead.status)}
                      </Badge>
                    </Td>
                    <Td className="text-stone-400 text-xs">
                      {String(lead.campus || "-")}
                    </Td>
                    <Td className="text-stone-500 text-xs">
                      {String(lead.created_at || "-").slice(0, 10)}
                    </Td>
                    <Td>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedLead(lead)}
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSelectedLead(lead);
                          }}
                        >
                          <MessageSquare className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            const name = prompt("Assign to:");
                            if (name) setSelectedLead(lead);
                          }}
                        >
                          <UserCheck className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </Td>
                  </Tr>
                ))
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <LeadDetailDialog
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
      />
    </div>
  );
}
