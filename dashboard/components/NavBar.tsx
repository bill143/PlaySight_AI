"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { clearTokens, getAccessToken } from "@/lib/api";

/** Top navigation bar with brand link and sign-out action. */
export default function NavBar() {
  const router = useRouter();
  const pathname = usePathname();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(Boolean(getAccessToken()));
  }, [pathname]);

  function signOut(): void {
    clearTokens();
    setAuthed(false);
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold tracking-wide">
          <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full bg-sky-500" />
          <span>
            PlaySight<span className="text-sky-400">AI</span>
          </span>
        </Link>
        {authed ? (
          <button type="button" className="btn btn-ghost" onClick={signOut}>
            Sign out
          </button>
        ) : null}
      </div>
    </header>
  );
}
