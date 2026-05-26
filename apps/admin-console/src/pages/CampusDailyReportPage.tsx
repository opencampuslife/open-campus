import { useCustom } from "@refinedev/core";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";

type DailyReport = {
  report_id: string;
  summary?: {
    narrative?: string;
    leave?: Record<string, number>;
    meal?: Record<string, number>;
    repair?: Record<string, number>;
  };
};

export function CampusDailyReportPage() {
  const today = new Date().toISOString().slice(0, 10);
  const { data, isLoading } = useCustom<DailyReport>({
    url: "/api/campus/reports/daily",
    method: "get",
    config: {
      query: { date: today },
    },
  });

  const report = data?.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-100">Campus Daily Report</h1>
        <p className="mt-1 text-sm text-stone-500">每日请假、订餐、报修汇总与摘要</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-stone-300">Narrative</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-stone-300">
            {isLoading ? "Generating report..." : report?.summary?.narrative || "No report data"}
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm text-stone-400">Leave</CardTitle></CardHeader>
          <CardContent><pre className="text-xs text-stone-300">{JSON.stringify(report?.summary?.leave || {}, null, 2)}</pre></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-stone-400">Meal</CardTitle></CardHeader>
          <CardContent><pre className="text-xs text-stone-300">{JSON.stringify(report?.summary?.meal || {}, null, 2)}</pre></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-stone-400">Repair</CardTitle></CardHeader>
          <CardContent><pre className="text-xs text-stone-300">{JSON.stringify(report?.summary?.repair || {}, null, 2)}</pre></CardContent>
        </Card>
      </div>
    </div>
  );
}
