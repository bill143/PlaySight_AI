import { PublishPanel } from "@/components/publish/PublishPanel";

export default function PublishPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Publish & Export</h1>
        <p className="mt-2 text-sm text-slate-400">
          Push completed highlight artifacts to YouTube with the right privacy
          setting for your coaching or fan workflow.
        </p>
      </div>
      <PublishPanel />
    </div>
  );
}
