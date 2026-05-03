import { useMemo } from "react";
import { ListChecks, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToolShell, EmptyHint, Spinner } from "../ToolShell";
import { JobCard } from "../JobCard";
import { useBgJobs } from "@/api/queries";

// Queue view of every background job (translate, convert) the server
// has tracked since process start. Newest first, in-flight items at
// the top regardless of age. Empty until something is enqueued from
// TranslatePage / ConvertPage.

export function JobsPage(): React.ReactElement {
  const jobsQ = useBgJobs();
  const jobs = useMemo(() => jobsQ.data?.jobs ?? [], [jobsQ.data]);

  const inFlight = useMemo(
    () => jobs.filter((j) => j.status === "queued" || j.status === "running"),
    [jobs],
  );
  const finished = useMemo(
    () => jobs.filter((j) => j.status !== "queued" && j.status !== "running"),
    [jobs],
  );

  return (
    <ToolShell
      icon={ListChecks}
      title="Hàng đợi xử lý"
      subtitle="Theo dõi các tác vụ dịch và chuyển định dạng đang chạy"
      pending={jobsQ.isLoading}
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-ink-mute">
            {inFlight.length > 0
              ? `${inFlight.length} đang chạy · ${finished.length} đã xong`
              : `${finished.length} tác vụ đã xong`}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => jobsQ.refetch()}
            disabled={jobsQ.isFetching}
          >
            {jobsQ.isFetching ? <Spinner /> : <RefreshCw size={12} />}
            Làm mới
          </Button>
        </div>
      }
    >
      {jobs.length === 0 ? (
        <EmptyHint>
          Chưa có tác vụ nào. Vào{" "}
          <a className="font-mono text-accent underline" href="/translate">
            Dịch thuật
          </a>{" "}
          hoặc{" "}
          <a className="font-mono text-accent underline" href="/convert">
            Chuyển định dạng
          </a>{" "}
          để bắt đầu.
        </EmptyHint>
      ) : (
        <div className="space-y-3">
          {inFlight.length > 0 && (
            <section>
              <h3 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-soft">
                Đang chạy ({inFlight.length})
              </h3>
              <div className="space-y-2">
                {inFlight.map((j) => (
                  <JobCard key={j.id} job={j} />
                ))}
              </div>
            </section>
          )}
          {finished.length > 0 && (
            <section>
              <h3 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-soft">
                Đã xong ({finished.length})
              </h3>
              <div className="space-y-2">
                {finished.map((j) => (
                  <JobCard key={j.id} job={j} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </ToolShell>
  );
}
