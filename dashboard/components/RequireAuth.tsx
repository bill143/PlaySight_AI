"use client";

import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import Loading from "@/components/Loading";
import { getAccessToken } from "@/lib/api";

/**
 * Client-side auth guard: renders children only once an access token exists in
 * localStorage, otherwise redirects to `/login`.
 */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (getAccessToken()) {
      setReady(true);
    } else {
      router.replace("/login");
    }
  }, [router, pathname]);

  if (!ready) return <Loading label="Checking session…" />;
  return <>{children}</>;
}
