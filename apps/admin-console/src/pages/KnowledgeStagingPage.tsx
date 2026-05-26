import { useState } from "react";
import { useList, useCustom } from "@refinedev/core";
import { Table, THead, TBody, Tr, Th, Td } from "../components/ui/table";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { adminMutation } from "../dataProvider";
import { FileText, Upload, RefreshCw, Eye, CheckCircle2, XCircle, Send } from "lucide-react";

type StagingDoc = Record<string, unknown> & {
  id: string | number;
  title?: string;
  status?: string;
  created_at?: string;
};

const statusBadge: Record<string, "success" | "warning" | "error" | "info" | "default"> = {
  pending: "warning",
  validated: "info",
  approved: "success",
  rejected: "error",
  published: "success",
};

function isPresent(value: unknown): boolean {
  return value !== null && value !== undefined;
}

function DocDetailPanel({
  doc,
  onClose,
}: {
  doc: StagingDoc | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={!!doc} onOpenChange={(open) => !open && onClose()}>
      {doc && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{String(doc.title || "Untitled")}</DialogTitle>
          </DialogHeader>
          <div className="p-6 space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-stone-500">ID</span>
                <p className="text-stone-200 font-mono text-xs">{String(doc.id)}</p>
              </div>
              <div>
                <span className="text-stone-500">Status</span>
                <p>
                  <Badge variant={statusBadge[String(doc.status)] || "default"}>
                    {String(doc.status)}
                  </Badge>
                </p>
              </div>
              <div>
                <span className="text-stone-500">Created</span>
                <p className="text-stone-200">{String(doc.created_at || "-")}</p>
              </div>
              <div>
                <span className="text-stone-500">Updated</span>
                <p className="text-stone-200">{String(doc.updated_at || "-")}</p>
              </div>
            </div>
            {isPresent(doc.frontmatter) && (
              <div>
                <span className="text-sm text-stone-500">Frontmatter</span>
                <pre className="mt-1 p-3 rounded bg-stone-900 text-stone-300 text-xs overflow-auto max-h-48">
                  {typeof doc.frontmatter === "string"
                    ? doc.frontmatter
                    : JSON.stringify(doc.frontmatter, null, 2)}
                </pre>
              </div>
            )}
            {isPresent(doc.content) && (
              <div>
                <span className="text-sm text-stone-500">Content Preview</span>
                <div className="mt-1 p-3 rounded bg-stone-900 text-stone-300 text-xs overflow-auto max-h-64 whitespace-pre-wrap">
                  {typeof doc.content === "string"
                    ? doc.content.slice(0, 2000)
                    : JSON.stringify(doc.content).slice(0, 2000)}
                </div>
                {typeof doc.content === "string" && doc.content.length > 2000 && (
                  <p className="text-xs text-stone-500 mt-1">Content truncated...</p>
                )}
              </div>
            )}
            {isPresent(doc.validation) && (
              <div>
                <span className="text-sm text-stone-500">Validation Results</span>
                <pre className="mt-1 p-3 rounded bg-stone-900 text-stone-300 text-xs overflow-auto max-h-32">
                  {JSON.stringify(doc.validation, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}

export function KnowledgeStagingPage() {
  const [selectedDoc, setSelectedDoc] = useState<StagingDoc | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const { data, isLoading, refetch } = useList({
    resource: "staging_docs",
    pagination: { current: 1, pageSize: 100 },
    sorters: [{ field: "created_at", order: "desc" }],
  });

  const docs = (data?.data || []) as StagingDoc[];

  async function performAction(docId: string | number, action: string) {
    setActionLoading(`${docId}-${action}`);
    try {
      await adminMutation(`/api/admin/staging/docs/${docId}/${action}`);
      refetch();
    } catch (err) {
      console.error(`Action ${action} failed:`, err);
    } finally {
      setActionLoading(null);
    }
  }

  function getAvailableActions(status: string): { label: string; action: string; variant: "default" | "secondary" | "outline" | "ghost" | "danger" }[] {
    switch (status) {
      case "pending":
        return [
          { label: "Validate", action: "validate", variant: "secondary" },
        ];
      case "validated":
        return [
          { label: "Approve", action: "approve", variant: "default" },
          { label: "Reject", action: "reject", variant: "danger" },
        ];
      case "approved":
        return [
          { label: "Publish", action: "publish", variant: "default" },
          { label: "Reject", action: "reject", variant: "danger" },
        ];
      default:
        return [];
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">Knowledge Staging</h1>
          <p className="text-sm text-stone-500 mt-1">
            Review, validate, and publish knowledge documents
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
          <Button size="sm">
            <Upload className="h-4 w-4 mr-1" />
            Upload
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <Tr>
                <Th>ID</Th>
                <Th>Title</Th>
                <Th>Status</Th>
                <Th>Created</Th>
                <Th>Actions</Th>
              </Tr>
            </THead>
            <TBody>
              {isLoading ? (
                <Tr>
                  <Td colSpan={5} className="text-center py-8 text-stone-500">
                    Loading...
                  </Td>
                </Tr>
              ) : docs.length === 0 ? (
                <Tr>
                  <Td colSpan={5} className="text-center py-8 text-stone-500">
                    No staging documents found
                  </Td>
                </Tr>
              ) : (
                docs.map((doc) => (
                  <Tr key={String(doc.id)}>
                    <Td className="font-mono text-xs text-stone-500">
                      {String(doc.id).slice(0, 8)}...
                    </Td>
                    <Td>
                      <button
                        onClick={() => setSelectedDoc(doc)}
                        className="flex items-center gap-2 text-stone-200 hover:text-amber-500 transition-colors"
                      >
                        <FileText className="h-4 w-4 text-stone-500" />
                        <span>{String(doc.title || "Untitled")}</span>
                      </button>
                    </Td>
                    <Td>
                      <Badge variant={statusBadge[String(doc.status)] || "default"}>
                        {String(doc.status)}
                      </Badge>
                    </Td>
                    <Td className="text-stone-500 text-xs">
                      {String(doc.created_at || "-").slice(0, 10)}
                    </Td>
                    <Td>
                      <div className="flex items-center gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedDoc(doc)}
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        {getAvailableActions(String(doc.status)).map((btn) => (
                          <Button
                            key={btn.action}
                            variant={btn.variant}
                            size="sm"
                            onClick={() => performAction(doc.id, btn.action)}
                            disabled={actionLoading === `${doc.id}-${btn.action}`}
                          >
                            {actionLoading === `${doc.id}-${btn.action}` ? (
                              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                            ) : btn.action === "approve" || btn.action === "validate" ? (
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            ) : btn.action === "reject" ? (
                              <XCircle className="h-3.5 w-3.5" />
                            ) : btn.action === "publish" ? (
                              <Send className="h-3.5 w-3.5" />
                            ) : null}
                            {btn.label}
                          </Button>
                        ))}
                      </div>
                    </Td>
                  </Tr>
                ))
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      {/* Validation results summary */}
      {docs.filter((d) => d.validation).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-stone-400">
              Latest Validations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {docs
                .filter((d) => d.validation)
                .slice(0, 5)
                .map((doc) => (
                  <div
                    key={String(doc.id)}
                    className="flex items-center justify-between text-sm py-1 border-b border-stone-800/50 last:border-0"
                  >
                    <span className="text-stone-300">
                      {String(doc.title || doc.id)}
                    </span>
                    <Badge
                      variant={
                        (doc.validation as Record<string, unknown>)?.valid
                          ? "success"
                          : "error"
                      }
                    >
                      {(doc.validation as Record<string, unknown>)?.valid
                        ? "Pass"
                        : "Fail"}
                    </Badge>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      <DocDetailPanel doc={selectedDoc} onClose={() => setSelectedDoc(null)} />
    </div>
  );
}
