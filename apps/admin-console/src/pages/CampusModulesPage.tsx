import { useCustom } from "@refinedev/core";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

type ModuleCounts = Record<string, number>;
type ModuleDashboard = Record<string, unknown> & {
  summary?: Record<string, ModuleCounts>;
};

const modules = [
  { key: "materials", title: "材料收集", primary: "open_tasks", secondary: "missing", secondaryLabel: "缺交" },
  { key: "leaves", title: "请假销假", primary: "pending", secondary: "overdue_return", secondaryLabel: "逾期未销假" },
  { key: "scores", title: "成绩复核", primary: "review_required", secondary: "", secondaryLabel: "" },
  { key: "payments", title: "缴费对账", primary: "review_required", secondary: "anomalies", secondaryLabel: "异常" },
  { key: "attendance", title: "考勤点名", primary: "open_anomalies", secondary: "", secondaryLabel: "" },
  { key: "automation", title: "自动化任务", primary: "pending_jobs", secondary: "", secondaryLabel: "" },
];

export function CampusModulesPage() {
  const { data, isLoading, error } = useCustom<ModuleDashboard>({
    url: "/api/campus/modules/dashboard",
    method: "get",
  });
  const summary = data?.data?.summary || {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-100">Campus Operations</h1>
        <p className="mt-1 text-sm text-stone-500">材料、销假、成绩、缴费与考勤模块统一待办视图</p>
      </div>
      {error ? <div className="rounded border border-red-800 p-4 text-red-300">{String(error.message)}</div> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {modules.map((item) => {
          const values = summary[item.key] || {};
          return (
            <Card key={item.key}>
              <CardHeader>
                <CardTitle className="text-sm text-stone-300">{item.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-semibold text-amber-400">
                  {isLoading ? "-" : String(values[item.primary] ?? 0)}
                </div>
                {item.secondary ? (
                  <p className="mt-2 text-sm text-stone-500">
                    {item.secondaryLabel}: {String(values[item.secondary] ?? 0)}
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-stone-500">当前待处理项</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
