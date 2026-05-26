import { useList } from "@refinedev/core";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Table, THead, TBody, Tr, Th, Td } from "../components/ui/table";
import { Badge } from "../components/ui/badge";

type RepairTicket = Record<string, unknown> & {
  ticket_id: string;
  location_detail?: string;
  category?: string;
  priority?: string;
  status?: string;
  assignee_id?: string;
};

export function CampusRepairsPage() {
  const { data, isLoading } = useList<RepairTicket>({
    resource: "campus_repairs",
    pagination: { current: 1, pageSize: 50 },
  });

  const items = data?.data || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-100">Campus Repairs</h1>
        <p className="mt-1 text-sm text-stone-500">报修工单池、优先级与处理状态</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-stone-300">Repair Tickets</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="py-8 text-center text-stone-500">Loading repair tickets...</div>
          ) : (
            <Table>
              <THead>
                <Tr>
                  <Th>Location</Th>
                  <Th>Category</Th>
                  <Th>Priority</Th>
                  <Th>Status</Th>
                  <Th>Assignee</Th>
                </Tr>
              </THead>
              <TBody>
                {items.map((item) => (
                  <Tr key={item.ticket_id}>
                    <Td>{String(item.location_detail || item.location_type || "-")}</Td>
                    <Td>{String(item.category || "-")}</Td>
                    <Td>
                      <Badge variant={item.priority === "urgent" ? "error" : item.priority === "high" ? "warning" : "info"}>
                        {String(item.priority || "-")}
                      </Badge>
                    </Td>
                    <Td>{String(item.status || "-")}</Td>
                    <Td>{String(item.assignee_id || "-")}</Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
