import type { Metadata } from "next";
import type { ReactNode } from "react";

import NavBar from "@/components/NavBar";

import "./globals.css";

export const metadata: Metadata = {
  title: "PlaySight",
  description: "Multi-sport video analytics and club operations platform",
};

/** Root layout: dark shell with sticky navigation. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <NavBar />
        <main className="mx-auto w-full max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
