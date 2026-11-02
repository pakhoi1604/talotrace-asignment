// Heading row for /hr/jobs: title reflects the filter, one-line explainer
// (failed jobs never count as a low score), plus the manual Refresh.

interface JobsPageHeadingProps {
  needsPerson: boolean;
  refresh: React.ReactNode;
}

export function JobsPageHeading({
  needsPerson,
  refresh,
}: JobsPageHeadingProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-bold text-display-md">
          {needsPerson ? "Needs a person" : "Scoring jobs"}
        </h1>
        <p className="m-0 text-body-sm text-muted-foreground">
          Every answer gets one scoring job. Failed jobs never count as a low
          score — retry them here or on the candidate page.
        </p>
      </div>
      {refresh}
    </div>
  );
}
