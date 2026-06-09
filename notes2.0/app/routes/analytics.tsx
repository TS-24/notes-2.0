import { BarChart3, ListTodo, FileText, Pin, Clock } from "lucide-react";
import { useState, useEffect } from "react";

interface AggregateMetrics {
  totalNotes: number;
  totalWords: number;
  totalChars: number;
}

export default function Analytics() {
  const [metricsData, setMetricsData] = useState<AggregateMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchAnalytics() {
      try {
        const storedNotes = localStorage.getItem("notes");
        const notes = storedNotes ? JSON.parse(storedNotes) : [];
        
        const response = await fetch("http://127.0.0.1:8000/api/analyze/aggregate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(notes),
        });

        if (!response.ok) {
          throw new Error("Failed to fetch analytics from backend");
        }

        const data = await response.json();
        setMetricsData(data);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    }

    fetchAnalytics();
  }, []);

  const metrics = [
    { name: "Total Notes", value: metricsData?.totalNotes || 0, icon: FileText, color: "text-blue-500" },
    { name: "Total Words", value: metricsData?.totalWords || 0, icon: ListTodo, color: "text-emerald-500" },
    { name: "Total Characters", value: metricsData?.totalChars || 0, icon: Pin, color: "text-amber-500" },
  ];

  return (
    <main className="flex-1 p-8 space-y-8 bg-zinc-50 dark:bg-zinc-950 min-h-screen font-sans">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-zinc-950/5 dark:bg-white/5 border border-zinc-200 dark:border-zinc-800 rounded-xl">
          <BarChart3 className="size-8 text-zinc-900 dark:text-zinc-50" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Analytics</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Insights and statistics for your note-taking activity.
          </p>
        </div>
      </div>

      {loading && <p className="text-sm text-zinc-500">Loading analytics from backend...</p>}
      {error && <p className="text-sm text-red-500">Error: {error}</p>}

      {!loading && !error && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {metrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <div
                key={metric.name}
                className="flex items-center gap-4 p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm hover:shadow-md transition-shadow"
              >
                <div className={`p-3 rounded-xl bg-zinc-100 dark:bg-zinc-800 ${metric.color}`}>
                  <Icon className="size-6" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                    {metric.name}
                  </p>
                  <h3 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                    {metric.value}
                  </h3>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="size-5 text-zinc-900 dark:text-zinc-50" />
          Recent Activity
        </h2>
        <div className="space-y-4">
          {[
            { action: "Created note", target: "Groceries List", time: "2 hours ago" },
            { action: "Pinned note", target: "Project Ideas", time: "5 hours ago" },
            { action: "Changed color", target: "Quick Reminders", time: "Yesterday" },
          ].map((item, index) => (
            <div
              key={index}
              className="flex items-center justify-between py-3 border-b border-zinc-100 dark:border-zinc-800 last:border-0"
            >
              <div>
                <span className="font-medium text-zinc-800 dark:text-zinc-200">
                  {item.action}
                </span>
                <span className="text-zinc-400 dark:text-zinc-500 mx-2">•</span>
                <span className="text-zinc-600 dark:text-zinc-400">{item.target}</span>
              </div>
              <span className="text-xs text-zinc-400 dark:text-zinc-500">{item.time}</span>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
