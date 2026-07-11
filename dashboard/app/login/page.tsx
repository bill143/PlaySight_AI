"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getAccessToken, login } from "@/lib/api";
import { errorMessage } from "@/lib/format";

/** Email/password sign-in page. */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getAccessToken()) router.replace("/");
  }, [router]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.push("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-16 w-full max-w-sm">
      <div className="card space-y-4">
        <div>
          <h1 className="text-lg font-semibold text-white">Sign in</h1>
          <p className="text-sm text-slate-400">Welcome back to PlaySight.</p>
        </div>

        {error ? <p className="error-box">{error}</p> : null}

        <form className="space-y-3" onSubmit={(e) => void onSubmit(e)}>
          <div>
            <label className="label" htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400">
          New club?{" "}
          <Link href="/register" className="text-sky-400 hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
