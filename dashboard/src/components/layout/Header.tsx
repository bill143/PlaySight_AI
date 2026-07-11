"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { clearTokens } from "@/lib/auth";

export function Header() {
  const router = useRouter();

  const handleSignOut = () => {
    clearTokens();
    router.replace("/login");
  };

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 px-4 py-4 backdrop-blur sm:px-6 lg:px-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-primary-300">
            PlaySight AI
          </p>
          <h2 className="text-xl font-semibold text-slate-100">
            Multi-Sport Analytics Dashboard
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 sm:block">
            Analyst Menu
          </div>
          <Button onClick={handleSignOut} size="sm" variant="outline">
            Sign Out
          </Button>
        </div>
      </div>
    </header>
  );
}
