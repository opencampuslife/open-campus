import { useCustom } from "@refinedev/core";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";

type MealSummary = {
  meal_date: string;
  total_count: number;
  special_count: number;
  delivery?: Record<string, unknown>;
};

export function CampusMealsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const { data, isLoading } = useCustom<MealSummary>({
    url: "/api/campus/meals/summary",
    method: "get",
    config: {
      query: { date: today },
    },
  });

  const summary = data?.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-stone-100">Campus Meals</h1>
        <p className="mt-1 text-sm text-stone-500">当日订餐汇总、配送状态与特殊餐统计</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm text-stone-400">Meal Date</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-stone-100">{summary?.meal_date || today}</div></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-stone-400">Total Orders</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-stone-100">{isLoading ? "..." : String(summary?.total_count ?? 0)}</div></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-stone-400">Special Meals</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-stone-100">{isLoading ? "..." : String(summary?.special_count ?? 0)}</div></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-stone-300">Delivery Status</CardTitle>
        </CardHeader>
        <CardContent>
          <Badge variant={String(summary?.delivery?.status || "pending") === "confirmed" ? "success" : "warning"}>
            {String(summary?.delivery?.status || "pending")}
          </Badge>
        </CardContent>
      </Card>
    </div>
  );
}
