import { useList } from "@refinedev/core";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Table, THead, TBody, Tr, Th, Td } from "../components/ui/table";
import { Badge } from "../components/ui/badge";

type LeaveRecord = Record<string, unknown> & {
  leave_id: string;
  student_name?: string;
  type?: string;
  start_time?: string;
  end_time?: string;
  status?: string;
};

export function CampusLeavesPage() {
  const { data, isLoading } = useList<LeaveRecord>({
    resource: "campus_leaves",
    pagination: { current: 1, pageSize: 50 },
  });

  const items = data?.data || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-100">Campus Leaves</h1>
        <p className="mt-1 text-sm text-stone-500">请假申请、审批状态与时间线</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-stone-300">Leave Ledger</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="py-8 text-center text-stone-500">Loading leave requests...</div>
          ) : (
            <Table>
              <THead>
                <Tr>
                  <Th>Student</Th>
                  <Th>Type</Th>
                  <Th>Start</Th>
                  <Th>End</Th>
                  <Th>Status</Th>
                </Tr>
              </THead>
              <TBody>
                {items.map((item) => (
                  <Tr key={item.leave_id}>
                    <Td>{String(item.student_name || item.student_id || "-")}</Td>
                    <Td>{String(item.type || "-")}</Td>
                    <Td>{String(item.start_time || "-")}</Td>
                    <Td>{String(item.end_time || "-")}</Td>
                    <Td>
                      <Badge variant={item.status === "approved" ? "success" : item.status === "rejected" ? "error" : "warning"}>
                        {String(item.status || "pending")}
                      </Badge>
                    </Td>
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
