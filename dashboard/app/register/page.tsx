"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getAccessToken, registerClub } from "@/lib/api";
import { errorMessage } from "@/lib/format";

/** Bootstrap page: creates the club plus its first admin user. */
export default function RegisterPage() {
  const router = useRouter();
  const [clubName, setClubName] = useState("");
  const [fullName, setFullName] = useState("");
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
      await registerClub({
        club_name: clubName.trim(),
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
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
          <h1 className="text-lg font-semibold text-white">Register a club</h1>
          <p className="text-sm text-slate-400">
            Creates your club and its first admin account.
          </p>
        </div>

        {error ? <p className="error-box">{error}</p> : null}

        <form className="space-y-3" onSubmit={(e) => void onSubmit(e)}>
          <div>
            <label className="label" htmlFor="reg-club">
              Club name
            </label>
            <input
              id="reg-club"
              type="text"
              className="input"
              value={clubName}
              onChange={(e) => setClubName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="reg-name">
              Your full name
            </label>
            <input
              id="reg-name"
              type="text"
              autoComplete="name"
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="reg-email">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="reg-password">
              Password
            </label>
            <input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              className="input"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={busy}>
            {busy ? "Creating club…" : "Create club"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400">
          Already registered?{" "}
          <Link href="/login" className="text-sky-400 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
